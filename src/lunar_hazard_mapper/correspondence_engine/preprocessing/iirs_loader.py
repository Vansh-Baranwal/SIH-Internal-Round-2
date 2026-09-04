"""
Stage A (new): IIRS Hyperspectral Loading & Composite Generation.

IIRS data is fundamentally different from TMC/OHRC -- a cube of many
wavelength bands per pixel, not a normal grayscale/RGB image. Rather than
rewriting the entire correspondence engine to understand hyperspectral data
natively, this module converts an IIRS cube into a synthetic grayscale
composite (by averaging a handful of bands) that LOOKS enough like a normal
image to feed directly into the EXISTING, already-tested pipeline unchanged
-- the same approach outlined in the project's own IIRS feature planning.

This is the correct architectural choice: register the composite against
TMC/OHRC using the proven engine, then (separately, downstream) map the full
spectral cube onto the registered footprint for actual mineral/hydration
analysis -- registration accuracy and spectral analysis are different
concerns and shouldn't be tangled into one code path.
"""
from __future__ import annotations
import numpy as np
import xml.etree.ElementTree as ET
from pathlib import Path
from dataclasses import dataclass


PDS_NS = {
    "pds": "http://pds.nasa.gov/pds4/pds/v1",
    "hs": "http://pds.nasa.gov/pds4/hs/v1",
}


@dataclass
class IIRSCubeInfo:
    lines: int
    samples: int
    bands: int
    data_type: str
    data_offset: int
    band_interleave: str  # "BSQ", "BIL", or "BIP"
    file_name: str | None


def parse_iirs_label(xml_path: str) -> IIRSCubeInfo:
    """
    Parses an IIRS PDS4 label to get cube dimensions. Same PDS4 namespace
    pattern as inspect_real_data.py's TMC/OHRC parser -- IIRS labels use an
    Array_3D_Spectrum (or similar 3D array element) instead of Array_2D_Image,
    since there's a band dimension in addition to line/sample.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    array_node = root.find(".//pds:File_Area_Observational/pds:Array_3D_Spectrum", namespaces=PDS_NS)
    if array_node is None:
        # some IIRS products describe it as a generic Array_3D instead
        array_node = root.find(".//pds:File_Area_Observational/pds:Array_3D", namespaces=PDS_NS)
    if array_node is None:
        raise ValueError(
            f"Could not find a 3D array element in {xml_path}. "
            f"This may be a 2D-only IIRS product (e.g. a single-band browse "
            f"image) rather than the full hyperspectral cube -- check the "
            f"product type before assuming this loader applies."
        )

    lines = samples = bands = None
    interleave = "BSQ"  # PDS4 default assumption unless stated otherwise
    for axis in array_node.findall("pds:Axis_Array", namespaces=PDS_NS):
        name = axis.find("pds:axis_name", namespaces=PDS_NS).text.lower()
        n = int(axis.find("pds:elements", namespaces=PDS_NS).text)
        if name == "line":
            lines = n
        elif name == "sample":
            samples = n
        elif name == "band":
            bands = n

    offset_node = array_node.find("pds:offset", namespaces=PDS_NS)
    offset = int(offset_node.text) if offset_node is not None else 0

    el = array_node.find("pds:Element_Array", namespaces=PDS_NS)
    data_type = el.find("pds:data_type", namespaces=PDS_NS).text if el is not None else "UnsignedLSB2"

    file_node = root.find(".//pds:File_Area_Observational/pds:File", namespaces=PDS_NS)
    file_name = file_node.find("pds:file_name", namespaces=PDS_NS).text if file_node is not None else None

    if lines is None or samples is None or bands is None:
        raise ValueError(f"Missing line/sample/band dimensions in {xml_path} -- can't determine cube shape.")

    return IIRSCubeInfo(lines, samples, bands, data_type, offset, interleave, file_name)


def _pds_dtype(data_type: str) -> np.dtype:
    type_map = {
        "UnsignedMSB2": np.dtype(">u2"), "UnsignedLSB2": np.dtype("<u2"),
        "SignedMSB2": np.dtype(">i2"), "SignedLSB2": np.dtype("<i2"),
        "UnsignedByte": np.dtype("u1"),
        "IEEE754MSBSingle": np.dtype(">f4"), "IEEE754LSBSingle": np.dtype("<f4"),
    }
    return type_map.get(data_type, np.dtype("<u2"))


def load_iirs_cube(qub_path: str, info: IIRSCubeInfo) -> np.ndarray:
    """
    Loads the raw hyperspectral cube from disk. Returns array shaped
    (bands, lines, samples) regardless of the file's native interleave, so
    downstream code always sees a consistent shape.
    """
    dtype = _pds_dtype(info.data_type)
    with open(qub_path, "rb") as f:
        f.seek(info.data_offset)
        raw = np.fromfile(f, dtype=dtype, count=info.lines * info.samples * info.bands)

    if info.band_interleave == "BSQ":
        cube = raw.reshape(info.bands, info.lines, info.samples)
    elif info.band_interleave == "BIL":
        cube = raw.reshape(info.lines, info.bands, info.samples).transpose(1, 0, 2)
    elif info.band_interleave == "BIP":
        cube = raw.reshape(info.lines, info.samples, info.bands).transpose(2, 0, 1)
    else:
        raise ValueError(f"unknown interleave: {info.band_interleave}")

    return cube


def make_grayscale_composite(cube: np.ndarray, band_indices: list[int] | None = None) -> np.ndarray:
    """
    Averages a handful of bands (default: a few near the visible/NIR range,
    where structure is most photograph-like) into a single grayscale image
    that resembles a normal optical photo closely enough for the existing
    SIFT/AKAZE/LoFTR matchers to find real structural features (crater rims
    etc.) in it -- exactly as outlined in the IIRS overlay feature plan.

    band_indices: which band indices to average. If None, uses the middle
    third of the available bands as a reasonable visible/NIR-ish default --
    override with real band-to-wavelength info from the label if precision
    matters for your specific use case.
    """
    n_bands = cube.shape[0]
    if band_indices is None:
        start, end = n_bands // 3, 2 * n_bands // 3
        band_indices = list(range(start, end))

    composite = cube[band_indices].astype(np.float32).mean(axis=0)
    normalized = 255 * (composite - composite.min()) / (composite.max() - composite.min() + 1e-6)
    return normalized.astype(np.uint8)


def prepare_iirs_for_registration(xml_path: str, qub_path: str | None = None,
                                   band_indices: list[int] | None = None) -> np.ndarray:
    """
    Main entry point: given an IIRS PDS4 label (and optionally an explicit
    cube file path), returns a grayscale composite ready to feed directly
    into the existing correspondence engine pipeline as a normal source/
    reference image -- e.g.:

        composite = prepare_iirs_for_registration(xml_path)
        Image.fromarray(composite).save("iirs_composite.png")
        # then: python -m ...registration.pipeline --source iirs_composite.png --reference tmc_crop.png ...
    """
    info = parse_iirs_label(xml_path)

    if qub_path is None:
        qub_path = str(Path(xml_path).with_suffix(".qub"))
        if not Path(qub_path).exists():
            qub_path = str(Path(xml_path).with_suffix(".img"))
        if not Path(qub_path).exists() and info.file_name:
            candidate = Path(xml_path).parent / info.file_name
            if candidate.exists():
                qub_path = str(candidate)

    if not Path(qub_path).exists():
        raise FileNotFoundError(f"Could not find IIRS cube file at {qub_path}. Pass qub_path explicitly.")

    cube = load_iirs_cube(qub_path, info)
    return make_grayscale_composite(cube, band_indices)