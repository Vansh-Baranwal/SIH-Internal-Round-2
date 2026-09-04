"""Read-only check: does OHRC's PDS4 label use the same corner tags as IIRS?"""
import sys
from pathlib import Path
sys.path.insert(0, "src")

from lunar_hazard_mapper.m1_data.loader import parse_iirs_corners

OHRC_XML = Path("data/real_samples/ohrc_raw2/data/calibrated/20210401/ch2_ohr_ncp_20210401T2357376656_d_img_hw1.xml")

try:
    print("SUCCESS — same tag schema as IIRS:", parse_iirs_corners(OHRC_XML))
except ValueError as e:
    print("Different schema — falling back to geometry CSV. Error was:")
    print(str(e)[:1500])

geom_csv = Path("data/real_samples/ohrc_raw2/geometry/calibrated/20210401/ch2_ohr_ncp_20210401T2357376656_g_grd_hw1.csv")
if geom_csv.exists():
    import csv
    with geom_csv.open() as f:
        reader = csv.reader(f)
        header = next(reader)
        first_row = next(reader, None)
    print("\nGeometry CSV columns:", header)
    print("First row:", first_row)