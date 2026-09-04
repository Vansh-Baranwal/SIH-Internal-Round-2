"""
Quick local smoke test for the new M1 files (coordinates.py, loader.py, overlap.py).
Run this from your repo root AFTER copying the three files into
lunar_hazard_mapper/m1_data/, with your venv active:

    python smoke_test_m1.py

It does NOT need the corner-coordinate parsing to be fixed yet -- it only
exercises the parts that are already known-correct (ENVI header parsing,
TMC/OHRC GeoTIFF loading, bbox-based overlap math). It WILL show you exactly
what parse_iirs_corners() finds/fails on, which is what we need to finish
loader.py's IIRS georeferencing.
"""
import sys
from pathlib import Path

sys.path.insert(0, ".")

from lunar_hazard_mapper.m1_data import loader, coordinates

IIRS_CUBE = Path("data/real_samples/iirs_raw/data/raw/20200203/ch2_iir_nri_20200203T1845559180_d_img_m65.qub")
IIRS_XML = IIRS_CUBE.with_suffix(".xml")

print("=== 1. ENVI header parse + cube open (bands/lines/samples sanity check) ===")
header = loader._parse_envi_header(IIRS_CUBE.with_suffix(".hdr"))
print(header)
assert header["bands"] == 256 and header["samples"] == 250 and header["lines"] == 10804, "header values don't match what we saw earlier -- check the file"
print("OK: header matches expected 256 bands / 250 samples / 10804 lines\n")

print("=== 2. Load a 3-band preview cube via rasterio ENVI driver ===")
cube = loader.load_iirs_cube(IIRS_CUBE, bands=[1, 128, 256])
print({k: v for k, v in cube.items() if k != "array"})
print("array shape:", cube["array"].shape, "dtype:", cube["array"].dtype)
assert cube["array"].shape == (3, 10804, 250), f"unexpected array shape: {cube['array'].shape}"
print("OK: cube reads correctly via GDAL's ENVI driver\n")

print("=== 3. IIRS corner-coordinate parse (this is the piece still being finalized) ===")
try:
    corners = loader.parse_iirs_corners(IIRS_XML)
    print("Corners found:", corners)
except ValueError as e:
    print("EXPECTED (for now) -- parser needs the real tag names:")
    print(str(e)[:2000])

print("\n=== 4. coordinates.py polygon math sanity check (synthetic data, no file needed) ===")
a = {"bounds": {"west": 0, "south": 0, "east": 10, "north": 10}, "crs": None}
b = {"bounds": {"west": 5, "south": 5, "east": 15, "north": 15}, "crs": None}
frac = coordinates.real_intersection_fraction(a, b)
print("Intersection fraction of two 50%-overlapping boxes (expect ~0.25):", frac)
assert abs(frac - 0.25) < 1e-6
print("OK: polygon intersection math is correct\n")

print("ALL SMOKE TESTS PASSED (except IIRS corner parsing, expected until we confirm tag names)")
