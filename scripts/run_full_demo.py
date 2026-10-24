"""Compatibility launcher for the real-recording dashboard."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.unified_demo import main


if __name__ == "__main__":
    raise SystemExit(main())
