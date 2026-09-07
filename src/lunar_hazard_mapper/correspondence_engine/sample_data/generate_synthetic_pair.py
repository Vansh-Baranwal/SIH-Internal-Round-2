"""
Generates a synthetic "OHRC vs TMC"-like image pair for testing the full
pipeline before real Chandrayaan-2 data is wired in. Simulates:
  - a scale difference (source is higher-res crop, reference is a wider,
    lower-res view of a larger area containing the same features)
  - a simulated illumination difference (different synthetic "sun angle" shading)
  - shared crater-like features so matching has something real to find
"""
import numpy as np
from PIL import Image
import os
from scipy.ndimage import gaussian_filter


def generate_crater_scene(size: int, seed: int, n_craters: int = 12) -> np.ndarray:
    rng = np.random.default_rng(seed)
    scene = np.ones((size, size), dtype=np.float32) * 0.5

    craters = []
    for _ in range(n_craters):
        cx, cy = rng.integers(size // 10, size - size // 10, 2)
        r = rng.integers(size // 30, size // 8)
        craters.append((cx, cy, r))

    yy, xx = np.mgrid[0:size, 0:size]
    for cx, cy, r in craters:
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        rim = np.exp(-((dist - r) ** 2) / (2 * (r * 0.15) ** 2))
        floor = (dist < r * 0.8).astype(np.float32) * -0.15
        scene += rim.astype(np.float32) * 0.3 + floor

    scene += gaussian_filter(rng.normal(0, 0.02, scene.shape), sigma=2)
    return np.clip(scene, 0, 1), craters


def apply_synthetic_shading(scene: np.ndarray, craters: list, sun_angle_deg: float) -> np.ndarray:
    """Simulate crater shadows shifting direction based on a synthetic sun angle."""
    shaded = scene.copy()
    dx = np.cos(np.radians(sun_angle_deg))
    dy = np.sin(np.radians(sun_angle_deg))
    size = scene.shape[0]
    yy, xx = np.mgrid[0:size, 0:size]

    for cx, cy, r in craters:
        shadow_cx, shadow_cy = cx + dx * r * 0.5, cy + dy * r * 0.5
        dist = np.sqrt((xx - shadow_cx) ** 2 + (yy - shadow_cy) ** 2)
        shadow = np.exp(-((dist) ** 2) / (2 * (r * 0.6) ** 2)) * 0.2
        shaded -= shadow

    return np.clip(shaded, 0, 1)


def generate(out_dir: str = None, base_size: int = 800, crop_size: int = 400):
    out_dir = out_dir or os.path.dirname(__file__)
    os.makedirs(out_dir, exist_ok=True)

    # shared underlying scene (same "ground truth" terrain)
    full_scene, craters = generate_crater_scene(base_size, seed=7)

    # "reference" (TMC-like): full wide view, one sun angle, moderate resolution
    reference = apply_synthetic_shading(full_scene, craters, sun_angle_deg=30)
    reference_img = (reference * 255).astype(np.uint8)
    ref_path = os.path.join(out_dir, "reference_tmc_sim.png")
    Image.fromarray(reference_img).save(ref_path)

    # "source" (OHRC-like): higher-res crop of a sub-region, DIFFERENT sun angle
    x0, y0 = base_size // 4, base_size // 4
    crop = full_scene[y0:y0 + crop_size, x0:x0 + crop_size]
    crop_craters = [(cx - x0, cy - y0, r) for cx, cy, r in craters
                    if x0 <= cx <= x0 + crop_size and y0 <= cy <= y0 + crop_size]
    source_shaded = apply_synthetic_shading(crop, crop_craters, sun_angle_deg=110)  # different sun angle
    # upsample to simulate higher native resolution (adds interpolation texture)
    source_upsampled = np.array(Image.fromarray((source_shaded * 255).astype(np.uint8))
                                 .resize((crop_size * 2, crop_size * 2), Image.LANCZOS))
    src_path = os.path.join(out_dir, "source_ohrc_sim.png")
    Image.fromarray(source_upsampled).save(src_path)

    print(f"Saved reference (TMC-sim, wide view, sun=30deg) -> {ref_path}")
    print(f"Saved source (OHRC-sim, crop+upsampled, sun=110deg) -> {src_path}")
    print(f"NOTE: source is a sub-region of reference's coordinate space, scaled 2x,")
    print(f"      with a different simulated sun angle -- tests both scale AND")
    print(f"      illumination invariance simultaneously, similar to the real")
    print(f"      OHRC-vs-TMC challenge described in your planning docs.")

    return src_path, ref_path


if __name__ == "__main__":
    generate()
