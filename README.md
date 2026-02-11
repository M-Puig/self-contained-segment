# Lung CT Lobe Segmentation Tool

Self-contained, OS-independent tool that segments pulmonary lobes from DICOM
lung CT data using [TotalSegmentator](https://github.com/wasserth/TotalSegmentator)
and reports per-lobe voxel counts and voxels below a configurable Hounsfield
Unit (HU) threshold.

**Two deployment options:**
1. **🐳 Docker container** (recommended for technical users) — no Python environment setup
2. **🖥️ Standalone GUI executable** (easiest for end users) — double-click to run

## Prerequisites

### For Docker
- [Docker](https://docs.docker.com/get-docker/) (v20+ recommended)
- For GPU acceleration: [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

### For Standalone Executable
- No prerequisites! Just download the `.exe` (Windows) or executable (Linux/Mac) and run it

---

## 🚀 Quick Start: GUI Standalone Executable (For End Users)

### Option 1: Download pre-built executable (easiest)

Go to the [Releases page](../../releases) and download the archive for your OS:
- **Windows**: `SegmentLobes-Windows.zip` — Extract and run `SegmentLobes.exe`
- **Linux**: `SegmentLobes-Linux.tar.gz` — Extract and run `./SegmentLobes`
- **macOS**: `SegmentLobes-macOS.zip` — Extract and run `SegmentLobes`

*(Releases are automatically built via GitHub Actions when new versions are tagged)*

### Option 2: Build it yourself (Linux/Mac/Windows)

**⚠️ Warning**: Building requires ~10 GB of free disk space and takes 10-30 minutes.

1. **Install Python 3.10+** (if not already installed)

2. **Clone or download this repository**
   ```bash
   cd self-contained-segment
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements-gui.txt
   ```

4. **Build the standalone executable**
   ```bash
   python build_executable.py
   ```
   
   This takes **5-10 minutes** and creates a directory bundle in `dist/SegmentLobes/`
   containing the executable and all dependencies (~500 MB - 1 GB).

5. **Run the GUI**
   - **Windows**: Run `dist/SegmentLobes/SegmentLobes.exe`
   - **Linux/Mac**: Run `./dist/SegmentLobes/SegmentLobes`

### Using the GUI

1. **Browse** to select your DICOM folder
2. **Select** a series from the dropdown (auto-detected)
3. **Set** the HU threshold (default: -910)
4. **Choose** where to save the output CSV
5. **Click "Run Segmentation"**
6. Wait while the tool processes (progress shown in the log)
7. Results are saved to your chosen CSV file

**Note**: On first run, TotalSegmentator downloads ~1.5 GB of model weights to 
`~/.totalsegmentator/`. This is a one-time download.

---

## 🐳 Quick Start: Docker (For Technical Users)

### 1. Build the image

```bash
# CPU-only (smaller image)
docker build -t segment-lobes .

# GPU-enabled (requires NVIDIA base image)
docker build -f Dockerfile.gpu -t segment-lobes-gpu .
```

### 2. List available DICOM series

If your DICOM folder contains multiple series, list them first:

```bash
docker run --rm \
  -v /path/to/dicom:/data/input:ro \
  segment-lobes \
  --input /data/input --list-series
```

### 3. Run segmentation

```bash
# Single series (auto-detected)
docker run --rm \
  -v /path/to/dicom:/data/input:ro \
  -v /path/to/output:/data/output \
  -v tseg-models:/root/.totalsegmentator \
  segment-lobes \
  --input /data/input \
  --output /data/output/lobe_stats.csv

# Multi-series: select by name
docker run --rm \
  -v /path/to/dicom:/data/input:ro \
  -v /path/to/output:/data/output \
  -v tseg-models:/root/.totalsegmentator \
  segment-lobes \
  --input /data/input \
  --output /data/output/lobe_stats.csv \
  --series "parenchyme"

# Custom HU threshold (default: -910)
docker run --rm \
  -v /path/to/dicom:/data/input:ro \
  -v /path/to/output:/data/output \
  -v tseg-models:/root/.totalsegmentator \
  segment-lobes \
  --input /data/input \
  --output /data/output/lobe_stats.csv \
  --threshold -950
```

### 4. GPU variant

```bash
docker run --rm --gpus 1 \
  -v /path/to/dicom:/data/input:ro \
  -v /path/to/output:/data/output \
  -v tseg-models:/root/.totalsegmentator \
  segment-lobes-gpu \
  --input /data/input \
  --output /data/output/lobe_stats.csv
```

### Using docker compose

Environment variables `DICOM_DIR` and `OUTPUT_DIR` control the host paths:

```bash
# List series
DICOM_DIR=/path/to/dicom docker compose run --rm segment --input /data/input --list-series

# Run segmentation (CPU)
DICOM_DIR=/path/to/dicom OUTPUT_DIR=/path/to/output \
  docker compose run --rm segment \
  --input /data/input --output /data/output/lobe_stats.csv --threshold -910

# Run segmentation (GPU)
DICOM_DIR=/path/to/dicom OUTPUT_DIR=/path/to/output \
  docker compose run --rm segment-gpu \
  --input /data/input --output /data/output/lobe_stats.csv
```

## CLI reference

```
usage: segment_lobes.py [-h] -i INPUT [-o OUTPUT] [-t THRESHOLD] [-s SERIES]
                        [--list-series] [--gpu | --no-gpu]

Segment pulmonary lobes from a DICOM lung CT and report per-lobe voxel counts
and voxels below a HU threshold.

options:
  -i, --input         Path to the DICOM directory (may contain nested sub-folders)
  -o, --output        Output CSV file path (default: lobe_stats.csv)
  -t, --threshold     HU threshold for low-attenuation voxel counting (default: -910)
  -s, --series        Select a specific DICOM series by its description name
  --list-series       List available DICOM series in the input directory and exit
  --gpu               Force GPU usage for TotalSegmentator
  --no-gpu            Force CPU-only mode for TotalSegmentator
```

## Output format

The output CSV contains one row per pulmonary lobe:

| Column                      | Description                                       |
| --------------------------- | ------------------------------------------------- |
| `lobe_name`                 | Anatomical name of the lobe                       |
| `lobe_id`                   | Numeric lobe ID (10–14)                           |
| `nb_voxels`                 | Total number of voxels in the lobe                |
| `volume_mm3`                | Total volume in mm³                               |
| `nb_voxels_below_threshold` | Number of voxels with HU < threshold              |
| `ratio_below_threshold`     | Fraction of voxels below threshold                |
| `threshold_hu`              | The HU threshold used                             |

### Lobe IDs

| ID | Lobe                        |
| -- | --------------------------- |
| 10 | `lung_upper_lobe_left`      |
| 11 | `lung_lower_lobe_left`      |
| 12 | `lung_upper_lobe_right`     |
| 13 | `lung_middle_lobe_right`    |
| 14 | `lung_lower_lobe_right`     |

## Notes

- **First run**: TotalSegmentator downloads ~1.5 GB of model weights. Mount a
  named Docker volume (`tseg-models`) to `/root/.totalsegmentator` to cache
  them across runs.
- **Threshold**: The default of **-910 HU** is a standard threshold for
  emphysema detection. Use `-950` for stricter low-attenuation area
  quantification.
- The tool uses the same lobe segmentation approach as the
  [clippcair-analyse](../clippcair-analyse/) pipeline scripts.

## Project structure

```
self-contained-segment/
├── segment_lobes.py            # Core CLI script (all logic in one file)
├── segment_lobes_gui.py        # GUI wrapper using tkinter
├── build_executable.py         # PyInstaller build script
├── requirements.txt            # Python dependencies (for Docker)
├── requirements-gui.txt        # Python dependencies (for GUI + executable)
├── Dockerfile                  # CPU-only container
├── Dockerfile.gpu              # GPU-enabled container (NVIDIA CUDA)
├── docker-compose.yml          # Simplified orchestration
├── .github/workflows/
│   └── build-executables.yml  # GitHub Actions workflow for multi-platform builds
├── .gitignore                  # Git ignore patterns
└── README.md                   # This file
```

## Comparison: Docker vs. Standalone Executable

| Feature                    | Docker                    | Standalone Executable     |
| -------------------------- | ------------------------- | ------------------------- |
| **Ease of use**            | Requires command line     | Double-click GUI          |
| **Prerequisites**          | Docker daemon             | None                      |
| **Build complexity**       | Simple (5-15 min)         | Moderate (10-30 min, ~10 GB) |
| **OS portability**         | One image for all         | Separate build per OS     |
| **File size**              | 3+ GB (image)             | 2-3 GB bundle (per OS)    |
| **Distribution**           | Docker Hub / tar file     | Zip/tar.gz bundle         |
| **First run setup**        | Model download (~1.5 GB)  | Model download (~1.5 GB)  |
| **GPU support**            | Easy with nvidia runtime  | Requires CUDA on host     |
| **Best for**               | Servers, reproducibility, **recommended for most users** | End users who can't install Docker |

## Building For Multiple Platforms (Developers)

### ⚠️ Important Notes on PyInstaller Builds

**Disk Space Requirements:** Building standalone executables with PyInstaller for TotalSegmentator + PyTorch requires:
- ~3-4 GB for installed dependencies (PyTorch, TotalSegmentator, etc.)
- ~2-3 GB for PyInstaller build process (temporary files)
- ~2-3 GB for final bundle

**Total: ~8-10 GB free space needed**

**GitHub Actions free runners have ~14GB free space**, but long builds can accumulate logs/caches. If builds fail with "No space left on device":

1. **Use the cleanup steps** already in the workflow
2. **Build locally** on machines with adequate storage (recommended for first-time setup)
3. **Consider Docker instead** for easier distribution

### Automated builds with GitHub Actions

The repository includes a GitHub Actions workflow that automatically builds executables for Windows, Linux, and macOS.

**To trigger a build:**

```bash
# Method 1: Create a version tag (recommended for releases)
git tag v1.0.0
git push origin v1.0.0

# Method 2: Manual trigger via GitHub web interface
# Go to Actions → Build Executables → Run workflow
```

**Download built executables:**
- Go to the "Actions" tab in GitHub
- Click on the latest successful workflow run
- Download artifacts: `SegmentLobes-windows-latest.zip`, `SegmentLobes-ubuntu-latest.tar.gz`, `SegmentLobes-macos-latest.zip`

**Publishing releases:**
- When you push a tag (e.g., `v1.0.0`), the workflow automatically creates a GitHub Release
- All three platform bundles are attached to the release as zip/tar.gz files
- Users can download from the Releases page and extract to run
