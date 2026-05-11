#!/usr/bin/env python
"""
RSI pilot pipeline:
  1. Extract mean b0 from DWI
  2. Skull-strip b0 with SynthStrip (apptainer)
  3. Run pyrsi (apptainer) with brain mask
"""

import os
import subprocess
import numpy as np
import nibabel as nib
from pathlib import Path

PILOT_DIR = Path("/mnt/fac/CX500007_DS1/bardou/rsi-wma/pilot_data")
OUTPUT_DIR = Path("/mnt/fac/CX500007_DS1/bardou/rsi-wma/rsi_output")

SYNTHSTRIP_SIF = "/mnt/fac/CX500002_DS1/lab-utils/synthstrip_v1.8.sif"
PYRSI_SIF = "/mnt/fac/CX500002_DS1/lab-utils/pyrsi.sif"

BIND_PATHS = "/mnt/fac"


def extract_b0(dwi_path, bval_path, out_dir):
    """Extract mean b0 volume from DWI."""
    b0_path = out_dir / "b0_mean.nii.gz"
    if b0_path.exists():
        print("  b0 already extracted")
        return b0_path

    img = nib.load(dwi_path)
    data = img.get_fdata()
    bvals = np.genfromtxt(bval_path)

    b0_idx = np.where(bvals <= 10)[0]
    if len(b0_idx) == 0:
        raise ValueError(f"No b0 volumes found in {bval_path}")

    b0_mean = data[:, :, :, b0_idx].mean(axis=3).astype(np.float32)
    nib.save(nib.Nifti1Image(b0_mean, img.affine, img.header), str(b0_path))
    print(f"  b0 extracted ({len(b0_idx)} volumes averaged)")
    return b0_path


def run_synthstrip(b0_path, out_dir):
    """Skull-strip b0 with SynthStrip container."""
    mask_path = out_dir / "brain_mask.nii.gz"
    if mask_path.exists():
        print("  Brain mask already exists")
        return mask_path

    cmd = [
        "apptainer", "exec", "--bind", BIND_PATHS,
        SYNTHSTRIP_SIF,
        "mri_synthstrip",
        "-i", str(b0_path),
        "-m", str(mask_path),
    ]
    print(f"  CMD: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  SynthStrip STDOUT: {result.stdout[:500]}")
        print(f"  SynthStrip STDERR: {result.stderr[:500]}")
        print(f"  SynthStrip RC: {result.returncode}")
        return None

    mask = nib.load(str(mask_path)).get_fdata()
    print(f"  Brain mask: {mask.sum():.0f} voxels")
    return mask_path


def run_pyrsi(dwi_path, bval_path, bvec_path, mask_path, out_dir):
    """Run pyrsi container."""
    rsi_out = out_dir / "rsi"
    rsi_out.mkdir(exist_ok=True)

    existing = list(rsi_out.glob("*_rni.nii.gz")) + list(rsi_out.glob("RNI.nii.gz"))
    if existing:
        print("  RSI already computed")
        return True

    cmd = [
        "apptainer", "run", "--bind", BIND_PATHS,
        PYRSI_SIF,
        str(dwi_path), str(bval_path), str(bvec_path),
        "-o", str(rsi_out),
        "--mask", str(mask_path),
        "--measures", "RNI", "RND", "RNT", "FNI",
        "-v",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  pyrsi ERROR: {result.stderr[:500]}")
        return False

    print(f"  RSI done → {rsi_out}")
    return True


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    subjects = []
    for group in ["WMA", "nonWMA"]:
        group_dir = PILOT_DIR / group
        if not group_dir.exists():
            continue
        for sub_dir in sorted(group_dir.iterdir()):
            if sub_dir.is_dir() and sub_dir.name.startswith("sub-"):
                subjects.append((group, sub_dir))

    print(f"Found {len(subjects)} subjects\n")

    for group, sub_dir in subjects:
        subj = sub_dir.name
        dwi_dir = sub_dir / "dwi"

        dwi_files = sorted(dwi_dir.glob("*_run-01_dwi.nii.gz"))
        if not dwi_files:
            print(f"SKIP {subj}: no run-01 dwi")
            continue

        dwi_path = dwi_files[0]
        bval_path = dwi_path.with_suffix("").with_suffix(".bval")
        bvec_path = dwi_path.with_suffix("").with_suffix(".bvec")

        if not bval_path.exists() or not bvec_path.exists():
            print(f"SKIP {subj}: missing bval/bvec")
            continue

        out_dir = OUTPUT_DIR / subj
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"[{group}] {subj}")

        # Step 1: extract b0
        b0_path = extract_b0(dwi_path, bval_path, out_dir)

        # Step 2: skull-strip with synthstrip
        mask_path = run_synthstrip(b0_path, out_dir)
        if mask_path is None:
            print(f"  FAILED skull-strip, skipping")
            continue

        # Step 3: RSI with pyrsi
        success = run_pyrsi(dwi_path, bval_path, bvec_path, mask_path, out_dir)
        if not success:
            print(f"  FAILED RSI")

    print("\nAll done.")


if __name__ == "__main__":
    main()
