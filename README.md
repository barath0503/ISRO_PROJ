# Distributed RF Clock Synchronization Dashboard

Plotly Dash simulation for six RF clock nodes in Tamil Nadu, India. The model runs an extended Kuramoto synchronizer with propagation delay, oscillator drift, Gaussian phase-rate noise, GNSS reference switching, and a PINN-inspired drift correction path.

## Run in VS Code

1. Open this folder in VS Code.
2. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Start the dashboard:

   ```powershell
   python app.py
   ```

5. Open `http://127.0.0.1:8050`.
