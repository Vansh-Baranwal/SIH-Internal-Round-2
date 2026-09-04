"""
Stage B (Advanced): LoFTR — detector-free, dense matching.

Per your planning doc: "Exceptional at low-texture areas and multi-modal
matching... outputs dense matches which need filtering." This is the strongest
option for genuinely difficult cross-modal pairs (e.g. TMC vs IIRS, where IIRS
has very different visual characteristics), at the cost of being computationally
heavier and needing the QuadTree uniform-distribution filter (Stage C) applied
afterward, since LoFTR's dense output is NOT naturally spatially uniform.

Auto-fallback: same pattern as deep_matcher.py — falls back to SIFT if
pretrained weights can't be reached in this environment.
"""
from __future__ import annotations
import numpy as np
import warnings
from lunar_hazard_mapper.correspondence_engine.features.baseline_sift import MatchResult, match_sift


class LoFTRMatcher:
    def __init__(self, device: str = "cpu", pretrained: str = "outdoor"):
        self.device = device
        self.pretrained = pretrained
        self.backend = None
        self._model = None
        self._try_load()

    def _try_load(self):
        try:
            import torch
            import kornia.feature as KF
            self._model = KF.LoFTR(pretrained=self.pretrained).to(self.device).eval()
            self.backend = "loftr"
        except Exception as e:
            warnings.warn(
                f"[LoFTRMatcher] Could not load LoFTR weights "
                f"({type(e).__name__}: {e}). Falling back to SIFT baseline. "
                f"See scripts/download_weights.md for how to fix this on a "
                f"machine with internet access."
            )
            self.backend = "sift-fallback"

    def match(self, source: np.ndarray, reference: np.ndarray,
              confidence_threshold: float = 0.5) -> MatchResult:
        if self.backend == "sift-fallback":
            result = match_sift(source, reference)
            return MatchResult(result.keypoints_source, result.keypoints_reference,
                                result.match_confidences, "sift-fallback")
        try:
            return self._match_real(source, reference, confidence_threshold)
        except Exception as e:
            warnings.warn(
                f"[LoFTRMatcher] Real matcher failed at runtime "
                f"({type(e).__name__}: {e}). Falling back to SIFT for this call."
            )
            result = match_sift(source, reference)
            return MatchResult(result.keypoints_source, result.keypoints_reference,
                                result.match_confidences, "sift-fallback-runtime")

    def _match_real(self, source: np.ndarray, reference: np.ndarray,
                     confidence_threshold: float) -> MatchResult:
        import torch

        def to_tensor(img):
            t = torch.from_numpy(img).float() / 255.0
            if t.ndim == 2:
                t = t.unsqueeze(0).unsqueeze(0)
            return t.to(self.device)

        input_dict = {"image0": to_tensor(source), "image1": to_tensor(reference)}

        with torch.no_grad():
            correspondences = self._model(input_dict)

        keypoints0 = correspondences["keypoints0"].cpu().numpy()
        keypoints1 = correspondences["keypoints1"].cpu().numpy()
        confidence = correspondences["confidence"].cpu().numpy()

        keep = confidence > confidence_threshold
        return MatchResult(keypoints0[keep], keypoints1[keep], confidence[keep], "loftr")


def match_loftr(source: np.ndarray, reference: np.ndarray, device: str = "cpu") -> MatchResult:
    matcher = LoFTRMatcher(device=device)
    return matcher.match(source, reference)
