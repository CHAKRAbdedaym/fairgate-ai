"""Start both local services, select available ports, and stop both on Ctrl-C."""

import os, sys, socket, subprocess, signal, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv()


def free_port(preferred):
    for port in range(preferred, preferred + 30):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                pass
    raise SystemExit(f"No free port near {preferred}.")


api = free_port(int(os.getenv("BACKEND_PORT", "8000")))
web = free_port(int(os.getenv("FRONTEND_PORT", "3001")))
if api == web:
    web = free_port(web + 1)
env = os.environ.copy()
env["CORS_ORIGINS"] = ",".join(
    dict.fromkeys(
        env.get("CORS_ORIGINS", "").split(",")
        + [f"http://localhost:{web}", f"http://127.0.0.1:{web}"]
    )
)
env["API_PROXY_TARGET"] = f"http://127.0.0.1:{api}"
commands = [
    [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(api),
    ],
    ["npm", "run", "dev", "--prefix", "frontend", "--", "--port", str(web)],
]
children = []
print(
    f"\nFAIRGATE AI · http://localhost:{web}/demo\nAPI docs · http://127.0.0.1:{api}/docs\nSelected available ports: frontend {web}, backend {api}\n",
    flush=True,
)
try:
    for command in commands:
        children.append(
            subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=True)
        )
    while all(c.poll() is None for c in children):
        time.sleep(0.5)
except KeyboardInterrupt:
    pass
finally:
    for child in children:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
