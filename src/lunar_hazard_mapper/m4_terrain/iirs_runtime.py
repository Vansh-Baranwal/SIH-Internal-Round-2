"""Runtime-only synthetic adapter for the existing Phase 8 IIRS pipeline."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
from affine import Affine

from lunar_hazard_mapper.scientific.iirs import (
    IIRSCube,
    IllustrativeClassificationRule,
    MaterialClass,
    classify_materials,
    compute_iirs_band_ratio,
    create_default_guardrail,
    extract_iirs_spectral_features,
    preprocess_iirs_cube,
)


class SyntheticIirsClassificationProvider:
    """Expose a controlled synthetic cube through the real Phase 8 pipeline."""

    def load_classification(self) -> Dict[str, Any]:
        cube = self._cube()
        preprocessed = preprocess_iirs_cube(cube)
        ratios = [
            compute_iirs_band_ratio(cube, preprocessed, 0, 1),
            compute_iirs_band_ratio(cube, preprocessed, 1, 0),
        ]
        features = extract_iirs_spectral_features(preprocessed, ratios)
        result = classify_materials(features, self._rules())
        serialized = result.to_dict()
        class_map = serialized["class_map"]
        valid_mask = serialized["valid_mask"]

        counts = {material_class.name: 0 for material_class in MaterialClass}
        for row in class_map:
            for class_name in row:
                counts[class_name] += 1
        valid_pixel_count = int(np.asarray(result.valid_mask, dtype=bool).sum())
        valid_counts = {
            class_name: sum(
                1
                for row_index, row in enumerate(class_map)
                for column_index, value in enumerate(row)
                if value == class_name and valid_mask[row_index][column_index]
            )
            for class_name in counts
        }

        return {
            "status": "illustrative",
            "source_type": "synthetic",
            "classes": [
                class_name for class_name in (material_class.name for material_class in MaterialClass)
                if counts[class_name] > 0
            ],
            "class_map": class_map,
            "score_map": serialized["score_map"],
            "score_semantics": "feature magnitude that triggered the rule; not probability or confidence",
            "valid_mask": valid_mask,
            "shape": {"height": len(class_map), "width": len(class_map[0])},
            "summary": [
                {
                    "class_name": class_name,
                    "pixel_count": counts[class_name],
                    "valid_pixel_count": valid_counts[class_name],
                    "valid_pixel_percentage": (
                        valid_counts[class_name] / valid_pixel_count * 100.0
                        if valid_pixel_count
                        else 0.0
                    ),
                }
                for class_name in (material_class.name for material_class in MaterialClass)
                if counts[class_name] > 0
            ],
            "provenance": {
                "source": "phase_8_iirs_classification_runtime_adapter",
                "dataset_name": cube.dataset_name,
                "pipeline": [
                    "preprocess_iirs_cube",
                    "compute_iirs_band_ratio",
                    "extract_iirs_spectral_features",
                    "classify_materials",
                ],
                "guardrail": create_default_guardrail().to_dict(),
                "note": (
                    "Controlled synthetic development input passed through the existing Phase 8 "
                    "rule-based classifier. Not real IIRS data and not publication-grade."
                ),
            },
        }

    @staticmethod
    def _cube() -> IIRSCube:
        return IIRSCube(
            data=np.array(
                [
                    [[4.0, 2.0, 0.0], [8.0, 4.0, 0.0]],
                    [[6.0, 3.0, 0.0], [2.0, 1.0, 0.0]],
                ],
                dtype=np.float32,
            ),
            wavelengths_um=np.array([0.8, 1.2, 2.0], dtype=np.float32),
            pixel_size_m=20.0,
            transform=Affine.translation(100.0, 200.0) @ Affine.scale(20.0, -20.0),
            crs="LOCAL_METER_FRAME",
            nodata=-9999.0,
            dataset_name="synthetic-iirs-phase-8-runtime",
            sensor="IIRS",
            observation_date="2026-01-01",
            orbit_id="synthetic-runtime-orbit",
            notes="Controlled synthetic development data only; not a real IIRS measurement.",
            extra={"synthetic": True, "controlled_fixture": "phase_8_spectrum_a"},
        )

    @staticmethod
    def _rules() -> list[IllustrativeClassificationRule]:
        return [
            IllustrativeClassificationRule(
                feature_name="ratio_band_0_over_band_1",
                target_class=MaterialClass.PYROXENE,
                min_threshold=1.5,
            ),
            IllustrativeClassificationRule(
                feature_name="ratio_band_1_over_band_0",
                target_class=MaterialClass.ILLMENITE,
                min_threshold=0.6,
            ),
        ]