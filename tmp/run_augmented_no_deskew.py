"""Run the augmented benchmark with the optional deskew candidate disabled."""

import runpy
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]),
                str(Path(__file__).resolve().parents[1] / "model")]
from model import photo_geometry

photo_geometry.deskew_table = lambda source: None
sys.modules["photo_geometry"] = photo_geometry
runpy.run_path(str(Path(__file__).resolve().parents[1] / "model" / "benchmark_augmented.py"),
               run_name="__main__")
