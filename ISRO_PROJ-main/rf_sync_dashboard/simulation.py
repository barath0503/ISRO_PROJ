:root {
    --bg: #02050b;
    --panel: #07111f;
    --panel-strong: #0a1728;
    --cyan: #35f6ff;
    --blue: #176bff;
    --red: #ff5470;
    --text: #d8f3ff;
    --muted: #83a9bf;
    --line: rgba(117, 211, 255, 0.18);
}

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: Inter, "Segoe UI", Arial, sans-serif;
}

.app-shell {
    min-height: 100vh;
    padding: 18px;
    background:
        radial-gradient(circle at 12% 6%, rgba(23, 107, 255, 0.16), transparent 30%),
        linear-gradient(135deg, #02050b 0%, #06101d 54%, #02050b 100%);
}

.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    min-height: 72px;
    margin-bottom: 16px;
    padding: 18px 20px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: rgba(7, 17, 31, 0.88);
    box-shadow: 0 0 24px rgba(53, 246, 255, 0.08);
}

.title {
    font-size: clamp(1.15rem, 2vw, 1.75rem);
    font-weight: 750;
    letter-spacing: 0;
}

.subtitle {
    margin-top: 4px;
    color: var(--muted);
    font-size: 0.95rem;
}

.status-strip {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 8px;
}

.status-pill {
    min-width: 96px;
    padding: 8px 11px;
    border: 1px solid rgba(53, 246, 255, 0.28);
    border-radius: 6px;
    background: rgba(8, 28, 48, 0.86);
    color: var(--text);
    text-align: center;
    font-size: 0.82rem;
    font-weight: 700;
}

.dashboard-grid {
    display: grid;
    grid-template-columns: 330px minmax(360px, 1fr) minmax(360px, 0.82fr);
    grid-template-rows: minmax(390px, calc((100vh - 130px) * 0.58)) minmax(300px, calc((100vh - 130px) * 0.42));
    gap: 16px;
}

.panel {
    min-width: 0;
    min-height: 0;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: rgba(7, 17, 31, 0.92);
    box-shadow: 0 0 28px rgba(0, 0, 0, 0.34);
    overflow: hidden;
}

.control-panel {
    grid-row: 1 / span 2;
    padding: 18px;
    overflow-y: auto;
}

.map-panel,
.phase-panel,
.error-panel {
    padding: 0;
}

.error-panel {
    grid-column: 2 / span 2;
}

.panel-heading {
    margin-bottom: 16px;
    color: var(--text);
    font-size: 1rem;
    font-weight: 750;
}

.button-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 18px;
}

button {
    height: 42px;
    border-radius: 6px;
    border: 1px solid transparent;
    color: var(--text);
    font: inherit;
    font-weight: 750;
    cursor: pointer;
}

.primary-button {
    background: linear-gradient(135deg, var(--blue), #00a7ff);
    box-shadow: 0 0 16px rgba(53, 246, 255, 0.25);
}

.secondary-button {
    border-color: rgba(117, 211, 255, 0.26);
    background: #0b1d32;
}

button:hover {
    filter: brightness(1.12);
}

.toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 0 16px;
    border-top: 1px solid var(--line);
    border-bottom: 1px solid var(--line);
    color: var(--muted);
    font-weight: 700;
}

.switch label {
    position: relative;
    display: inline-block;
    width: 54px;
    height: 30px;
}

.switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.switch label::before {
    content: "";
    position: absolute;
    inset: 0;
    border: 1px solid rgba(117, 211, 255, 0.28);
    border-radius: 999px;
    background: #182335;
    transition: 160ms ease;
}

.switch label::after {
    content: "";
    position: absolute;
    top: 4px;
    left: 5px;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: #7892a8;
    transition: 160ms ease;
}

.switch label:has(input:checked)::before {
    background: rgba(53, 246, 255, 0.28);
    border-color: rgba(53, 246, 255, 0.70);
}

.switch label:has(input:checked)::after {
    left: 27px;
    background: var(--cyan);
    box-shadow: 0 0 12px rgba(53, 246, 255, 0.72);
}

