import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
SERVICE = "cli"


def compose(*args, **kwargs):
    return subprocess.run(["docker", "compose", *args], cwd=PROJECT_DIR, **kwargs)


def container_id():
    result = compose("ps", "-q", SERVICE, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def main():
    if shutil.which("docker") is None:
        print("docker was not found on PATH.", file=sys.stderr)
        return 1

    try:
        compose("up", "-d", "--build", check=True)
    except subprocess.CalledProcessError as exc:
        print(f"`docker compose up` failed (exit {exc.returncode}).", file=sys.stderr)
        return exc.returncode

    cid = container_id()
    if not cid:
        print(f"Service '{SERVICE}' is not running; nothing to attach to.", file=sys.stderr)
        compose("down")
        return 1

    try:
        subprocess.run(["docker", "attach", cid])
    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopping container...")
        compose("down")

    return 0


if __name__ == "__main__":
    sys.exit(main())
