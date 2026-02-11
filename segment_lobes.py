#!/usr/bin/env python3
"""
Self-contained lung CT lobe segmentation tool.

Takes DICOM lung CT data as input, segments the 5 pulmonary lobes using
TotalSegmentator, and outputs a CSV with per-lobe voxel counts and
voxels below a user-defined HU threshold.

Consolidates the 3-step pipeline (dicom2nifti → nifti2tseg → lobestats)
from clippcair-analyse/scripts/ into a single command.
"""

import argparse
import logging
import sys
import tempfile
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd
import SimpleITK as sitk

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOBE_ROI_SUBSET = [
    "lung_upper_lobe_left",
    "lung_lower_lobe_left",
    "lung_upper_lobe_right",
    "lung_middle_lobe_right",
    "lung_lower_lobe_right",
]

# Mapping from lobe IDs (as output by TotalSegmentator, normalised to 10-14)
# to human-readable names.
LOBE_ID_TO_NAME = {
    10: "lung_upper_lobe_left",
    11: "lung_lower_lobe_left",
    12: "lung_upper_lobe_right",
    13: "lung_middle_lobe_right",
    14: "lung_lower_lobe_right",
}

NLOBES = 5

# DICOM tags used for metadata extraction
TAG_SERIES_DESCRIPTION = "0008|103e"
TAG_PIXEL_SPACING = "0028|0030"
TAG_SLICE_THICKNESS = "0018|0050"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DICOM utilities
# ---------------------------------------------------------------------------


def discover_series(dicom_dir: Path) -> dict[str, list[str]]:
    """Return a dict mapping series description → list of DICOM file paths.

    Recursively walks *dicom_dir* looking for valid DICOM series.
    """
    reader = sitk.ImageFileReader()
    series_map: dict[str, list[str]] = {}

    dicom_dir_str = str(dicom_dir)

    # Try top-level first, then walk sub-directories
    dirs_to_scan: list[str] = [dicom_dir_str]
    for p in sorted(dicom_dir.rglob("*")):
        if p.is_dir():
            dirs_to_scan.append(str(p))

    seen_series_uids: set[str] = set()

    for d in dirs_to_scan:
        series_uids = sitk.ImageSeriesReader.GetGDCMSeriesIDs(d)
        for uid in series_uids:
            if uid in seen_series_uids:
                continue
            seen_series_uids.add(uid)
            file_names = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(d, uid)
            if not file_names:
                continue
            # Read series description from the first slice
            try:
                reader.SetFileName(file_names[0])
                reader.LoadPrivateTagsOn()
                reader.ReadImageInformation()
                description = reader.GetMetaData(TAG_SERIES_DESCRIPTION).strip()
            except Exception:
                description = f"unknown_{uid[:8]}"
            series_map[description] = list(file_names)

    return series_map


def read_dicom_series(file_names: list[str]) -> sitk.Image:
    """Read a DICOM series given an ordered list of file paths."""
    reader = sitk.ImageSeriesReader()
    reader.SetFileNames(file_names)
    reader.MetaDataDictionaryArrayUpdateOn()
    reader.LoadPrivateTagsOn()
    image = reader.Execute()
    return image


def get_voxel_volume_mm3(dicom_file: str) -> float:
    """Compute the voxel volume in mm³ from DICOM metadata."""
    reader = sitk.ImageFileReader()
    reader.SetFileName(dicom_file)
    reader.LoadPrivateTagsOn()
    reader.ReadImageInformation()

    pixel_spacing = reader.GetMetaData(TAG_PIXEL_SPACING).split("\\")
    slice_thickness = reader.GetMetaData(TAG_SLICE_THICKNESS)

    voxel_vol = (
        float(pixel_spacing[0]) * float(pixel_spacing[1]) * float(slice_thickness)
    )
    return voxel_vol


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------


