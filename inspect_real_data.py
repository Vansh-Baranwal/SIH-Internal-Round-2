"""
Reconnaissance script: figure out what we actually have on disk, and whether
any of it geographically overlaps the IIRS scene, before running the real
verify_real_overlap() test. Run from repo root with your venv active:

    python inspect_real_data.py

This does NOT modify anything -- read-only inspection.
"""
import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "src")  # repo uses src/lunar_hazard_mapper per earlier traceback

import rasterio

# IIRS scene footprint, already confirmed:
IIRS_LON_RANGE = (24.556687, 25.176954)
IIRS_LAT_RANGE = (-30.375724, -0.526650)

FILES_TO_CHECK = {
    "OHRC (ohrc_raw2, via .xml label -- PDS4 driver)": "data/real_samples/ohrc_raw2/data/calibrated/20210401/ch2_ohr_ncp_20210401T2357376656_d_img_hw1.xml",
    "OHRC (ohrc_raw2, via .img directly, for comparison)": "data/real_samples/ohrc_raw2/data/calibrated/20210401/ch2_ohr_ncp_20210401T2357376656_d_img_hw1.img",
    "TMC (tmc_ortho2, GeoTIFF)": "data/real_samples/tmc_ortho2/data/derived/20250707/ch2_tmc_ndn_20250707T1853051045_d_oth_d18.tif",
    "nac_a.tif (mystery file -- possibly LRO NAC)": "data/real_samples/nac_a.tif",
    "nac_b.tif (mystery file -- possibly LRO NAC)": "data/real_samples/nac_b.tif",
}


def describe(label: str, path_str: str) -> None:
    path = Path(path_str)
    print(f"\n--- {label} ---")
    print(f"path: {path}")
    if not path.exists():
        print("  !! FILE NOT FOUND -- check the path")
        return
    try:
        with rasterio.open(path) as ds:
            print(f"  driver: {ds.driver}")
            print(f"  size: {ds.width} x {ds.height}, bands: {ds.count}, dtype: {ds.dtypes[0]}")
            print(f"  crs: {ds.crs}")
            if ds.crs is not None and ds.transform is not None and not ds.transform.is_identity:
                b = ds.bounds
                print(f"  bounds (in file's own CRS units): west={b.left}, south={b.bottom}, east={b.right}, north={b.top}")
                # Only meaningful to compare directly against IIRS lon/lat if this
                # is already a geographic (lat/lon degrees) CRS -- print a flag
                # rather than silently assuming.
                is_geographic = ds.crs.is_geographic if ds.crs else False
                print(f"  is_geographic (lat/lon degrees, directly comparable to IIRS range): {is_geographic}")
                if is_geographic:
                    lon_overlap = not (b.right < IIRS_LON_RANGE[0] or b.left > IIRS_LON_RANGE[1])
                    lat_overlap = not (b.top < IIRS_LAT_RANGE[0] or b.bottom > IIRS_LAT_RANGE[1])
                    print(f"  POSSIBLE OVERLAP WITH IIRS SCENE: {lon_overlap and lat_overlap}")
            else:
                print("  NOT georeferenced (identity transform / no CRS) -- would need corner parsing from XML like IIRS")
    except Exception as e:
        print(f"  !! could not open with rasterio: {type(e).__name__}: {e}")


if __name__ == "__main__":
    for label, path_str in FILES_TO_CHECK.items():
        describe(label, path_str)
    print("\n\nDone. Paste this full output back.")
