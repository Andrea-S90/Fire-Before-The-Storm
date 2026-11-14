#!/usr/bin/env python
"""Print the HDF5 tree of one GCOV file (first thing to run after the first download).

  python steps/inspect_gcov.py data/raw/nisar/NISAR_L2_PR_GCOV_....h5

If the grid group, coordinate or projection names differ from what ashwatch/nisar.py expects
(.../grids/frequencyA/{HHHH,HVHV,xCoordinates,yCoordinates,projection}), adjust nisar.py.
"""
import sys
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ashwatch.nisar import read_gcov  # noqa: E402


def main(fn):
    with h5py.File(fn, "r") as f:
        def show(name, obj):
            if "frequency" in name or name.count("/") <= 3:
                if isinstance(obj, h5py.Dataset):
                    print(f"{name:80s} {obj.shape} {obj.dtype} {dict(list(obj.attrs.items())[:4])}")
                else:
                    print(name + "/")
        f.visititems(show)
    g = read_gcov(fn)
    print("\nread_gcov ->", g["crs"], g["transform"])
    for p, a in g["pols"].items():
        print(f"  {p}: {a.shape}, median {np.nanmedian(a):.4f} (linear), {10*np.log10(np.nanmedian(a)):.1f} dB")


if __name__ == "__main__":
    main(sys.argv[1])
