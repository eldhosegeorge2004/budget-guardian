"""
Unified Runner for Budget Guardian
Runs both the FastAPI backend and Streamlit frontend in a single process.
Useful for single-instance deployments or lightweight cloud containers.
"""

import os
import subprocess
import sys
import time
import signal


def main():
    port = os.getenv("PORT", "8501")
    backend_port = "8000"

    print(f"[STARTUP] Seeding initial database...")
    subprocess.run([sys.executable, "-m", "backend.seed_demo_data"], check=False)

    print(f"[STARTUP] Launching FastAPI backend on port {backend_port}...")
    backend_proc = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "backend.main:app",
        "--host", "0.0.0.0",
        "--port", backend_port,
    ])

    # Wait for backend to initialize
    time.sleep(3)

    print(f"[STARTUP] Launching Streamlit dashboard on port {port}...")
    frontend_env = os.environ.copy()
    frontend_env["API_BASE"] = f"http://127.0.0.1:{backend_port}"

    frontend_proc = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", "frontend/app.py",
        "--server.port", port,
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
    ], env=frontend_env)

    def handle_exit(sig, frame):
        print("\n[SHUTDOWN] Stopping services...")
        backend_proc.terminate()
        frontend_proc.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    frontend_proc.wait()
    backend_proc.terminate()


if __name__ == "__main__":
    main()
