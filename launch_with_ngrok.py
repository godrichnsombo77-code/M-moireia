import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests


APP_DIR = Path(__file__).resolve().parent
APP_HOST = "127.0.0.1"
APP_PORT = int(os.getenv("APP_PORT", "7860"))
NGROK_API = "http://127.0.0.1:4040/api/tunnels"


def find_ngrok_executable() -> str | None:
    candidates = []
    env_path = os.getenv("NGROK_EXE", "").strip()
    if env_path:
        candidates.append(env_path)
    which_path = shutil.which("ngrok")
    if which_path:
        candidates.append(which_path)
    candidates.extend(
        [
            r"C:\Program Files\ngrok\ngrok.exe",
            r"C:\Program Files (x86)\ngrok\ngrok.exe",
            str(Path.home() / "Downloads" / "ngrok.exe"),
        ]
    )
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return str(path)
    return None


def wait_for_public_url(timeout_seconds: int = 30) -> str | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(NGROK_API, timeout=2)
            if response.status_code == 200:
                data = response.json()
                for tunnel in data.get("tunnels", []):
                    public_url = tunnel.get("public_url", "")
                    if public_url.startswith("https://"):
                        return public_url
        except Exception:
            pass
        time.sleep(1)
    return None


def main() -> int:
    ngrok_exe = find_ngrok_executable()
    if not ngrok_exe:
        print("ngrok introuvable. Installe-le ou definis NGROK_EXE vers ngrok.exe.")
        return 1

    uvicorn_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app:app",
        "--host",
        APP_HOST,
        "--port",
        str(APP_PORT),
    ]
    ngrok_cmd = [
        ngrok_exe,
        "http",
        str(APP_PORT),
    ]

    app_proc = subprocess.Popen(uvicorn_cmd, cwd=str(APP_DIR))
    ngrok_proc = subprocess.Popen(ngrok_cmd, cwd=str(APP_DIR))

    try:
        public_url = wait_for_public_url()
        if public_url:
            print()
            print("=" * 72)
            print("URL HTTPS pour le telephone:")
            print(public_url)
            print("=" * 72)
            print()
        else:
            print("Impossible de recuperer l'URL ngrok via l'API locale.")
            print("Verifie que ngrok tourne bien sur http://127.0.0.1:4040")

        print(f"Application locale: http://{APP_HOST}:{APP_PORT}")
        print("Laisse cette fenetre ouverte pour garder le tunnel actif.")

        while True:
            if app_proc.poll() is not None:
                return app_proc.returncode or 0
            if ngrok_proc.poll() is not None:
                return ngrok_proc.returncode or 0
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for proc in (ngrok_proc, app_proc):
            if proc and proc.poll() is None:
                try:
                    if os.name == "nt":
                        proc.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        proc.terminate()
                except Exception:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
        for proc in (ngrok_proc, app_proc):
            if proc:
                try:
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
