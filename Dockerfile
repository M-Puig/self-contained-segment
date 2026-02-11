# --------------------------------------------------------------------------
# CPU-only Dockerfile for segment_lobes
# --------------------------------------------------------------------------
FROM python:3.10-slim

# System dependencies required by SimpleITK, nibabel, and TotalSegmentator
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        ffmpeg \
        wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (heavy – cached in its own layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install CPU-only PyTorch to keep image size manageable.
# TotalSegmentator pulls torch as a dep, but we override with CPU wheel.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY segment_lobes.py .

# TotalSegmentator downloads models on first run (~1.5 GB).
# Mount a volume to /root/.totalsegmentator to persist them across runs.
VOLUME ["/root/.totalsegmentator"]

ENTRYPOINT ["python", "segment_lobes.py"]
