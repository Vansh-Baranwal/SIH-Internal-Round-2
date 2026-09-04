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
from fastapi.responses import FileResponse, JSONResponse

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
        metrics = run_pipeline(str(source_path), str(reference_path), str(job_dir),
                                matcher=matcher, geo_model=geo_model)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    if metrics is None:
        return JSONResponse(status_code=422, content={"error": "insufficient matches found"})

    matches_path = job_dir / "matches.json"
    with open(matches_path) as f:
        matches = json.load(f).get("matches", [])

    return {
        "job_id": job_id,
        "metrics": metrics.to_dict(),
        "matches": matches,
        "warped_url": f"/api/v1/correspondence/jobs/{job_id}/warped_source.png",
        "visualization_path": str(job_dir / "match_visualization.png"),
        "matches_csv_path": str(job_dir / "matches.csv"),
        "matches_json_path": str(job_dir / "matches.json"),
    }


@router.get("/jobs/{job_id}/{filename}")
async def get_job_file(job_id: str, filename: str):
    if filename not in {"warped_source.png", "match_visualization.png"}:
        return JSONResponse(status_code=404, content={"error": "file not found"})
    path = JOBS_DIR / job_id / filename
    if not path.exists():
        return JSONResponse(status_code=404, content={"error": "file not found"})
    return FileResponse(path)


@router.get("/metrics/{job_id}")
async def get_metrics(job_id: str):
    matches_json_path = JOBS_DIR / job_id / "matches.json"
    if not matches_json_path.exists():
        return JSONResponse(status_code=404, content={"error": "job not found"})
    with open(matches_json_path) as f:
        data = json.load(f)
    return data["metrics"]
