import signal
import sys

import cli


def _on_sigterm(signum, frame):
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGTERM, _on_sigterm)
    try:
        cli.main()
    except KeyboardInterrupt:
        print("\nClosed.")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
