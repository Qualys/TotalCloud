#!/usr/bin/env python3
"""Cross-platform launcher for the Qualys Posture Dashboard — no bash required.

  python run.py                 → run in the FOREGROUND on http://localhost:8770 (Ctrl+C to stop)
  python run.py start           → run in the BACKGROUND (terminal can close); writes a PID file
  python run.py stop            → stop the background server
  python run.py status          → is it running?
  python run.py --demo          → seed synthetic sample data (no live Qualys needed)
  python run.py --port 9000     → use a different port  (works with foreground or start)

Uses only the Python standard library, so it runs with the system `python3`; it creates a local
`.venv`, installs the backend deps into it, and launches the app with that venv's Python.
"""
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
VENV = ROOT / ".venv"
PIDFILE = ROOT / ".qpd.pid"
LOGFILE = ROOT / "qpd.log"
IS_WIN = os.name == "nt"
VENV_PY = VENV / ("Scripts/python.exe" if IS_WIN else "bin/python")


def venv_python() -> str:
    return str(VENV_PY)


def deps_ok() -> bool:
    if not VENV_PY.exists():
        return False
    try:
        subprocess.check_call([venv_python(), "-c", "import fastapi, uvicorn, pydantic, cryptography, openpyxl"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def ensure_env() -> None:
    if not VENV_PY.exists():
        print("› Creating virtualenv (.venv)…")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    if not deps_ok():
        print("› Installing backend dependencies…")
        subprocess.check_call([venv_python(), "-m", "pip", "install", "-q",
                               "--disable-pip-version-check", "-r", str(BACKEND / "requirements.txt")])
    if not (ROOT / "frontend" / "dist" / "index.html").exists():
        print("⚠  frontend/dist not found — the API will run but the UI won't be served.")
        print("   Build it once with:  cd frontend && npm ci && npm run build")


def read_pid():
    try:
        return int(PIDFILE.read_text().strip())
    except Exception:
        return None


def is_alive(pid) -> bool:
    if not pid:
        return False
    try:
        if IS_WIN:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True).stdout
            return str(pid) in out
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def app_command(port: int, extra: list) -> list:
    return [venv_python(), "app.py", "--port", str(port)] + extra


def cmd_status(port: int) -> None:
    pid = read_pid()
    print(f"Running (pid {pid}) → http://localhost:{port}" if is_alive(pid) else "Not running.")


def cmd_stop() -> None:
    pid = read_pid()
    if is_alive(pid):
        try:
            if IS_WIN:
                subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
        except Exception as e:
            print("Stop error:", e)
        try:
            PIDFILE.unlink()
        except OSError:
            pass
        print(f"Stopped (pid {pid}).")
    else:
        try:
            PIDFILE.unlink()
        except OSError:
            pass
        print("Not running.")


def cmd_start(port: int, extra: list) -> None:
    if is_alive(read_pid()):
        print(f"Already running (pid {read_pid()}) → http://localhost:{port}. Use: python run.py stop")
        return
    ensure_env()
    log = open(LOGFILE, "ab")
    kwargs = dict(cwd=str(BACKEND), stdout=log, stderr=log, stdin=subprocess.DEVNULL)
    if IS_WIN:
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP → survives closing the console.
        kwargs["creationflags"] = 0x00000008 | 0x00000200
    else:
        kwargs["start_new_session"] = True  # setsid → survives closing the terminal.
    p = subprocess.Popen(app_command(port, extra + ["--no-browser"]), **kwargs)
    PIDFILE.write_text(str(p.pid))
    print(f"› Started in background (pid {p.pid}) → http://localhost:{port}")
    print(f"  logs: {LOGFILE}   ·   stop: python run.py stop   ·   status: python run.py status")


def cmd_foreground(port: int, extra: list) -> None:
    if is_alive(read_pid()):
        print(f"Already running (pid {read_pid()}) → http://localhost:{port}. Use: python run.py stop")
        return
    ensure_env()
    print(f"› Starting on http://localhost:{port}  (Ctrl+C to stop)")
    try:
        subprocess.call(app_command(port, extra), cwd=str(BACKEND))
    except KeyboardInterrupt:
        print("\nStopped.")


def main() -> None:
    args = sys.argv[1:]
    port, command, extra = 8770, None, []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("start", "stop", "status"):
            command = a
        elif a == "--port":
            port = int(args[i + 1]); i += 1
        else:
            extra.append(a)
        i += 1
    if command == "status":
        cmd_status(port)
    elif command == "stop":
        cmd_stop()
    elif command == "start":
        cmd_start(port, extra)
    else:
        cmd_foreground(port, extra)


if __name__ == "__main__":
    main()
