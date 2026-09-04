# M4 Phase 11.12: Lunar GPS Final Validation

Phase 11.12 is the terminal orchestration and decision layer for the frozen Phase 11 pipeline. It consumes the result objects from Phases 11.1 through 11.11 and does not recompute matching, geometry, coordinates, confidence, ROI, metadata separation, or accuracy.

## Evidence and claims

The required chain is the Phase 11.1 input, metadata assessment, retrieval, correspondence, anchor selection, geometric verification, coordinate estimation, and explicit Phase 11.11 accuracy evaluation. Confidence (11.8), ROI retrieval (11.9), and metadata separation (11.10) are supporting evidence and may be absent. Geometry, confidence, ROI, and metadata agreement never substitute for authoritative truth.

Validation levels are 0 implementation only, 1 pipeline execution, 2 internally usable localization evidence, 3 authoritative accuracy measured, and 4 an explicit authoritative acceptance criterion satisfied. Only level 4 maps to `VALIDATED`.

## Status model

`VALIDATED` requires compatible authoritative truth, computed accuracy, and an explicit passing criterion. `TECHNICALLY_VALID` means the software evidence chain is usable but scientific validation is not established. `INCONCLUSIVE` represents measured authoritative evidence without a passing criterion or with a failed supplied criterion. `BLOCKED` represents unavailable required execution evidence. `INVALID` represents contradictions, malformed evidence, or provenance violations.

The validator preserves estimated coordinates, upstream statuses, an evidence matrix, checks, reasons, limitations, and provenance. It performs no CRS conversion, longitude wrapping, coordinate alteration, threshold invention, confidence recalculation, ROI recalculation, or accuracy recalculation.

## Truth and provenance

Phase 11.11 truth authority and provenance are inspected rather than trusted from a status string alone. Synthetic and unavailable evidence remains distinct from real evidence; synthetic evidence can demonstrate mechanics only. Source metadata is contextual and never truth. The repository inspection found no authoritative real lunar localization reference dataset, so the normal real-data outcome is `TECHNICALLY_VALID`, not scientific `VALIDATED`.

Cross-phase checks cover required artifact presence, estimate/status coherence, geometry claim boundaries, blocked confidence with a score, ROI/reference identity, accuracy authority, and synthetic provenance marked as real. No scientific acceptance threshold is invented; caller-supplied thresholds remain evaluation configuration unless an authoritative specification establishes them.

## Limitations

The framework can establish implementation and internal evidence readiness. It cannot establish real-world Lunar GPS accuracy or validity without an authoritative, provenance-bearing reference dataset and an explicit acceptance criterion.