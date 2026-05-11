#!/usr/bin/env python
"""
RSI preprocessing + processing for pilot data.
- Creates brain mask from b0 using dipy's median_otsu (no FSL needed)
- Runs RSI decomposition via RSIproc_1_0_8.py
"""

import os
import sys
import subprocess
import numpy as np
import nibabel as nib
from pathlib import Path
from dipy.segment.mask import median_otsu

PILOT_DIR = Path("/mnt/fac/CX500007_DS1/bardou/rsi-wma/pilot_data")
RSI_SCRIPT = Path("/mnt/fac/CX500007_DS1/bardou/rsi-wma/rsi/RSIproc_1_0_8.py")
OUTPUT_DIR = Path("/mnt/fac/CX500007_DS1/bardou/rsi-wma/rsi_output")

sys.path.insert(0, str(RSI_SCRIPT.parent))


def extract_b0_and_mask(dwi_path, bval_path, out_dir):
    """Extract mean b0 and create brain mask with median_otsu."""
    img = nib.load(dwi_path)
    data = img.get_fdata()
    bvals = np.genfromtxt(bval_path)

    b0_idx = np.where(bvals <= 10)[0]
    if len(b0_idx) == 0:
        raise ValueError(f"No b0 volumes found in {bval_path}")

    b0_mean = data[:, :, :, b0_idx].mean(axis=3)

    b0_masked, mask = median_otsu(b0_mean, median_radius=2, numpass=1)

    mask = mask.astype(np.float32)
    mask_img = nib.Nifti1Image(mask, img.affine, img.header)
    mask_img.header.set_data_dtype(np.float32)
    mask_path = out_dir / "b0_brain_mask.nii.gz"
    nib.save(mask_img, str(mask_path))

    b0_img = nib.Nifti1Image(b0_mean.astype(np.float32), img.affine, img.header)
    nib.save(b0_img, str(out_dir / "b0_mean.nii.gz"))

    print(f"  Mask created: {mask.sum():.0f} voxels, shape {mask.shape}")
    return mask_path


def run_rsi(dwi_path, mask_path, bval_path, bvec_path, out_dir):
    """Run RSI processing in the output directory."""
    cmd = [
        sys.executable, str(RSI_SCRIPT),
        str(dwi_path), str(mask_path), str(bval_path), str(bvec_path)
    ]
    result = subprocess.run(cmd, cwd=str(out_dir), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr[:500]}")
        return False
    return True


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    subjects = []
    for group in ["WMA", "nonWMA"]:
        group_dir = PILOT_DIR / group
        for sub_dir in sorted(group_dir.iterdir()):
            if sub_dir.is_dir() and sub_dir.name.startswith("sub-"):
                subjects.append((group, sub_dir))

    print(f"Found {len(subjects)} subjects\n")

    for group, sub_dir in subjects:
        subj = sub_dir.name
        dwi_dir = sub_dir / "dwi"

        # Use run-01 only
        dwi_files = sorted(dwi_dir.glob("*_run-01_dwi.nii.gz"))
        if not dwi_files:
            print(f"SKIP {subj}: no run-01 dwi found")
            continue

        dwi_path = dwi_files[0]
        bval_path = dwi_path.with_suffix("").with_suffix(".bval")
        bvec_path = dwi_path.with_suffix("").with_suffix(".bvec")

        if not bval_path.exists() or not bvec_path.exists():
            print(f"SKIP {subj}: missing bval/bvec")
            continue

        out_dir = OUTPUT_DIR / subj
        out_dir.mkdir(parents=True, exist_ok=True)

        # Check if already processed
        if (out_dir / "n0s1.nii.gz").exists():
            print(f"SKIP {subj}: already processed")
            continue

        print(f"Processing {subj} ({group})...")

        # Step 1: Brain mask
        print("  Creating brain mask...")
        mask_path = extract_b0_and_mask(dwi_path, bval_path, out_dir)

        # Step 2: RSI
        print("  Running RSI decomposition...")
        success = run_rsi(dwi_path, mask_path, bval_path, bvec_path, out_dir)
        if success:
            print(f"  Done: {subj}")
        else:
            print(f"  FAILED: {subj}")

    print("\nAll done.")


if __name__ == "__main__":
    main()
