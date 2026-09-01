# Claude Code Guidelines - SIH26166 Multi-Modal Correspondence Platform

## Project Overview
This repository (`SIH-Internal-Round-2`) upgrades the existing Lunar Hazard Mapper into the **SIH26166 Multi-Modal Lunar Image Correspondence and Registration Platform**.
It integrates multi-sensor cross-matching (Chandrayaan-2 TMC, OHRC, IIRS, and LRO NAC), illumination and scale invariance, landmark geolocalization, spectral intelligence, and a Multi-Sensor Fusion Cockpit while preserving existing validated modules (M1–M6).

---

## Critical Invariant Rules (What MUST NOT Be Changed or Broken)
1. **M2 CSASR Pipeline:** The validated Stage 1 & Stage 2 CSASR lunar super-resolution pipeline (`src/lunar_hazard_mapper/m2_super_resolution/`) is scientifically locked. **Do not retrain, replace, or delete.**
2. **Hazard Mapping (M4):** Slope, roughness, and crater/boulder hazard modules (`src/lunar_hazard_mapper/m4_hazards/`) must remain functional and operate as a downstream layer on registered imagery.
3. **Terrain & DEM (M3):** Physical elevation handling, DEM transformations, and GeoTIFF processing are the truth layer for 3D simulation and illumination modeling.
4. **Lander & Trajectory Simulation (M5 & M6):** Lander site evaluation and trajectory physics must remain functional as downstream consumers.
5. **No Destructive Refactoring:** Add new modules (Correspondence Engine, Landmark Network, Counterfactual Sun Simulator, Temporal Engine, Cockpit) alongside existing code without breaking existing APIs or tests.

---

## Code Architecture & Target Modules
* **Core Correspondence Engine (`src/lunar_hazard_mapper/correspondence/` or `alignment`):**
  * Multi-modal feature extractors and matchers: SIFT baseline, SuperPoint + LightGlue, LoFTR / detector-free matcher.
  * Preprocessing: Radiometric normalization, illumination invariant filtering (phase congruency / gradients), Gaussian scale pyramids (e.g. OHRC downsampling to match TMC resolution).
  * Robust geometric estimation: RANSAC / MAGSAC++ homography & Thin Plate Splines.
  * Sub-pixel refinement (Lucas-Kanade / phase correlation) & uniform grid distribution (QuadTree filtering).
  * Registration metrics: RMSE (< 1.0 px target), inlier count, inlier ratio, spatial coverage.
* **Counterfactual Sun Simulator:** Synthetic illumination & shadow projection from DEM to evaluate sun-angle invariance without polluting real registered products.
* **Lunar Landmark Network:** Database of stable crater geometries for coarse-to-fine georeferencing / "GPS" retrieval.
* **Spectral & Ice Intelligence:** Lightweight IIRS hyperspectral footprint mapping and multi-sensor water-ice confidence layers.
* **Temporal Analysis:** Sub-pixel change detection & differencing between multi-temporal observation pairs.
* **Backend API (`src/lunar_hazard_mapper/api/`):** FastAPI endpoints for pairwise multi-modal registration, benchmark comparisons, landmark query, sun simulation, and temporal diffs.
* **Frontend Cockpit (`web/`):** React + Vite + Tailwind + Three.js / R3F Multi-Sensor Fusion Cockpit (swipe/split viewer, keypoint visualizer, metrics HUD, digital twin viewer).

---

## Development & Test Commands
- **Backend Environment:** Python 3.10+ / PyTorch
- **Run Backend:** `uvicorn src.lunar_hazard_mapper.api.main:app --reload --port 8000`
- **Run Frontend:** `cd web && npm run dev`
- **Run Tests:** `pytest tests/`
- **Build Frontend:** `cd web && npm run build`


