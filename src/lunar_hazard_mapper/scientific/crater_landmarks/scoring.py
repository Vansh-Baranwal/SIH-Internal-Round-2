"""
Member 4 — Landmark Quality Scoring.

Contains quality-scoring utilities for crater landmarks.

This module does not modify crater detection.
It evaluates outputs already produced by the M4 detector.
"""

from __future__ import annotations

from .detector import CraterCandidate

import numpy as np 

def score_detection(
    candidate: CraterCandidate,
) -> float:
    """
    Convert an existing crater detection confidence
    into the normalized M4 detection-quality score.

    Parameters
    ----------
    candidate:
        CraterCandidate produced by CraterDetector.

    Returns
    -------
    float
        Detection score in the range [0, 1].

    Notes
    -----
    The current detector confidence is already normalized
    to [0, 1]. Therefore this component preserves the
    detector's confidence rather than applying an additional
    arbitrary transformation.
    """

    confidence = float(
        candidate.confidence
    )

    if not 0.0 <= confidence <= 1.0:
        raise ValueError(
            "Crater detection confidence must "
            "be between 0 and 1."
        )

    return confidence

def score_geometry(
    candidate: CraterCandidate,
    geometry,
    pixel_size_m: float,
) -> float:
    """
    Calculate a normalized geometry-quality score.

    The score evaluates:

    1. Circularity of the extracted structure.
    2. Agreement between detector diameter and extracted diameter.
    3. Whether the measured crater depth is meaningful
       relative to the DEM pixel resolution.

    Returns
    -------
    float
        Geometry quality score in the range [0, 1].

    Notes
    -----
    This is an engineering quality heuristic. It is not
    a scientifically calibrated uncertainty estimate.
    """

    if pixel_size_m <= 0:
        raise ValueError(
            "pixel_size_m must be positive."
        )

    # --------------------------------------------------
    # 1. Circularity score
    # --------------------------------------------------

    circularity = float(
        geometry.circularity
    )

    if not 0.0 <= circularity <= 1.0:
        raise ValueError(
            "geometry.circularity must "
            "be between 0 and 1."
        )

    circularity_score = circularity

    # --------------------------------------------------
    # 2. Detector/extractor diameter agreement
    # --------------------------------------------------

    detected_diameter = float(
        candidate.diameter_m
    )

    extracted_diameter = float(
        geometry.diameter_m
    )

    if detected_diameter <= 0:
        raise ValueError(
            "candidate.diameter_m must be positive."
        )

    if extracted_diameter <= 0:
        raise ValueError(
            "geometry.diameter_m must be positive."
        )

    relative_difference = abs(
        extracted_diameter
        - detected_diameter
    ) / detected_diameter

    # Full score when the measurements agree.
    # Score decreases as the relative difference grows.
    diameter_agreement_score = max(
        0.0,
        1.0 - relative_difference,
    )

    # --------------------------------------------------
    # 3. Depth measurability
    # --------------------------------------------------

    depth_m = float(
        geometry.depth_m
    )

    if depth_m < 0:
        raise ValueError(
            "geometry.depth_m cannot be negative."
        )

    # A depression equal to one DEM pixel is
    # considered minimally measurable.
    depth_score = min(
        1.0,
        depth_m / pixel_size_m,
    )

    # --------------------------------------------------
    # Combined geometry score
    # --------------------------------------------------

    geometry_score = (
        0.50 * circularity_score
        +
        0.30 * diameter_agreement_score
        +
        0.20 * depth_score
    )

    return float(
        max(
            0.0,
            min(
                1.0,
                geometry_score,
            ),
        )
    )

