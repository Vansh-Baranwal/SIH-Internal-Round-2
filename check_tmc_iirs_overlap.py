# check_tmc_iirs_overlap.py
import sys
sys.path.insert(0, "src")
from pathlib import Path
# from lunar_hazard_mapper.m1_data.loader import load_tmc_tile, parse_isda_corners
from lunar_hazard_mapper.m1_data import coordinates
from lunar_hazard_mapper.m1_data.loader import load_tmc_tile, parse_iirs_corners
tmc = load_tmc_tile(Path("data/real_samples/tmc_ortho2/data/derived/20250707/ch2_tmc_ndn_20250707T1853051045_d_oth_d18.tif"))
iirs_corners = parse_iirs_corners(Path("data/real_samples/iirs_raw/data/raw/20200203/ch2_iir_nri_20200203T1845559180_d_img_m65.xml"))

print("TMC bounds:", tmc["bounds"])
print("TMC crs:", tmc["crs"][:80] if tmc["crs"] else None)
print("IIRS corners:", iirs_corners)

record_a = {"bounds": tmc["bounds"], "crs": tmc["crs"]}
record_b = {"corners": iirs_corners, "crs": None}

frac = coordinates.real_intersection_fraction(record_a, record_b)
print("Real TMC<->IIRS overlap fraction:", frac)