.control-block {
    margin-top: 20px;
}

.control-block label {
    display: block;
    margin-bottom: 8px;
    color: var(--muted);
    font-size: 0.88rem;
    font-weight: 750;
}

.control-block .rc-slider-track {
    background-color: var(--cyan);
}

.control-block .rc-slider-rail {
    background-color: #1a2a3f;
}

.control-block .rc-slider-handle {
    border-color: var(--cyan);
    background-color: var(--cyan);
    box-shadow: 0 0 10px rgba(53, 246, 255, 0.62);
}

.control-block .rc-slider-mark-text {
    color: var(--muted);
}

.metric-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 22px;
}

.metric-card {
    min-height: 72px;
    padding: 12px;
    border: 1px solid rgba(117, 211, 255, 0.14);
    border-radius: 8px;
    background: rgba(10, 23, 40, 0.86);
}

.metric-label {
    color: var(--muted);
    font-size: 0.76rem;
    font-weight: 700;
}

.metric-value {
    margin-top: 8px;
    color: var(--text);
    font-size: 1rem;
    font-weight: 760;
    overflow-wrap: anywhere;
}

.graph {
    width: 100%;
    height: 100%;
}

.graph [data-dash-is-loading="true"],
.graph[data-dash-is-loading="true"] {
    opacity: 1 !important;
    visibility: visible !important;
}

.graph .dash-spinner {
    display: none !important;
}

.graph .js-plotly-plot {
    width: 100%;
    height: 100%;
}

@media (max-width: 1180px) {
    .dashboard-grid {
        grid-template-columns: 300px 1fr;
        grid-template-rows: 420px 420px 340px;
    }

    .control-panel {
        grid-row: 1 / span 3;
    }

    .phase-panel {
        grid-column: 2;
    }

    .error-panel {
        grid-column: 2;
    }
}

@media (max-width: 860px) {
    .app-shell {
        padding: 12px;
    }

    .topbar {
        align-items: flex-start;
        flex-direction: column;
    }

    .status-strip {
        justify-content: flex-start;
    }

    .dashboard-grid {
        display: flex;
        flex-direction: column;
    }

    .control-panel {
        max-height: none;
    }

    .map-panel,
    .phase-panel,
    .error-panel {
        height: 390px;
    }
}

/* ── Jammer Localization Panel ─────────────────────────────── */
.jammer-panel-active {
    border: 1px solid rgba(255, 84, 112, 0.6) !important;
    background: rgba(40, 10, 18, 0.88) !important;
    box-shadow: 0 0 18px rgba(255, 84, 112, 0.18);
    animation: jammer-pulse 2.4s ease-in-out infinite;
}

@keyframes jammer-pulse {
    0%   { box-shadow: 0 0 10px rgba(255, 84, 112, 0.15); }
    50%  { box-shadow: 0 0 26px rgba(255, 84, 112, 0.38); }
    100% { box-shadow: 0 0 10px rgba(255, 84, 112, 0.15); }
}

.jammer-section-heading {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
    margin: 18px 0 6px;
    padding-bottom: 4px;
    border-bottom: 1px solid var(--line);
}

.loc-error-highlight {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 10px;
    padding: 8px 10px;
    border-radius: 6px;
    background: rgba(255, 209, 102, 0.07);
    border: 1px solid rgba(255, 209, 102, 0.28);
    font-size: 0.88rem;
    font-weight: 700;
}

.loc-error-value {
    color: #ffd166;
    font-size: 1.1rem;
    font-weight: 800;
}

.loc-error-na {
    color: #83a9bf;
    font-size: 1.0rem;
    font-weight: 700;
}

.check-row {
    padding: 12px 0;
    border-top: 1px solid var(--line);
    color: var(--muted);
    font-size: 0.88rem;
    font-weight: 700;
}

/* ── Jammer Error Banner ─────────────────────────────────────── */
.jammer-error-banner {
    padding: 14px;
    border-radius: 10px;
    border: 1px solid rgba(117, 211, 255, 0.18);
    background: rgba(10, 23, 40, 0.92);
    transition: border-color 0.4s ease, background 0.4s ease;
}

