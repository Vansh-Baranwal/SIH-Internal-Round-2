# Advanced Features, 3D, and Scientific Intelligence

## 1. Counterfactual Sun Simulator (Sun-Angle Invariance Test)
*   **Objective:** Demonstrate the pipeline's robustness to varying illumination conditions, fulfilling the sun-angle invariance requirement.
*   **Pipeline:** DEM -> 3D Terrain -> Sun Position Control -> Synthetic Shadow Rendering -> Synthetic Image Generation -> Correspondence Engine vs. Real Target.
*   **UI Concept:** A slider in the 3D viewer adjusting Sun azimuth/elevation, with a button to "Run Registration against current Sun state."
*   **Validation:** Verify that the correspondence engine extracts the same physical keypoints regardless of the synthetic shadow placement.
*   **Constraint:** This is purely an evaluation tool. Synthetic outputs must be strictly labeled as "Simulated Data."

## 2. Multi-Sensor Fusion Cockpit
*   **Objective:** Provide a unified UI for analyzing registered multi-modal datasets.
*   **Pipeline:** Registered TMC/OHRC/IIRS/LRO datasets -> Frontend UI.
*   **UI Concept:** Split-screen or swipe-layer interface. Users can overlay datasets, adjust opacity, and inspect spatial coverage and confidence metrics.
*   **Relationship to SIH26166:** Directly visualizes the "Registered output product" and multi-modal alignment success.

## 3. Lunar Change / Temporal Intelligence
*   **Objective:** Identify physical surface changes (e.g., new craters, ejecta) between temporally separated observations.
*   **Pipeline:** Observation A & Observation B -> Correspondence Engine -> Sub-pixel Registration -> Image Differencing -> Change Detection Filtering (ignoring illumination).
*   **Scientific Value:** Automates the discovery of dynamic lunar events.
*   **Constraint:** Heavily dependent on finding genuine multi-date imagery (e.g., LRO NAC). Do not fabricate temporal change.

## 4. Registration "GPS" for Lunar Images
*   **Objective:** Estimate the precise location of an unknown or weakly georeferenced lunar image.
*   **Pipeline:** Unknown Image -> Feature Extraction -> Landmark Database Query -> Correspondence Engine -> Geometric Verification -> Coordinate Estimation -> ROI Retrieval.
*   **UI Concept:** "Upload Image to Geolocate." Returns estimated coordinates and an overlaid view on the broader lunar map.
*   **Distinction:** Clearly label outputs as "Estimated Coordinates" versus "Metadata-derived Coordinates."

## 5. Crater-Based Lunar Landmark Network
*   **Objective:** Create a database of stable crater geometries to act as registration anchors.
*   **Data Stored:** Crater ID, Center (Lat/Lon), Diameter, DEM Profile, and multi-sensor appearances (TMC, OHRC, IIRS).
*   **Pipeline:** Crater Detection -> Multi-modal crop extraction -> Database Storage.
*   **Scientific Value:** Enhances cross-modal matching by relying on structural features rather than transient pixel intensities.

## 6. IIRS Spectral / Mineral Overlay
*   **Objective:** Project hyperspectral mineralogical data onto high-resolution optical imagery.
*   **Pipeline:** IIRS Hyperspectral Cube -> Spectral Analysis (Band ratios, USGS references) -> Mineral Classification -> Correspondence Engine (Registration to OHRC/TMC) -> High-Res Overlay.
*   **Material Classes:** Ilmenite, pyroxene, olivine, plagioclase/feldspar, unclassified.
*   **Constraint:** Framed as a lightweight/illustrative classification. Do not present as publication-grade mineralogy without explicit scientific validation.

## 7. LUPEX-Targeted Water-Ice Confidence Refinement
*   **Objective:** Spatially refine coarse water-ice indicators using high-resolution registered optical imagery for upcoming missions like LUPEX.
*   **Pipeline:** Coarse Indicators (Diviner, Mini-RF, LOLA) + IIRS Hydration Signal -> Correspondence Engine (Registration to OHRC/TMC) -> High-Res Context Overlay -> Refined Confidence Map.
*   **Terminology:** Use "hydration signal", "water-ice confidence", "candidate hotspot". Do NOT claim "confirmed water ice."

## 8. 3D Multi-Sensor Lunar Viewer / Digital Twin
*   **Objective:** Evolve the existing 3D system into a comprehensive multi-sensor digital twin.
*   **Features:** DEM terrain base, virtual camera frustums (TMC, OHRC footprints), Sun simulation, crater landmarks, and layered overlays (hazards, spectra, ice).
*   **Constraint:** The 3D environment must be visually distinct from 2D real observations.

## 9. Existing Hazard Map & Lander Systems (Integration)
*   **Objective:** Repurpose existing M4, M5, and M6 modules as downstream applications.
*   **Pipeline:** Registered Imagery (New Engine) -> DEM Context -> M4 Hazard Mapping -> M5 Lander Site Evaluation -> M6 Trajectory Simulation.
*   **Constraint:** Do not remove these modules. They prove the utility of the newly registered image products.
