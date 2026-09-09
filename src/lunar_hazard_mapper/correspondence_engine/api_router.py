"""
Correspondence Engine — API integration router.

Their existing app (src/lunar_hazard_mapper/api/main.py) is a SINGLE FastAPI
instance with plain @app.get/@app.post routes — not multiple apps. This file
replaces the standalone `api/main.py` from the original m2_engine.zip package
(the one with `app = FastAPI(...)`) so it plugs into their existing app as an
APIRouter instead of colliding with a second FastAPI instance.

DO NOT copy the original api/main.py from m2_engine.zip into this repo.
Use THIS file instead, placed at:
  src/lunar_hazard_mapper/correspondence_engine/api_router.py
"""
from __future__ import annotations
import os
import shutil
import uuid
import json
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse

def extract_metadata(filepath: str):
    import os
    if not str(filepath).lower().endswith(('.tif', '.tiff')):
        return None
    try:
        import rasterio
        with rasterio.open(filepath) as dataset:
            tags = dataset.tags()
            # Try some common tag names for solar angles
            az = None
            el = None
            for key, val in tags.items():
                kl = key.lower()
                if 'azimuth' in kl and 'sun' in kl:
                    try: az = float(val)
                    except: pass
                elif 'elevation' in kl and 'sun' in kl:
                    try: el = float(val)
                    except: pass
            
            if az is not None or el is not None:
                return {"azimuth": az, "elevation": el}
    except:
        pass
    return None


from lunar_hazard_mapper.correspondence_engine.registration.pipeline import run_pipeline, MATCHERS

router = APIRouter(prefix="/api/v1/correspondence", tags=["correspondence-engine"])

# Reuses the SAME base-dir pattern as their existing api/main.py (BASE_DIR is
# 4 parents up from this file, matching their convention exactly)
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
JOBS_DIR = BASE_DIR / "data" / "correspondence_jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/register")
async def register(
    source: UploadFile = File(...),
    reference: UploadFile = File(...),
    matcher: str = Form("sift"),
    geo_model: str = Form("affine"),
    illumination_variant: bool = Form(False),
    sun_azimuth: float = Form(135.0),
    sun_elevation: float = Form(45.0),
):
    if matcher not in MATCHERS:
        return JSONResponse(status_code=400, content={"error": f"unknown matcher: {matcher}"})

    job_id = str(uuid.uuid4())[:8]
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    source_path = job_dir / ("source" + os.path.splitext(source.filename)[-1])
    reference_path = job_dir / ("reference" + os.path.splitext(reference.filename)[-1])
    with open(source_path, "wb") as f:
        shutil.copyfileobj(source.file, f)
    with open(reference_path, "wb") as f:
        shutil.copyfileobj(reference.file, f)

    try:
        print(f"Running pipeline with illumination_variant={illumination_variant}, azimuth={sun_azimuth}, elevation={sun_elevation}")
        metrics = run_pipeline(str(source_path), str(reference_path), str(job_dir),
                                matcher=matcher, geo_model=geo_model,
                                apply_illumination_invariant=illumination_variant,
                                sun_azimuth=sun_azimuth)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    if metrics is None:
        return JSONResponse(status_code=422, content={"error": "insufficient matches found"})

    import base64
    
    warped_b64 = None
    vis_b64 = None
    
    try:
        with open(job_dir / "warped_source.png", "rb") as f:
            warped_b64 = base64.b64encode(f.read()).decode("utf-8")
    except: pass
    
    try:
        with open(job_dir / "match_visualization.png", "rb") as f:
            vis_b64 = base64.b64encode(f.read()).decode("utf-8")
    except: pass

    matches_data = []
    try:
        with open(job_dir / "matches.json", "r") as f:
            jdata = json.load(f)
            matches_data = jdata.get("matches", [])
    except:
        pass

    return {
        "job_id": job_id,
        "metrics": metrics.to_dict(),
        "warped_path": str(job_dir / "warped_source.png"),
        "visualization_path": str(job_dir / "match_visualization.png"),
        "warped_b64": warped_b64,
        "vis_b64": vis_b64,
        "matches_csv_path": str(job_dir / "matches.csv"),
        "matches_json_path": str(job_dir / "matches.json"),
        "matches": matches_data,
        "source_metadata": extract_metadata(str(source_path)),
        "reference_metadata": extract_metadata(str(reference_path)),
    }


@router.get("/metrics/{job_id}")
async def get_metrics(job_id: str):
    matches_json_path = JOBS_DIR / job_id / "matches.json"
    if not matches_json_path.exists():
        return JSONResponse(status_code=404, content={"error": "job not found"})
    with open(matches_json_path) as f:
        data = json.load(f)
    return data["metrics"]