.jammer-error-banner--active {
    border-color: rgba(255, 84, 112, 0.60);
    background: rgba(35, 8, 16, 0.92);
    box-shadow: 0 0 20px rgba(255, 84, 112, 0.14);
    animation: banner-pulse 2.6s ease-in-out infinite;
}

@keyframes banner-pulse {
    0%   { box-shadow: 0 0 10px rgba(255, 84, 112, 0.12); }
    50%  { box-shadow: 0 0 28px rgba(255, 84, 112, 0.32); }
    100% { box-shadow: 0 0 10px rgba(255, 84, 112, 0.12); }
}

.jammer-error-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(117, 211, 255, 0.12);
}

.jammer-error-title {
    color: var(--muted);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
}

.jammer-info-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10px;
}

.jammer-info-cell {
    padding: 10px;
    border-radius: 7px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(117, 211, 255, 0.09);
}

.jammer-info-cell--error {
    background: rgba(255, 209, 102, 0.06);
    border-color: rgba(255, 209, 102, 0.22);
}

.jammer-info-label {
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 6px;
}

.jammer-info-label--true { color: #ff5470; }
.jammer-info-label--est  { color: #ffd166; }
.jammer-info-label--err  { color: #83a9bf; }

.jammer-info-value {
    color: var(--text);
    font-size: 0.75rem;
    font-weight: 700;
    overflow-wrap: anywhere;
    line-height: 1.4;
}

/* Large error value display */
.jammer-error-value {
    font-size: 1.28rem;
    font-weight: 900;
    letter-spacing: -0.01em;
    margin-top: 2px;
    transition: color 0.4s ease;
}

.jammer-error-value--na   { color: #83a9bf !important; font-size: 1.05rem; }
.jammer-error-value--good { text-shadow: 0 0 12px rgba(77, 255, 136, 0.45); }
.jammer-error-value--warn { text-shadow: 0 0 12px rgba(255, 209, 102, 0.45); }
.jammer-error-value--bad  { text-shadow: 0 0 12px rgba(255, 84, 112, 0.45); }


/* ── Live Coordinate Readout Widget ─────────────────────────────── */
.jammer-coord-readout {
    margin-top: 14px;
    padding: 12px 14px;
    border-radius: 10px;
    border: 1px solid rgba(53, 246, 255, 0.20);
    background: linear-gradient(135deg, rgba(10, 23, 40, 0.96) 0%, rgba(5, 14, 26, 0.96) 100%);
    box-shadow: 0 0 18px rgba(53, 246, 255, 0.06);
    transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.jammer-coord-readout:hover {
    border-color: rgba(53, 246, 255, 0.38);
    box-shadow: 0 0 22px rgba(53, 246, 255, 0.12);
}

.coord-readout-row {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
}

.coord-readout-label {
    font-size: 0.67rem;
    font-weight: 800;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: var(--muted);
}

.coord-readout-values {
    display: flex;
    align-items: center;
    gap: 0;
}

.coord-value-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;
    gap: 4px;
}

.coord-axis-tag {
    font-size: 0.60rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--cyan);
    opacity: 0.65;
}

.coord-axis-value {
    font-size: 0.98rem;
    font-weight: 800;
    color: var(--cyan);
    letter-spacing: 0.02em;
    text-shadow: 0 0 10px rgba(53, 246, 255, 0.50);
    transition: color 0.2s ease, text-shadow 0.2s ease;
    font-variant-numeric: tabular-nums;
}

.coord-divider {
    width: 1px;
    height: 36px;
    background: rgba(53, 246, 255, 0.22);
    margin: 0 10px;
    flex-shrink: 0;
}

/* Map marker legend hint below coordinate readout */
.coord-map-hint {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid rgba(53, 246, 255, 0.10);
}

.coord-hint-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
}

.coord-hint-text {
    font-size: 0.65rem;
    color: var(--muted);
    line-height: 1.3;
}
