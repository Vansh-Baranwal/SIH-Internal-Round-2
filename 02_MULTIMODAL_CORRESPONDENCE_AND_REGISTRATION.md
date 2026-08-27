# Multi-Modal Correspondence & Registration

## 1. Objective

Build the central core of the SIH26166 platform: a robust engine capable of accurately finding correspondences between highly varied lunar imagery. This includes matching across different sensors (multi-modal), varying sun angles (illumination invariance), different viewpoints (viewpoint invariance), and significantly different resolutions (scale invariance).

## 2. Sensor Modalities Supported

The engine must support the following primary cross-modal combinations:
*   **TMC ↔ OHRC:** Aligning regional context (TMC, 5m/pixel) with high-resolution details (OHRC, ~0.25m/pixel). Extremely high scale difference.
*   **TMC ↔ IIRS:** Aligning optical terrain (TMC) with hyperspectral mineral/ice footprints (IIRS, ~80m/pixel). Requires mapping lower-resolution spectral pixels to high-resolution optical data.
*   **OHRC ↔ IIRS:** Directly aligning ultra-high resolution to spectral footprints.
*   **TMC/OHRC/IIRS ↔ LRO NAC:** Using external LRO NAC imagery as independent verification or additional multi-modal capability.
*   **SELENE:** Supported where relevant (e.g., Terrain Camera or Kaguya data).

## 3. Pipeline Stages

The correspondence pipeline will consist of the following ordered stages:

### A. Preprocessing & Normalization
*   **Radiometric Calibration:** Normalize intensity distributions between different sensors to minimize the impact of varying sensor characteristics.
*   **Illumination Handling:** Apply illumination invariant transformations (e.g., phase congruency, directional gradients) if simple normalization fails.
*   **Scale Handling:** Downsample the higher-resolution image (e.g., OHRC) using image pyramids (Gaussian) to roughly match the Ground Sample Distance (GSD) of the lower-resolution image (e.g., TMC) prior to feature extraction.
*   **Viewpoint Handling:** Where DEM is available (M3), apply an initial orthorectification step to remove severe topographic distortions.

### B. Feature Extraction & Matching
*   **Detection:** Identify stable keypoints (crater rims, boulders, rilles) in both images.
*   **Description:** Generate robust descriptors that encapsulate the local neighborhood of each keypoint, maximizing invariance to scale, rotation, and non-linear intensity changes.
*   **Matching:** Perform Nearest Neighbor matching (often with ratio test) between descriptors.
*   **Cross-Modal Considerations:** Multi-modal matching often fails with simple pixel-intensity descriptors. Structural or learning-based descriptors are critical.

### C. Geometric Verification (RANSAC) & Refinement
*   **Outlier Rejection:** Apply RANSAC (Random Sample Consensus) or MAGSAC++ to filter out incorrect matches (outliers).
*   **Geometric Models:** Utilize an appropriate transformation model:
    *   *Affine/Projective (Homography):* For flat terrain or nadir observations.
    *   *Piecewise/Thin Plate Spline:* For complex topography.
*   **Sub-Pixel Refinement:** Perform localized phase-correlation or iterative Lucas-Kanade optimization on the confirmed inliers to achieve sub-pixel correspondence accuracy.
*   **Uniform Match Distribution:** Implement a spatial grid-based filtering mechanism (e.g., QuadTree) to ensure match points are not clustered in highly textured areas but are uniformly distributed across the overlapping region.

### D. Registration & Output Generation
*   **Transformation Estimation:** Compute the final transformation matrix.
*   **Image Warping:** Warp the source image to align with the target reference image using high-quality interpolation (e.g., Lanczos).
*   **Match-Point Export:** Output the validated keypoint pairs in a standard format (e.g., CSV, JSON) for analysis.

## 4. Candidate Algorithms & Evaluation Strategy

Do NOT blindly assume one algorithm is best. The existing SIFT/RANSAC implementation will be treated as the baseline.

| Algorithm | Category | Pros | Cons | Role in Pipeline |
| :--- | :--- | :--- | :--- | :--- |
| **SIFT/SURF** | Handcrafted | Existing baseline, well-understood scale invariance. | Struggles with severe non-linear intensity changes (cross-modal). | Baseline / Fallback. |
| **AKAZE** | Handcrafted | Fast, preserves boundaries better than SIFT. | May still struggle with extreme multi-modal illumination differences. | Secondary Baseline. |
| **SuperPoint** | Deep Learning | Excellent repeatability, good under illumination changes. | Requires resizing, may miss very fine lunar textures if not trained well. | Recommended First Implementation. |
| **LightGlue** | Deep Learning (Matcher) | State-of-the-art matching and outlier rejection. Very fast. | Must be paired with a good extractor (like SuperPoint or ALIKED). | Recommended Matcher. |
| **LoFTR** | Deep Learning (Detector-Free) | Exceptional at low-texture areas and multi-modal matching. | Computationally heavy, outputs dense matches which need filtering. | Advanced Implementation. |

### Evaluation Methodology
1.  **Baseline Setup:** Benchmark existing SIFT pipeline on a curated TMC/OHRC dataset.
2.  **Implementation 1:** Integrate SuperPoint + LightGlue. Compare against baseline.
3.  **Implementation 2:** Integrate LoFTR. Compare against SuperPoint + LightGlue.

## 5. Registration Quality Metrics

The system will quantitatively evaluate the success of registration using:
1.  **RMSE (Root Mean Square Error):** Calculated on the final inlier match points after transformation. (Target: < 1.0 pixels).
2.  **Inlier Count:** The absolute number of verified geometric matches.
3.  **Inlier Ratio:** (Inliers / Total Initial Matches). Indicates the robustness of the initial matching phase.
4.  **Spatial Coverage:** A metric (e.g., percentage of grid cells containing at least one match) to guarantee uniformly distributed match points.
