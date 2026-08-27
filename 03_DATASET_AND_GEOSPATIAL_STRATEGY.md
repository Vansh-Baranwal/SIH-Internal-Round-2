# Dataset & Geospatial Strategy

## 1. Objective

Define the actual data requirements, ingestion strategies, and spatial management required to power the SIH26166 correspondence engine and its advanced scientific features. This document establishes how diverse lunar datasets will be acquired, verified for spatial overlap, and prepared for processing.

## 2. Core Imagery Datasets

| Dataset | Purpose | Expected Resolution | Spectral Properties | Coordinate System | Status / Action |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Chandrayaan-2 TMC** | Broad regional context, topography, base layer for registration. | 5 m/pixel | Panchromatic (Optical) | GCS / Moon_2000 | Verify local availability; acquire overlapping regions with OHRC. |
| **Chandrayaan-2 OHRC** | Ultra-high resolution target analysis, sub-pixel matching. | 0.25 - 0.3 m/pixel | Panchromatic (Optical) | GCS / Moon_2000 | Verify local availability; strict overlap with TMC required. |
| **Chandrayaan-2 IIRS** | Mineral classification, spectral overlay, hydration context. | ~80 m/pixel | Hyperspectral (IR) | GCS / Moon_2000 | Must be acquired; requires overlap with TMC/OHRC in ROI. |
| **LRO NAC (External)** | Independent cross-modal reference, temporal change detection. | 0.5 - 2 m/pixel | Panchromatic (Optical) | GCS / Moon_2000 | Must be acquired; target same ROIs as Chandrayaan datasets. |
| **SELENE (Optional)** | Additional multi-modal reference (Terrain Camera). | ~10 m/pixel | Panchromatic (Optical) | GCS / Moon_2000 | Optional; acquire if requested for specific ROIs. |

## 3. Geospatial & Scientific Support Datasets

| Dataset | Purpose | Expected Resolution | Format | Status / Action |
| :--- | :--- | :--- | :--- | :--- |
| **DEM / DTM (LOLA / TMC)** | Orthorectification, 3D visualization, counterfactual sun simulation, existing hazard maps. | Variable (typically 5m - 30m) | GeoTIFF (Elevation) | Existing (M3); ensure coverage for new ROIs. |
| **LRO Diviner** | Temperature data for coarse ice-confidence indicators. | Coarse | GeoTIFF / Grid | Must acquire for water-ice refinement. |
| **LRO Mini-RF** | Radar backscatter for ice-confidence (CPR). | Coarse | GeoTIFF | Must acquire for water-ice refinement. |
| **LOLA (Reflectance)** | Surface brightness anomalies for ice indicators. | Variable | GeoTIFF | Must acquire for water-ice refinement. |
| **Temporal Imagery** | Image pairs of the same region separated by time (e.g., LRO NAC from 2010 vs 2020). | Varies | GeoTIFF | Must actively search PDS for known change regions. |

## 4. Overlap & Scene Selection Strategy

**Critical Constraint:** Do NOT assume filenames or broad coordinate bounding boxes imply useful optical overlap.

1.  **Target Regions of Interest (ROIs):**
    *   Focus on the Lunar South Pole (e.g., Shackleton, de Gerlache, Faustini, Cabeus) for the LUPEX Water-Ice feature.
    *   Select mid-latitude craters with distinct features (e.g., Tycho, Copernicus) for baseline algorithm testing.
2.  **Geospatial Footprint Intersection:**
    *   Develop a pre-ingestion script to parse the metadata (PDS/ISDA labels) of all candidate images.
    *   Project the corner coordinates into a common spatial database (e.g., GeoJSON polygons).
    *   Calculate the precise intersection area. Reject pairs where the physical overlapping area is too small to yield meaningful correspondence points.
3.  **Illumination Screening:**
    *   Check solar azimuth and elevation in metadata.
    *   Intentionally select image pairs of the *same* ROI with *different* sun angles to explicitly test the sun-angle invariance requirement.

## 5. Preprocessing & Normalization Pipeline

Before reaching the correspondence engine, data must be unified:
*   **Format Conversion:** Convert all PDS/ISDA formats to standardized GeoTIFFs.
*   **Coordinate Unification:** Ensure all data uses a consistent lunar reference frame (e.g., Moon_2000, equidistant cylindrical or polar stereographic depending on latitude).
*   **No-Data Handling:** Mask out invalid pixels and image borders to prevent the correspondence engine from matching artifacts.
*   **Registration Role:** The lower-resolution or higher-confidence geolocated image (usually TMC or LRO) acts as the fixed *Reference*, while the other image (e.g., OHRC or an unanchored image) acts as the moving *Target* to be registered.
