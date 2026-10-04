"""Run the original-image benchmark with optional deskew disabled."""

import runpy
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / "model")]
from model import photo_geometry

photo_geometry.deskew_table = lambda source: None
sys.modules["photo_geometry"] = photo_geometry
runpy.run_path(str(root / "model" / "benchmark_images.py"), run_name="__main__")
