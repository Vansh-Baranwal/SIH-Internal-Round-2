# Frontend, Backend & UX Plan

## 1. UX Philosophy & Visual Identity

The platform must feel like a professional ISRO/space-science analysis tool. It will maintain the existing black/white/dark-mode lunar visual identity, accented with high-contrast colors (e.g., neon blue, amber) only for data overlays, confidence heatmaps, and matched keypoints. The interface should prioritize data density, clear scientific metadata, and seamless transitions between 2D analysis and 3D context.

## 2. Global UI Layout

*   **Top Navigation:** ISRO/SIH branding, Current Module Selector (Registration, Analytics, 3D, Mission), and an active processing queue indicator.
*   **Left Sidebar (Data Panel):** Dataset selection (TMC, OHRC, IIRS), metadata inspection, coordinate readout, and layer management.
*   **Main Workspace:** Context-dependent primary viewer (2D canvas, Split-screen, or 3D viewer).
*   **Right Sidebar (Analytics Panel):** Registration metrics (RMSE, Inlier count), algorithm parameters, and confidence scores.

## 3. Core Pages & Routes

### A. Landing / Mission Control
*   **Purpose:** Overview of the SIH26166 project, system status, and entry point.
*   **UI Components:** High-level metrics, recent registrations, and quick-links to core tools.

### B. Image Registration & Multi-Sensor Cockpit (Core SIH26166)
*   **Purpose:** The primary workspace for multimodal correspondence.
*   **Inputs:** Select Source (e.g., OHRC) and Reference (e.g., TMC) images.
*   **Main Workspace:** Side-by-side or swipe-slider view.
*   **Outputs:** Visualized match points (lines connecting the two images), transformed/registered image overlay.
*   **Analytics Panel:** RMSE, inlier ratio, spatial coverage histogram, sub-pixel accuracy estimation.
*   **API Requirements:** `/api/v1/register` (trigger engine), `/api/v1/metrics` (fetch results).

### C. Spectral & Water-Ice Intelligence (IIRS / LUPEX)
*   **Purpose:** Analyze mineralogy and hydration on registered optical images.
*   **Main Workspace:** Base optical image (OHRC) with a colored, thresholded heatmap overlay representing spectral classifications or water-ice confidence.
*   **UI Components:** Color legend, spectral band ratio selector, classification confidence slider.
*   **API Requirements:** `/api/v1/spectral/classify`, `/api/v1/ice/confidence`.

### D. Lunar Change Detection
*   **Purpose:** Temporal analysis of registered pairs.
*   **Main Workspace:** Image differencing view. Flashing GIF-style comparison or highlighted difference map.
*   **UI Components:** Timeline slider, threshold slider to filter out noise.

### E. 3D Lunar Observatory (Digital Twin)
*   **Purpose:** Spatial context and counterfactual sun simulation.
*   **Main Workspace:** Full-screen Three.js terrain (M3 DEM-backed).
*   **UI Components:** Camera frustum toggles (show where OHRC is looking), Sun azimuth/elevation sliders.
*   **Action Button:** "Generate Counterfactual Observation" -> Triggers simulation and sends to Registration Cockpit.

### F. Legacy Integration: Hazard Analysis & Mission Simulation
*   **Purpose:** Preserve existing M4, M5, M6 functionality.
*   **UI Components:** Existing Hazard Map visualization, existing Lander/Trajectory simulation UI, now updated to accept newly registered imagery as inputs.

## 4. Backend Architecture (FastAPI)

*   **Asynchronous Processing:** Multi-modal registration is computationally heavy. The backend must use Celery or FastAPI background tasks. The UI will poll or use WebSockets to display loading states.
*   **Data Models:** Define strict Pydantic schemas for `RegistrationRequest`, `RegistrationResult`, and `FeatureMatches`.
*   **File Serving:** Efficient streaming of large GeoTIFFs/pyramids (e.g., using Cloud Optimized GeoTIFFs - COG logic) to the frontend canvas.

## 5. Judge / Demo Experience

The UX will include a "Guided Demo" mode. This will step a judge through:
1.  Loading two unaligned, multi-modal images (TMC + OHRC).
2.  Executing the correspondence engine and watching the match points appear.
3.  Viewing the registered output and the sub-pixel RMSE metrics.
4.  Switching to the 3D Viewer to change the Sun angle.
5.  Re-running registration to prove sun-angle invariance.
6.  Applying the IIRS Spectral overlay on the newly registered footprint.
