#!/usr/bin/env python3
"""Debug script to check model path resolution."""
import os
from pathlib import Path

# Simulate what segment_lobes.py does
script_dir = Path(__file__).resolve().parent
weights_dir = script_dir / "totalseg_data" / "nnunet" / "results"

print("=== Local layout ===")
print(f"Script dir: {script_dir}")
print(f"Expected weights dir: {weights_dir}")
print(f"  exists: {weights_dir.exists()}")
if weights_dir.exists():
    print(f"  contents:")
    for p in sorted(weights_dir.iterdir()):
        print(f"    {p.name} ({'dir' if p.is_dir() else 'file'})")
else:
    # Check partial paths
    for d in ["totalseg_data", "totalseg_data/nnunet", "totalseg_data/nnunet/results"]:
        full = script_dir / d
        print(f"  {d}: exists={full.exists()}")

print()

# Set env vars as our code would
os.environ["TOTALSEG_WEIGHTS_PATH"] = str(weights_dir)
os.environ["TOTALSEG_HOME_DIR"] = str(script_dir / "totalseg_data")

from totalsegmentator.config import get_weights_dir, setup_nnunet
setup_nnunet()

resolved_weights = get_weights_dir()
print("=== TotalSegmentator resolution ===")
print(f"get_weights_dir(): {resolved_weights}")
print(f"nnUNet_results: {os.environ.get('nnUNet_results')}")
print(f"  exists: {Path(resolved_weights).exists()}")
if Path(resolved_weights).exists():
    print(f"  contents:")
    for p in sorted(Path(resolved_weights).iterdir()):
        print(f"    {p.name} ({'dir' if p.is_dir() else 'file'})")

print()

# Check what folder names download_pretrained_weights expects
print("=== Expected model folders ===")
try:
    from totalsegmentator.libs import download_pretrained_weights
    import inspect
    src = inspect.getsource(download_pretrained_weights)
    # Extract lines that set weights_path for task 291 and 298
    for line in src.splitlines():
        if "291" in line or "298" in line or "weights_path" in line or "config_dir" in line:
            print(f"  {line.strip()}")
except Exception as e:
    print(f"  Error inspecting: {e}")

print()

# Also check ~/.totalsegmentator
default_dir = Path.home() / ".totalsegmentator" / "nnunet" / "results"
print(f"=== Default location: {default_dir} ===")
print(f"  exists: {default_dir.exists()}")
if default_dir.exists():
    print(f"  contents:")
    for p in sorted(default_dir.iterdir()):
        print(f"    {p.name} ({'dir' if p.is_dir() else 'file'})")