def run_totalsegmentator(nifti_path: Path, output_dir: Path, use_gpu: bool | None = None) -> Path:
    """Run TotalSegmentator on a NIfTI file and return path to lobe mask.

    Parameters
    ----------
    nifti_path : Path
        Input NIfTI file (.nii or .nii.gz).
    output_dir : Path
        Directory where TotalSegmentator will write its output.
    use_gpu : bool | None
        If None, auto-detect GPU availability.

    Returns
    -------
    Path
        Path to the combined lobe segmentation file (``lobes.nii``).
    """
    from totalsegmentator.python_api import totalsegmentator

    # Determine device
    if use_gpu is None:
        try:
            import torch
            use_gpu = torch.cuda.is_available()
        except ImportError:
            use_gpu = False

    logger.info("Running TotalSegmentator (GPU=%s) …", use_gpu)

    output_dir.mkdir(parents=True, exist_ok=True)

    # With ml=True, TotalSegmentator treats the output path as a file stem
    # and appends .nii — so output="dir/lobes" creates "dir/lobes.nii".
    # This matches the clippcair-analyse pattern in nifti2tseg.py.
    ts_output = output_dir / "lobes"

    totalsegmentator(
        input=nifti_path,
        output=ts_output,
        task="total",
        ml=True,
        roi_subset=LOBE_ROI_SUBSET,
    )

    # Look for the combined lobe mask file in several possible locations
    candidates = [
        output_dir / "lobes.nii",       # expected: ml=True appends .nii to output stem
        output_dir / "lobes.nii.gz",    # some versions use .nii.gz
        ts_output / "lobes.nii",        # fallback: file inside directory
        ts_output / "lobes.nii.gz",
    ]

    for lobes_file in candidates:
        if lobes_file.exists():
            logger.info("Found lobe mask at %s", lobes_file)
            return lobes_file

    # Last resort: look for individual per-lobe files (non-ml mode)
    # and combine them into a single multilabel mask
    individual_files = {}
    search_dirs = [output_dir, ts_output] if ts_output.is_dir() else [output_dir]
    for search_dir in search_dirs:
        for i, roi_name in enumerate(LOBE_ROI_SUBSET):
            for ext in [".nii.gz", ".nii"]:
                candidate = search_dir / f"{roi_name}{ext}"
                if candidate.exists():
                    individual_files[i] = candidate

    if individual_files:
        logger.info("Found %d individual lobe files, combining into multilabel mask…", len(individual_files))
        combined_mask = None
        for i, fpath in individual_files.items():
            lobe_data = nib.load(fpath).get_fdata()
            lobe_data = np.round(lobe_data).astype(int)
            if combined_mask is None:
                combined_mask = np.zeros_like(lobe_data, dtype=int)
            # Label: 1-5 (will be normalised to 10-14 later by compute_lobe_stats)
            combined_mask[lobe_data > 0] = i + 1

        combined_path = output_dir / "lobes_combined.nii.gz"
        ref_img = nib.load(next(iter(individual_files.values())))
        nib.save(nib.Nifti1Image(combined_mask, ref_img.affine, ref_img.header), combined_path)
        logger.info("Combined lobe mask saved to %s", combined_path)
        return combined_path

    # List what TotalSegmentator actually created for debugging
    all_files = []
    for d in [output_dir, ts_output] if ts_output.is_dir() else [output_dir]:
        all_files.extend(list(d.iterdir()))

    raise FileNotFoundError(
        f"TotalSegmentator did not produce a lobe mask. "
        f"Searched: {[str(c) for c in candidates]}. "
        f"Available files: {[str(f) for f in all_files]}"
    )


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def compute_lobe_stats(
    ct_data: np.ndarray,
    lobe_mask: np.ndarray,
    voxel_volume_mm3: float,
    threshold_hu: float,
) -> list[dict]:
    """Compute per-lobe voxel statistics.

    Parameters
    ----------
    ct_data : np.ndarray
        3-D array of CT Hounsfield Unit values.
    lobe_mask : np.ndarray
        3-D integer array of lobe labels (same shape as *ct_data*).
    voxel_volume_mm3 : float
        Volume of a single voxel in mm³.
    threshold_hu : float
        HU threshold below which voxels are counted.

    Returns
    -------
    list[dict]
        One dict per lobe with keys: lobe_name, lobe_id, nb_voxels,
        volume_mm3, nb_voxels_below_threshold, ratio_below_threshold,
        threshold_hu.
    """
    # Normalise lobe IDs: some TotalSegmentator versions output 1-5,
    # others 10-14.  We normalise to 10-14.
    lobe_mask = np.round(lobe_mask).astype(int)
    if lobe_mask.max() < 10:
        lobe_mask[lobe_mask != 0] += 9

    results = []
    for i in range(NLOBES):
        lobe_id = i + 10
        lobe_name = LOBE_ID_TO_NAME[lobe_id]

        mask = lobe_mask == lobe_id
        nb_voxels = int(mask.sum())

        if nb_voxels == 0:
            logger.warning("Lobe %s (id=%d) has 0 voxels.", lobe_name, lobe_id)
            results.append(
                {
                    "lobe_name": lobe_name,
                    "lobe_id": lobe_id,
                    "nb_voxels": 0,
                    "volume_mm3": 0.0,
                    "nb_voxels_below_threshold": 0,
                    "ratio_below_threshold": float("nan"),
                    "threshold_hu": threshold_hu,
                }
            )
            continue

        voxel_values = ct_data[mask]
        nb_below = int(np.sum(voxel_values < threshold_hu))
        ratio = nb_below / nb_voxels

        results.append(
            {
                "lobe_name": lobe_name,
                "lobe_id": lobe_id,
                "nb_voxels": nb_voxels,
                "volume_mm3": round(nb_voxels * voxel_volume_mm3, 4),
                "nb_voxels_below_threshold": nb_below,
                "ratio_below_threshold": round(ratio, 6),
                "threshold_hu": threshold_hu,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    dicom_dir: Path,
    output_csv: Path,
    threshold_hu: float = -910.0,
    series_filter: str | None = None,
    use_gpu: bool | None = None,
) -> None:
    """End-to-end pipeline: DICOM → segmentation → per-lobe CSV.

    Parameters
    ----------
    dicom_dir : Path
        Directory containing DICOM files (possibly nested).
    output_csv : Path
        Path to the output CSV file.
    threshold_hu : float
        Hounsfield Unit threshold (default -910).
    series_filter : str | None
        If specified, select the series whose description matches.
    use_gpu : bool | None
        Force GPU on/off.  None = auto-detect.
    """
    # ---- 1. Discover DICOM series ----------------------------------------
    logger.info("Scanning DICOM directory: %s", dicom_dir)
    series_map = discover_series(dicom_dir)

    if not series_map:
        logger.error("No DICOM series found in %s", dicom_dir)
        sys.exit(1)

    if len(series_map) == 1:
        chosen_desc = next(iter(series_map))
        logger.info("Single series found: '%s'", chosen_desc)
    elif series_filter:
        # Case-insensitive, whitespace-insensitive match
        norm = series_filter.lower().replace(" ", "")
        match = None
        for desc in series_map:
            if desc.lower().replace(" ", "") == norm:
                match = desc
                break
        if match is None:
            logger.error(
                "Series '%s' not found. Available series:\n  %s",
                series_filter,
                "\n  ".join(series_map.keys()),
            )
            sys.exit(1)
        chosen_desc = match
        logger.info("Selected series: '%s'", chosen_desc)
    else:
        logger.error(
            "Multiple series found. Use --series to select one, "
            "or --list-series to display them:\n  %s",
            "\n  ".join(series_map.keys()),
        )
        sys.exit(1)

    file_names = series_map[chosen_desc]

    # ---- 2. Read DICOM and convert to NIfTI (temp file) ------------------
    logger.info("Reading %d DICOM files …", len(file_names))
    image = read_dicom_series(file_names)
    voxel_volume = get_voxel_volume_mm3(file_names[0])
    logger.info("Voxel volume: %.4f mm³", voxel_volume)

    with tempfile.TemporaryDirectory(prefix="segment_lobes_") as tmpdir:
        tmpdir = Path(tmpdir)
        nifti_path = tmpdir / "ct.nii.gz"
        sitk.WriteImage(image, str(nifti_path))
        logger.info("Temporary NIfTI written to %s", nifti_path)

        # ---- 3. Run TotalSegmentator ------------------------------------
        ts_output_dir = tmpdir / "totalsegmentator"
        lobes_file = run_totalsegmentator(nifti_path, ts_output_dir, use_gpu=use_gpu)
        logger.info("Lobe mask: %s", lobes_file)

        # ---- 4. Compute per-lobe statistics ------------------------------
        ct_data = nib.load(str(nifti_path)).get_fdata()
        lobe_data = nib.load(str(lobes_file)).get_fdata()

        if ct_data.shape != lobe_data.shape:
            logger.error(
                "Shape mismatch: CT %s vs lobe mask %s",
                ct_data.shape,
                lobe_data.shape,
            )
            sys.exit(1)

        stats = compute_lobe_stats(ct_data, lobe_data, voxel_volume, threshold_hu)

    # ---- 5. Write CSV ----------------------------------------------------
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(stats)
    df.to_csv(output_csv, index=False)
    logger.info("Results written to %s", output_csv)
    print(df.to_string(index=False))


def list_series(dicom_dir: Path) -> None:
    """Print available DICOM series descriptions and exit."""
    series_map = discover_series(dicom_dir)
    if not series_map:
        print(f"No DICOM series found in {dicom_dir}")
        sys.exit(1)
    print(f"Found {len(series_map)} series in {dicom_dir}:\n")
    for desc, files in series_map.items():
        print(f"  • {desc}  ({len(files)} slices)")
    sys.exit(0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Segment pulmonary lobes from a DICOM lung CT and report "
            "per-lobe voxel counts and voxels below a HU threshold."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s -i /path/to/dicom\n"
            "  %(prog)s -i /path/to/dicom --list-series\n"
            "  %(prog)s -i /path/to/dicom -s 'parenchyme' -t -950\n"
            "  %(prog)s -i /path/to/dicom -o results.csv --no-gpu\n"
        ),
    )

    parser.add_argument(
        "-i", "--input",
        required=True,
        type=Path,
        help="Path to the DICOM directory (may contain nested sub-folders).",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("lobe_stats.csv"),
        help="Output CSV file path (default: lobe_stats.csv).",
    )
    parser.add_argument(
        "-t", "--threshold",
        type=float,
        default=-910.0,
        help="HU threshold for low-attenuation voxel counting (default: -910).",
    )
    parser.add_argument(
        "-s", "--series",
        type=str,
        default=None,
        help="Select a specific DICOM series by its description name.",
    )
    parser.add_argument(
        "--list-series",
        action="store_true",
        help="List available DICOM series in the input directory and exit.",
    )

    gpu_group = parser.add_mutually_exclusive_group()
    gpu_group.add_argument(
        "--gpu",
        dest="use_gpu",
        action="store_true",
        default=None,
        help="Force GPU usage for TotalSegmentator.",
    )
    gpu_group.add_argument(
        "--no-gpu",
        dest="use_gpu",
        action="store_false",
        help="Force CPU-only mode for TotalSegmentator.",
    )

    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    if not args.input.is_dir():
        logger.error("Input path does not exist or is not a directory: %s", args.input)
        sys.exit(1)

    if args.list_series:
        list_series(args.input)

    run_pipeline(
        dicom_dir=args.input,
        output_csv=args.output,
        threshold_hu=args.threshold,
        series_filter=args.series,
        use_gpu=args.use_gpu,
    )


if __name__ == "__main__":
    main()