def score_profile(
    profile,
) -> float:
    """
    Calculate a normalized DEM-profile quality score.

    The score evaluates:

    1. Number of available profile samples.
    2. Consistency of radial sampling.
    3. Validity of elevation values.
    4. Evidence that the profile contains a measurable
       central depression.

    Returns
    -------
    float
        Profile quality score in the range [0, 1].

    Notes
    -----
    This is an engineering quality heuristic. It is not
    a scientifically calibrated uncertainty estimate.
    """

    distances = list(
        profile.distances_m
    )

    elevations = list(
        profile.elevations_m
    )

    sampling_interval = float(
        profile.sampling_interval_m
    )

    # --------------------------------------------------
    # Basic validation
    # --------------------------------------------------

    if len(distances) != len(elevations):
        raise ValueError(
            "Profile distances and elevations "
            "must have the same length."
        )

    if len(distances) < 3:
        raise ValueError(
            "At least 3 profile samples are required."
        )

    if sampling_interval <= 0:
        raise ValueError(
            "sampling_interval_m must be positive."
        )

    distances_array = np.asarray(
        distances,
        dtype=float,
    )

    elevations_array = np.asarray(
        elevations,
        dtype=float,
    )

    # --------------------------------------------------
    # 1. Sample adequacy
    # --------------------------------------------------

    # Ten samples are treated as the minimum useful
    # profile length for this engineering score.
    sample_score = min(
        1.0,
        len(distances) / 10.0,
    )

    # --------------------------------------------------
    # 2. Sampling consistency
    # --------------------------------------------------

    spacing = np.diff(
        distances_array
    )

    if len(spacing) == 0:
        sampling_consistency = 0.0

    else:
        spacing_error = np.abs(
            spacing
            - sampling_interval
        )

        mean_spacing_error = float(
            np.mean(
                spacing_error
            )
        )

        if sampling_interval == 0:
            sampling_consistency = 0.0

        else:
            relative_error = (
                mean_spacing_error
                / sampling_interval
            )

            sampling_consistency = max(
                0.0,
                1.0 - relative_error,
            )

    # --------------------------------------------------
    # 3. Elevation validity
    # --------------------------------------------------

    finite_mask = np.isfinite(
        elevations_array
    )

    valid_fraction = float(
        np.mean(finite_mask)
    )

    validity_score = valid_fraction

    # --------------------------------------------------
    # 4. Depression evidence
    # --------------------------------------------------

    if not np.all(
        np.isfinite(
            elevations_array
        )
    ):
        depression_score = 0.0

    else:

        centre_elevation = float(
            elevations_array[0]
        )

        minimum_elevation = float(
            np.min(
                elevations_array
            )
        )

        elevation_range = float(
            np.max(
                elevations_array
            )
            -
            np.min(
                elevations_array
            )
        )

        if elevation_range <= 0.0:

            depression_score = 0.0

        else:

            # How close the centre is to the profile
            # minimum, normalized by total elevation range.
            centre_minimum_error = abs(
                centre_elevation
                - minimum_elevation
            ) / elevation_range

            centre_score = max(
                0.0,
                1.0 - centre_minimum_error,
            )

            # A non-zero elevation range confirms that
            # the profile contains measurable terrain variation.
            variation_score = min(
                1.0,
                elevation_range / 1.0,
            )

            depression_score = (
                0.70 * centre_score
                +
                0.30 * variation_score
            )

    # --------------------------------------------------
    # Combined profile score
    # --------------------------------------------------

    profile_score = (
        0.25 * sample_score
        +
        0.25 * sampling_consistency
        +
        0.25 * validity_score
        +
        0.25 * depression_score
    )

    return float(
        max(
            0.0,
            min(
                1.0,
                profile_score,
            ),
        )
    )

def score_combined(
    detection_score: float,
    geometry_score: float,
    profile_score: float,
) -> float:
    """
    Calculate the combined landmark-quality score.

    Parameters
    ----------
    detection_score:
        Quality score from crater detection.

    geometry_score:
        Quality score from crater geometry extraction.

    profile_score:
        Quality score from the DEM radial profile.

    Returns
    -------
    float
        Combined landmark quality score in [0, 1].

    Notes
    -----
    The current weighting is an engineering heuristic:

        detection = 40%
        geometry  = 35%
        profile   = 25%

    This is not a scientifically calibrated probability
    or uncertainty estimate.
    """

    scores = (
        float(detection_score),
        float(geometry_score),
        float(profile_score),
    )

    # --------------------------------------------------
    # Validate input ranges
    # --------------------------------------------------

    for name, score in zip(
        (
            "detection_score",
            "geometry_score",
            "profile_score",
        ),
        scores,
    ):

        if not 0.0 <= score <= 1.0:
            raise ValueError(
                f"{name} must be between 0 and 1."
            )

    # --------------------------------------------------
    # Weighted combination
    # --------------------------------------------------

    combined_score = (
        0.40 * scores[0]
        +
        0.35 * scores[1]
        +
        0.25 * scores[2]
    )

    return float(
        max(
            0.0,
            min(
                1.0,
                combined_score,
            ),
        )
    )

def classify_quality(
    combined_score: float,
) -> str:
    """
    Convert a combined landmark-quality score into
    a human-readable quality classification.

    Classification thresholds:

        >= 0.80 -> HIGH
        >= 0.60 -> MEDIUM
        <  0.60 -> LOW

    Parameters
    ----------
    combined_score:
        Combined landmark quality score in [0, 1].

    Returns
    -------
    str
        One of: "HIGH", "MEDIUM", "LOW".
    """

    score = float(combined_score)

    if not 0.0 <= score <= 1.0:
        raise ValueError(
            "combined_score must be between 0 and 1."
        )

    if score >= 0.80:
        return "HIGH"

    if score >= 0.60:
        return "MEDIUM"

    return "LOW"