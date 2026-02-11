#!/usr/bin/env python3
"""
Build script for creating standalone executables using PyInstaller.

Usage:
    python build_executable.py
    
This will create:
- dist/SegmentLobes/ containing the executable bundle
- dist/SegmentLobes.exe (Windows) or dist/SegmentLobes (Linux/Mac)
"""

import sys
import subprocess
from pathlib import Path

def build():
    """Build the standalone executable using PyInstaller."""
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("ERROR: PyInstaller not installed.")
        print("Install it with: pip install pyinstaller")
        sys.exit(1)
    
    print("Building standalone executable...")
    print("This may take several minutes due to the large dependencies (PyTorch, TotalSegmentator).")
    print()
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--name=SegmentLobes",
        "--windowed",  # No console window (GUI only)
        "--onefile",   # Single executable file
        "--icon=NONE",
        "--add-data", f"segment_lobes.py{':' if sys.platform != 'win32' else ';'}.",
        "--hidden-import=nibabel",
        "--hidden-import=SimpleITK",
        "--hidden-import=totalsegmentator",
        "--hidden-import=torch",
        "--hidden-import=pandas",
        "--hidden-import=numpy",
        "--collect-all=totalsegmentator",
        "--collect-all=nnunetv2",
        "segment_lobes_gui.py",
    ]
    
    # Run PyInstaller
    try:
        subprocess.run(cmd, check=True)
        print("\n" + "="*60)
        print("✓ Build successful!")
        print("="*60)
        
        if sys.platform == "win32":
            exe_path = Path("dist/SegmentLobes.exe")
        else:
            exe_path = Path("dist/SegmentLobes")
        
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"\nExecutable: {exe_path.absolute()}")
            print(f"Size: {size_mb:.1f} MB")
            print("\nNOTE: The executable is large due to PyTorch and TotalSegmentator.")
            print("On first run, TotalSegmentator will download ~1.5 GB of model weights")
            print("to your home directory (~/.totalsegmentator/).")
        else:
            print(f"\nWARNING: Expected executable not found at {exe_path}")
            print("Check the dist/ folder for output.")
            
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Build failed with exit code {e.returncode}")
        print("Check the error messages above for details.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nBuild cancelled by user.")
        sys.exit(1)


if __name__ == "__main__":
    build()
