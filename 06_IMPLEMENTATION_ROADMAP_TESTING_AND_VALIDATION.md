# Implementation Roadmap, Testing, & Validation

## 1. Roadmap Milestones

### M0: Repository Audit & Data Verification
*   **Goal:** Verify existing M1-M6 integrity and prepare the spatial database.
*   **Tasks:** Audit current M2 (CSASR) and M6 (DEM) commits. Script automated spatial overlap checks for Chandrayaan-2 datasets.
*   **Acceptance:** Existing tests pass. Overlapping TMC/OHRC/IIRS pairs identified for development.

### M1: Multimodal Correspondence Baseline
*   **Goal:** Establish the existing SIFT/RANSAC performance baseline.
*   **Tasks:** Isolate the old SIFT code. Run it against multi-modal (TMC vs OHRC) and multi-illumination pairs.
*   **Acceptance:** Baseline RMSE, inlier ratio, and failure cases documented.

### M2: Advanced Correspondence Engine (Core SIH26166)
*   **Goal:** Implement the primary AI/modern correspondence pipeline (e.g., SuperPoint/LightGlue or LoFTR).
*   **Tasks:** Build preprocessing normalization. Integrate feature extractor and matcher. Implement RANSAC and affine/spline transformations.
*   **Tests:** Cross-modal matching tests (TMC-OHRC, TMC-IIRS).
*   **Acceptance:** Engine successfully registers multi-modal pairs with < 1.0 pixel RMSE. Outperforms M1 baseline.

### M3: Sub-Pixel Refinement & Uniform Distribution
*   **Goal:** Achieve sub-pixel accuracy and ensure match points cover the entire image.
*   **Tasks:** Implement QuadTree grid filtering for spatial uniformity. Add Lucas-Kanade or phase-correlation refinement.
*   **Tests:** Validation of inlier distribution metrics. Sub-pixel coordinate verification.

### M4: Counterfactual Sun Simulator (Evaluation)
*   **Goal:** Build the tool to prove sun-angle invariance.
*   **Tasks:** Connect DEM to Three.js shadow renderer. Generate synthetic lighting variants.
*   **Tests:** Run M2 engine on synthetic vs. real variants.
*   **Acceptance:** Engine extracts identical keypoints despite altered shadow geometry.

### M5: Scientific Intelligence Layers (IIRS & LUPEX)
*   **Goal:** Implement the spectral classification and water-ice refinement features.
*   **Tasks:** Build IIRS band-ratio logic. Map coarse Diviner/Mini-RF data to registered optical footprints.
*   **Acceptance:** Visual generation of mineral and hydration heatmaps on registered OHRC data. No false scientific claims made.

### M6: Crater Landmark Network & Registration GPS
*   **Goal:** Build the crater database and localization feature.
*   **Tasks:** Extract crater geometries. Build retrieval pipeline for unknown images.
*   **Tests:** Localization accuracy tests using stripped metadata.

### M7: Frontend Integration & Cockpit
*   **Goal:** Unify the UI.
*   **Tasks:** Build Multi-Sensor Cockpit. Integrate 3D Digital Twin. Connect React frontend to FastAPI correspondence endpoints.
*   **Acceptance:** Seamless user journey from ingestion to 3D visualization.

### M8: End-to-End Validation & Legacy Integration
*   **Goal:** Ensure the entire pipeline works, including legacy modules.
*   **Tasks:** Route registered outputs into M4 (Hazards) and M5/M6 (Lander).
*   **Acceptance:** Existing hazard maps and trajectory sims successfully process the new registered imagery.

---

## 2. Testing & Validation Strategy

*   **Registration Accuracy:** The primary metric is RMSE on a held-out set of manually annotated lunar landmarks. Target is < 1.0 pixels.
*   **Cross-Modal Robustness:** System must successfully register at least 85% of verified overlapping TMC/OHRC pairs.
*   **Sun-Angle Invariance Verification:** Demonstrated quantitatively via the Counterfactual Sun Simulator.
*   **Regression Testing:** The M2 CSASR output must remain bit-for-bit identical to its state at commit `6fed60d`.
*   **Synthetic vs. Real Separation:** Automated tests must ensure synthetic images generated in M4 never overwrite or blend into the real dataset repository.

---

## 3. Definition of Done (SIH26166 Transformation)

The transformation is considered complete when:
1.  The Correspondence Engine successfully registers TMC, OHRC, and IIRS imagery without manual intervention.
2.  Sub-pixel accuracy is quantitatively proven and match points are uniformly distributed.
3.  Sun-angle invariance is demonstrable via the 3D simulation tool.
4.  IIRS spectral overlays and LUPEX water-ice confidence maps map correctly to the registered optical data.
5.  All existing M2 (CSASR), M4 (Hazards), and M6 (Trajectory) features remain functional and accessible in the unified frontend.
6.  The UI provides a seamless, professional experience suitable for an ISRO evaluation panel.
