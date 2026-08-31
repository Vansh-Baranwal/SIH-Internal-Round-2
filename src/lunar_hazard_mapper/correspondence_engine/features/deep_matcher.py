"""
Stage B (Recommended): SuperPoint + LightGlue deep-learning matcher.

Per your planning doc, this is the "Recommended First Implementation" — deep
keypoint detection (SuperPoint) + state-of-the-art learned matching (LightGlue),
which should outperform SIFT particularly on cross-modal (TMC vs OHRC) and
cross-illumination pairs, since it's trained to be robust to exactly those
variations rather than relying on handcrafted intensity gradients.

Auto-fallback: if pretrained weights can't be downloaded (no internet, or a
restricted network), this transparently falls back to the SIFT baseline so the
REST of the pipeline (RANSAC, sub-pixel refinement, evaluation) is always
testable, even before weights are available.
"""
from __future__ import annotations
import numpy as np
import warnings
from lunar_hazard_mapper.correspondence_engine.features.baseline_sift import MatchResult, match_sift


class SuperPointLightGlueMatcher:
    def __init__(self, device: str = "cpu"):
        self.device = device
        self.backend = None
        self._extractor = None
        self._matcher = None
        self._try_load()

    def _try_load(self):
        try:
            import torch
            import kornia.feature as KF
            self._extractor = KF.DISK.from_pretrained("depth").to(self.device).eval()
            # kornia's LightGlue implementation expects DISK or SuperPoint-style
            # descriptors; DISK is used here as it's the most reliably-downloadable
            # kornia-hosted weight set. Swap to KF.SuperPoint if your network can
            # reach the SuperPoint checkpoint host instead.
            self._matcher = KF.LightGlueMatcher("disk").to(self.device).eval()
            self.backend = "superpoint_lightglue"
        except Exception as e:
            warnings.warn(
                f"[SuperPointLightGlueMatcher] Could not load deep matcher weights "
                f"({type(e).__name__}: {e}). Falling back to SIFT baseline. "
                f"This is expected in network-restricted environments — on your "
                f"own machine with internet access, this should load automatically. "
                f"See scripts/download_weights.md."
            )
            self.backend = "sift-fallback"

    def match(self, source: np.ndarray, reference: np.ndarray) -> MatchResult:
        if self.backend == "sift-fallback":
            result = match_sift(source, reference)
            return MatchResult(result.keypoints_source, result.keypoints_reference,
                                result.match_confidences, "sift-fallback")
        try:
            return self._match_real(source, reference)
        except Exception as e:
            # KNOWN OPEN ITEM (see README "Test log" section): kornia's
            # LightGlueMatcher expects keypoints in LAF format
            # (kornia.feature.laf_from_center_scale_ori), not the raw Nx2
            # arrays DISK's .keypoints attribute provides directly. Weight
            # download/loading works correctly (confirmed in testing) — this
            # is a remaining API wiring task, not a missing-weights problem.
            # Falls back safely to SIFT so the rest of the pipeline (RANSAC,
            # sub-pixel refinement, evaluation) is never blocked by this.
            warnings.warn(
                f"[SuperPointLightGlueMatcher] Real matcher failed at runtime "
                f"({type(e).__name__}: {e}). Falling back to SIFT for this call. "
                f"See README 'Test log' section for the exact fix needed."
            )
            result = match_sift(source, reference)
            return MatchResult(result.keypoints_source, result.keypoints_reference,
                                result.match_confidences, "sift-fallback-runtime")

    def _match_real(self, source: np.ndarray, reference: np.ndarray) -> MatchResult:
        import torch
        import kornia.feature as KF

        def to_tensor(img):
            t = torch.from_numpy(img).float() / 255.0
            if t.ndim == 2:
                t = t.unsqueeze(0).unsqueeze(0)
                t = t.repeat(1, 3, 1, 1)  # DISK expects 3-channel input even for grayscale imagery
            return t.to(self.device)

        src_t = to_tensor(source)
        ref_t = to_tensor(reference)

        with torch.no_grad():
            # kornia's DISK returns a list of per-image DISKFeatures (batch dimension);
            # we pass one image at a time, so take element 0 of each.
            src_feats = self._extractor(src_t)[0]
            ref_feats = self._extractor(ref_t)[0]

            if src_feats.keypoints.shape[0] < 2 or ref_feats.keypoints.shape[0] < 2:
                raise RuntimeError("DISK found fewer than 2 keypoints in one of the images")

            # FIX (previously the known bug documented above): LightGlueMatcher
            # requires keypoints wrapped as LAFs of shape (1, N, 2, 3), not the
            # raw (N, 2) tensors DISK's .keypoints attribute exposes directly.
            # DISK doesn't provide scale/orientation, so we use kornia's helper
            # with defaults (scale=1, orientation=0) — LightGlue only actually
            # *needs* the keypoint centers out of the LAF (see get_laf_center
            # inside LightGlueMatcher.forward), so this is a correct, not a
            # lossy, conversion for our purposes.
            lafs_src = KF.laf_from_center_scale_ori(src_feats.keypoints.unsqueeze(0))
            lafs_ref = KF.laf_from_center_scale_ori(ref_feats.keypoints.unsqueeze(0))

            h_s, w_s = source.shape[:2]
            h_r, w_r = reference.shape[:2]

            dists, idxs = self._matcher(
                src_feats.descriptors, ref_feats.descriptors,
                lafs_src, lafs_ref,
                hw1=(h_s, w_s), hw2=(h_r, w_r),
            )

        if idxs.shape[0] == 0:
            raise RuntimeError("LightGlue returned zero matches")

        pts_src = src_feats.keypoints[idxs[:, 0]].cpu().numpy()
        pts_ref = ref_feats.keypoints[idxs[:, 1]].cpu().numpy()
        confidences = dists.cpu().numpy().flatten()

        return MatchResult(pts_src, pts_ref, confidences, "superpoint_lightglue")


def match_superpoint_lightglue(source: np.ndarray, reference: np.ndarray, device: str = "cpu") -> MatchResult:
    matcher = SuperPointLightGlueMatcher(device=device)
    return matcher.match(source, reference)