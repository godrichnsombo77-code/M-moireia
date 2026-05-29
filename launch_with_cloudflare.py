import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import socket
from pathlib import Path

import requests


APP_DIR = Path(__file__).resolve().parent
APP_HOST = "127.0.0.1"
APP_PORT = int(os.getenv("APP_PORT", "7860"))
TUNNEL_TARGET = f"http://{APP_HOST}:{APP_PORT}"
URL_PATTERN = re.compile(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com")


def find_cloudflared_executable() -> str | None:
    candidates = []
    env_path = os.getenv("CLOUDFLARED_EXE", "").strip()
    if env_path:
        candidates.append(env_path)
    which_path = shutil.which("cloudflared")
    if which_path:
        candidates.append(which_path)
    candidates.extend(
        [
            r"C:\Program Files\cloudflared\cloudflared.exe",
            r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
            str(Path.home() / "Downloads" / "cloudflared.exe"),
        ]
    )
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return str(path)
    return None


def pump_output(pipe, on_line):
    try:
        for raw in iter(pipe.readline, ""):
            if not raw:
                break
            line = raw.rstrip()
            if line:
                on_line(line)
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def is_port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def find_free_port(host: str, start_port: int, search_limit: int = 25) -> int:
    for port in range(start_port, start_port + search_limit):
        if is_port_free(host, port):
            return port
    raise RuntimeError(f"Aucun port libre trouve a partir de {start_port}.")


def main() -> int:
    cloudflared_exe = find_cloudflared_executable()
    if not cloudflared_exe:
        print("cloudflared introuvable.")
        print("Installe-le avec:")
        print("  winget install --id Cloudflare.cloudflared")
        print("ou definit CLOUDFLARED_EXE vers cloudflared.exe")
        return 1

    app_port = find_free_port(APP_HOST, APP_PORT)
    tunnel_target = f"http://{APP_HOST}:{app_port}"

    uvicorn_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app:app",
        "--host",
        APP_HOST,
        "--port",
        str(app_port),
    ]
    cloudflared_cmd = [
        cloudflared_exe,
        "tunnel",
        "--url",
        tunnel_target,
        "--no-autoupdate",
    ]

    app_proc = subprocess.Popen(
        uvicorn_cmd,
        cwd=str(APP_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    public_url = None

    def handle_cloudflared_line(line: str) -> None:
        nonlocal public_url
        print(line)
        if public_url is None:
            match = URL_PATTERN.search(line)
            if match:
                public_url = match.group(0)
                print()
                print("=" * 72)
                print("URL HTTPS pour le telephone:")
                print(public_url)
                print("=" * 72)
                print()

    def handle_app_line(line: str) -> None:
        print(line)

    app_thread = threading.Thread(
        target=pump_output,
        args=(app_proc.stdout, handle_app_line),
        daemon=True,
    )
    app_thread.start()

    print(f"Application locale: {tunnel_target}")
    print("En attente que l'API reponde...")

    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            response = requests.get(f"http://{APP_HOST}:{app_port}/health", timeout=2)
            if response.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        print("L'API locale n'a pas repondu a temps. Arret.")
        try:
            app_proc.terminate()
        except Exception:
            pass
        return 1

    print("API prete. Demarrage du tunnel Cloudflare...")
    tunnel_proc = subprocess.Popen(
        cloudflared_cmd,
        cwd=str(APP_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )
    tunnel_thread = threading.Thread(
        target=pump_output,
        args=(tunnel_proc.stdout, handle_cloudflared_line),
        daemon=True,
    )
    tunnel_thread.start()
    print("En attente de l'URL Cloudflare...")

    try:
        while True:
            if app_proc.poll() is not None:
                return app_proc.returncode or 0
            if tunnel_proc.poll() is not None:
                return tunnel_proc.returncode or 0
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for proc in (tunnel_proc, app_proc):
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
        for proc in (tunnel_proc, app_proc):
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
