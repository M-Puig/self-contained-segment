#!/usr/bin/env python3
"""
Pre-download TotalSegmentator model weights needed for lung lobe segmentation.

Downloads only the two models required for task="total" with roi_subset
targeting lung lobes:
  - Task 291: organs (contains lung lobes)
  - Task 298: crop model (6mm, used for ROI localisation)

Models are saved to ./totalseg_models/ by default, ready to be bundled
with PyInstaller.

Usage:
    python download_models.py [--output-dir ./totalseg_models]
"""

import argparse
import os
import sys
from pathlib import Path


# Task IDs needed for lung lobe segmentation with roi_subset
REQUIRED_TASK_IDS = [291, 298]


def download_models(output_dir: Path) -> None:
    """Download the required TotalSegmentator model weights."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Tell TotalSegmentator to use our custom directory
    os.environ["TOTALSEG_WEIGHTS_PATH"] = str(output_dir)

    try:
        from totalsegmentator.config import setup_nnunet
    except ImportError:
        print("ERROR: totalsegmentator is not installed.")
        print("Install it with: pip install TotalSegmentator")
        sys.exit(1)

    setup_nnunet()

    from totalsegmentator.libs import download_pretrained_weights

    for task_id in REQUIRED_TASK_IDS:
        print(f"Downloading model for task {task_id}...")
        download_pretrained_weights(task_id)
        print(f"  Task {task_id} done.")

    # Also create a minimal config so TotalSegmentator doesn't prompt
    config_dir = output_dir.parent
    config_file = config_dir / "config.json"
    if not config_file.exists():
        import json
        config = {
            "totalseg_id": "bundled",
            "send_usage_stats": False,
            "statistics_disclaimer_shown": True,
            "prediction_counter": 0,
        }
        config_file.write_text(json.dumps(config, indent=2))
        print(f"Created config at {config_file}")

    # Print summary
    total_size = sum(
        f.stat().st_size for f in output_dir.rglob("*") if f.is_file()
    )
    print(f"\nModels downloaded to: {output_dir}")
    print(f"Total size: {total_size / (1024**2):.0f} MB")


def main():
    parser = argparse.ArgumentParser(
        description="Pre-download TotalSegmentator models for lung lobe segmentation."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("totalseg_data/nnunet/results"),
        help="Directory to save model weights (default: totalseg_data/nnunet/results)",
    )
    args = parser.parse_args()
    download_models(args.output_dir)


if __name__ == "__main__":
    main()
