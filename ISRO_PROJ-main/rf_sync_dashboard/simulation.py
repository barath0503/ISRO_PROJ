from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rf_sync_dashboard.config import (
    CLOCK_FREQUENCY_HZ,
    LATITUDES,
    LONGITUDES,
    MAX_HISTORY_POINTS,
    NODE_NAMES,
    NODES,
    NS_PER_RADIAN,
    RNG_SEED,
    SPEED_OF_LIGHT_MPS,
    SYNC_WAVE_PERIOD_S,
)


@dataclass(frozen=True)
class SimulationParameters:
    coupling_strength: float
    noise_level: float
    drift_intensity: float
    gnss_enabled: bool


@dataclass(frozen=True)
class SimulationSnapshot:
    time_s: float
    node_names: tuple[str, ...]
    latitudes: np.ndarray
    longitudes: np.ndarray
    proposed_theta: np.ndarray
    baseline_theta: np.ndarray
    proposed_error_ns: np.ndarray
    baseline_error_ns: np.ndarray
    proposed_rms_ns: float
    baseline_rms_ns: float
    order_parameter: float
    temperatures_c: np.ndarray
    history_time_s: np.ndarray
    history_proposed_rms_ns: np.ndarray
    history_baseline_rms_ns: np.ndarray


class KuramotoClockNetwork:
    """Vectorized six-node RF clock synchronization model."""

    def __init__(self, seed: int = RNG_SEED) -> None:
        self._seed = seed
        self._rng = np.random.default_rng(seed)
        self._node_count = len(NODES)
        self._distances_m = self._distance_matrix_m()
        self._topology = self._topology_matrix()
        self._delay_phase = self._delay_phase_matrix()

        self._frequency_bias_ppm = np.array(
            [0.010, -0.016, 0.021, -0.018, 0.014, -0.011],
            dtype=float,
        )
        self._natural_frequency_rate = self._ppm_to_phase_rate(
            self._frequency_bias_ppm
        )
        self._temp_coeff_ppm = np.array(
            [0.00074, 0.00088, 0.00070, 0.00095, 0.00082, 0.00079],
            dtype=float,
        )
        self._aging_ppm_per_hour = np.array(
            [0.0018, -0.0011, 0.0015, -0.0016, 0.0012, -0.0014],
            dtype=float,
        )
        self._thermal_phase = np.linspace(
            0.0,
            2.0 * np.pi,
            self._node_count,
            endpoint=False,
        )
        self.reset()

    def reset(self) -> None:
        self.time_s = 0.0
        initial_theta = self._rng.uniform(-0.55, 0.55, self._node_count)
        self.proposed_theta = initial_theta.copy()
        self.baseline_theta = initial_theta.copy()
        self.temperatures_c = self._temperature_profile(0.0)
        self.history_time_s = np.array([], dtype=float)
        self.history_proposed_rms_ns = np.array([], dtype=float)
        self.history_baseline_rms_ns = np.array([], dtype=float)
        self._append_history()

    def step(self, dt_s: float, params: SimulationParameters) -> SimulationSnapshot:
        self.time_s += dt_s
        self.temperatures_c = self._temperature_profile(self.time_s)

        if params.gnss_enabled:
            self.proposed_theta = np.zeros(self._node_count, dtype=float)
            self.baseline_theta = np.zeros(self._node_count, dtype=float)
            self._append_history()
            return self.snapshot()

        drift_rate = self._oscillator_drift_rate(
            self.temperatures_c,
            self.time_s,
            params.drift_intensity,
        )
        noise_rate = self._rng.normal(
            loc=0.0,
            scale=params.noise_level,
            size=self._node_count,
        )

        baseline_rate = (
            self._natural_frequency_rate
            + self._kuramoto_rate(self.baseline_theta, params.coupling_strength)
            + drift_rate
            + noise_rate
        )
        proposed_rate = (
            self._natural_frequency_rate
            + self._kuramoto_rate(self.proposed_theta, params.coupling_strength)
            + drift_rate
            + noise_rate
            - self._pinn_drift_correction(
                self.proposed_theta,
                self.temperatures_c,
                self.time_s,
                params.drift_intensity,
            )
        )

        self.baseline_theta = self.baseline_theta + dt_s * baseline_rate
        self.proposed_theta = self.proposed_theta + dt_s * proposed_rate
        self._append_history()
        return self.snapshot()

    def snapshot(self) -> SimulationSnapshot:
        proposed_error = self._phase_to_error_ns(self.proposed_theta)
        baseline_error = self._phase_to_error_ns(self.baseline_theta)
        proposed_rms = float(np.sqrt(np.mean(np.square(proposed_error))))
        baseline_rms = float(np.sqrt(np.mean(np.square(baseline_error))))
        order_parameter = float(
            np.abs(np.mean(np.exp(1j * np.mod(self.proposed_theta, 2.0 * np.pi))))
        )

        return SimulationSnapshot(
            time_s=float(self.time_s),
            node_names=NODE_NAMES,
            latitudes=LATITUDES.copy(),
            longitudes=LONGITUDES.copy(),
            proposed_theta=self.proposed_theta.copy(),
            baseline_theta=self.baseline_theta.copy(),
            proposed_error_ns=proposed_error,
            baseline_error_ns=baseline_error,
            proposed_rms_ns=proposed_rms,
            baseline_rms_ns=baseline_rms,
            order_parameter=order_parameter,
            temperatures_c=self.temperatures_c.copy(),
            history_time_s=self.history_time_s.copy(),
            history_proposed_rms_ns=self.history_proposed_rms_ns.copy(),
            history_baseline_rms_ns=self.history_baseline_rms_ns.copy(),
        )

    def _kuramoto_rate(
        self,
        theta: np.ndarray,
        coupling_strength: float,
    ) -> np.ndarray:
        phase_delta = theta[np.newaxis, :] - theta[:, np.newaxis]
        interaction = np.sin(phase_delta - self._delay_phase)
        return coupling_strength * np.sum(self._topology * interaction, axis=1)

    def _oscillator_drift_rate(
        self,
        temperatures_c: np.ndarray,
        time_s: float,
        drift_intensity: float,
    ) -> np.ndarray:
        thermal_offset_c = temperatures_c - 25.0
        thermal_ppm = self._temp_coeff_ppm * np.square(thermal_offset_c)
        aging_ppm = self._aging_ppm_per_hour * (time_s / 3600.0)
        colored_model_error_ppm = 0.0016 * np.sin(
            0.17 * time_s + self._thermal_phase
        )
        total_ppm = (
            drift_intensity * (thermal_ppm + aging_ppm)
            + colored_model_error_ppm
        )
        return self._ppm_to_phase_rate(total_ppm)

    def _pinn_drift_correction(
        self,
        theta: np.ndarray,
        temperatures_c: np.ndarray,
        time_s: float,
        drift_intensity: float,
    ) -> np.ndarray:
        physics_rate = self._physics_drift_predictor(
            temperatures_c,
            time_s,
            drift_intensity,
        )
        holdover_anchor = 0.44 * np.tanh(theta / 0.70)
        consensus_residual = 0.12 * (theta - np.mean(theta))
        return physics_rate + holdover_anchor + consensus_residual

    def _physics_drift_predictor(
        self,
        temperatures_c: np.ndarray,
        time_s: float,
        drift_intensity: float,
    ) -> np.ndarray:
        thermal_offset_c = temperatures_c - 25.0
        nominal_thermal_ppm = 0.97 * self._temp_coeff_ppm * np.square(
            thermal_offset_c
        )
        nominal_aging_ppm = 0.90 * self._aging_ppm_per_hour * (time_s / 3600.0)
        nominal_bias_ppm = 0.95 * self._frequency_bias_ppm
        drift_ppm = nominal_bias_ppm + drift_intensity * (
            nominal_thermal_ppm + nominal_aging_ppm
        )
        return self._ppm_to_phase_rate(drift_ppm)

    def _append_history(self) -> None:
        proposed_error = self._phase_to_error_ns(self.proposed_theta)
        baseline_error = self._phase_to_error_ns(self.baseline_theta)
        proposed_rms = np.sqrt(np.mean(np.square(proposed_error)))
        baseline_rms = np.sqrt(np.mean(np.square(baseline_error)))

        self.history_time_s = np.append(self.history_time_s, self.time_s)
        self.history_proposed_rms_ns = np.append(
            self.history_proposed_rms_ns,
            proposed_rms,
        )
        self.history_baseline_rms_ns = np.append(
            self.history_baseline_rms_ns,
            baseline_rms,
        )

        if self.history_time_s.size > MAX_HISTORY_POINTS:
            self.history_time_s = self.history_time_s[-MAX_HISTORY_POINTS:]
            self.history_proposed_rms_ns = self.history_proposed_rms_ns[
                -MAX_HISTORY_POINTS:
            ]
            self.history_baseline_rms_ns = self.history_baseline_rms_ns[
                -MAX_HISTORY_POINTS:
            ]

    def _temperature_profile(self, time_s: float) -> np.ndarray:
        diurnal = 5.0 * np.sin((2.0 * np.pi * time_s / 180.0) + self._thermal_phase)
        local_gradient = np.array([3.5, 0.5, 2.8, 4.0, 3.0, 1.2], dtype=float)
        weather = 0.8 * np.sin((2.0 * np.pi * time_s / 51.0) + 0.7)
        return 28.0 + local_gradient + diurnal + weather

    def _distance_matrix_m(self) -> np.ndarray:
        lat = np.radians(LATITUDES)
        lon = np.radians(LONGITUDES)
        lat_delta = lat[:, np.newaxis] - lat[np.newaxis, :]
        lon_delta = lon[:, np.newaxis] - lon[np.newaxis, :]
        haversine = (
            np.sin(lat_delta / 2.0) ** 2
            + np.cos(lat[:, np.newaxis])
            * np.cos(lat[np.newaxis, :])
            * np.sin(lon_delta / 2.0) ** 2
        )
        return 6_371_000.0 * 2.0 * np.arctan2(
            np.sqrt(haversine),
            np.sqrt(1.0 - haversine),
        )

    def _topology_matrix(self) -> np.ndarray:
        topology = np.exp(-self._distances_m / 420_000.0)
        np.fill_diagonal(topology, 0.0)
        row_sum = np.sum(topology, axis=1, keepdims=True)
        return np.divide(topology, row_sum, out=np.zeros_like(topology), where=row_sum > 0)

    def _delay_phase_matrix(self) -> np.ndarray:
        propagation_s = self._distances_m / SPEED_OF_LIGHT_MPS
        phase = 2.0 * np.pi * propagation_s / SYNC_WAVE_PERIOD_S
        np.fill_diagonal(phase, 0.0)
        return phase

    @staticmethod
    def _ppm_to_phase_rate(ppm: np.ndarray) -> np.ndarray:
        return 2.0 * np.pi * CLOCK_FREQUENCY_HZ * ppm * 1.0e-6

    @staticmethod
    def _phase_to_error_ns(theta: np.ndarray) -> np.ndarray:
        return theta * NS_PER_RADIAN
