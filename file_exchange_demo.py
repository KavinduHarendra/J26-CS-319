"""Compatibility launcher for the real-recording integration demo.

Use ``demo.py`` for new commands. This filename remains available so existing
notes and scripts continue to run the same application.
"""

from src.unified_demo import main


if __name__ == "__main__":
    raise SystemExit(main())
