"""Phase 11.2 metadata quality assessment for UnknownImage inputs.

This module assesses the completeness, validity, and internal consistency of the
Phase 11.1 `UnknownImage` contract. It does not localize the image, estimate
coordinates, or perform any later-stage Phase 11 algorithm.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from enum import Enum
from typing import Any, Dict, Iterable, Optional

from .provenance import DataProvenance
from .unknown_image import UnknownImage, UnknownImageReferenceType


class FieldAssessmentStatus(str, Enum):
    PRESENT_VALID = "present_valid"
    MISSING = "missing"
    INVALID = "invalid"
    UNKNOWN = "unknown"
    LIMITED = "limited"


class MetadataAssessmentStatus(str, Enum):
    METADATA_VALID = "metadata_valid"
    METADATA_PARTIAL = "metadata_partial"
    METADATA_INSUFFICIENT = "metadata_insufficient"
    METADATA_INVALID = "metadata_invalid"
    METADATA_UNKNOWN = "metadata_unknown"


@dataclass(frozen=True)
class FieldAssessment:
    field_name: str
    status: FieldAssessmentStatus
    message: str = ""
    value_summary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "field_name": self.field_name,
            "status": self.status.value,
            "message": self.message,
            "value_summary": self.value_summary,
        }
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FieldAssessment":
        if not isinstance(payload, dict):
            raise ValueError("FieldAssessment payload must be a dictionary.")
        return cls(
            field_name=str(payload.get("field_name", "unknown_field")),
            status=FieldAssessmentStatus(payload["status"]),
            message=str(payload.get("message", "")),
            value_summary=payload.get("value_summary"),
        )


@dataclass(frozen=True)
class MetadataQualityResult:
    image_id: str
    assessment_status: MetadataAssessmentStatus
    completeness_status: str
    completeness_score: float
    field_assessments: Dict[str, FieldAssessment]
    warnings: tuple[str, ...]
    limitations: tuple[str, ...]
    provenance: DataProvenance
    source_contract: str = "UnknownImage"
    source_contract_version: str = "11.1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "assessment_status": self.assessment_status.value,
            "completeness_status": self.completeness_status,
            "completeness_score": self.completeness_score,
            "field_assessments": {key: value.to_dict() for key, value in self.field_assessments.items()},
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "provenance": self.provenance.value,
            "source_contract": self.source_contract,
            "source_contract_version": self.source_contract_version,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "MetadataQualityResult":
        if not isinstance(payload, dict):
            raise ValueError("MetadataQualityResult payload must be a dictionary.")
        field_payloads = payload.get("field_assessments", {})
        if not isinstance(field_payloads, dict):
            raise ValueError("field_assessments must be a dictionary.")
        fields = {
            key: FieldAssessment.from_dict(value)
            for key, value in field_payloads.items()
        }
        return cls(
            image_id=str(payload["image_id"]),
            assessment_status=MetadataAssessmentStatus(payload["assessment_status"]),
            completeness_status=str(payload["completeness_status"]),
            completeness_score=float(payload["completeness_score"]),
            field_assessments=fields,
            warnings=tuple(payload.get("warnings", ())),
            limitations=tuple(payload.get("limitations", ())),
            provenance=DataProvenance(payload["provenance"]),
            source_contract=str(payload.get("source_contract", "UnknownImage")),
            source_contract_version=str(payload.get("source_contract_version", "11.1")),
        )


def _finite_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("numeric value required")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("numeric value must be finite")
    return number


def _parse_iso_date(value: str) -> Optional[datetime]:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("date value required")
    candidate = value.strip()
    try:
        if "T" in candidate or " " in candidate:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        return datetime.strptime(candidate, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("invalid date string") from exc


def _safe_summary(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value[:60]
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        return f"dict:{len(value)} entries"
    if isinstance(value, (list, tuple)):
        return f"seq:{len(value)} items"
    return type(value).__name__


def _field_status_from_value(field_name: str, value: Any, *, allow_none: bool = False, kind: str = "generic") -> FieldAssessmentStatus:
    if value is None:
        return FieldAssessmentStatus.MISSING if not allow_none else FieldAssessmentStatus.UNKNOWN
    if kind == "numeric":
        try:
            _finite_number(value)
        except ValueError:
            return FieldAssessmentStatus.INVALID
        return FieldAssessmentStatus.PRESENT_VALID
    if kind == "mapping":
        if not isinstance(value, dict):
            return FieldAssessmentStatus.INVALID
        return FieldAssessmentStatus.PRESENT_VALID
    if kind == "image_reference":
        if not isinstance(value, str) or not value.strip():
            return FieldAssessmentStatus.INVALID
        return FieldAssessmentStatus.PRESENT_VALID
    if kind == "bool":
        if isinstance(value, bool):
            return FieldAssessmentStatus.PRESENT_VALID
        return FieldAssessmentStatus.INVALID
    if kind == "string":
        if not isinstance(value, str) or not value.strip():
            return FieldAssessmentStatus.INVALID
        return FieldAssessmentStatus.PRESENT_VALID
    return FieldAssessmentStatus.PRESENT_VALID


def _assess_reference_fields(image: UnknownImage) -> Dict[str, FieldAssessment]:
    assessments: Dict[str, FieldAssessment] = {}

    image_reference_status = FieldAssessmentStatus.PRESENT_VALID
    if not isinstance(image.image_reference, str) or not image.image_reference.strip():
        image_reference_status = FieldAssessmentStatus.INVALID
    assessments["image_reference"] = FieldAssessment(
        field_name="image_reference",
        status=image_reference_status,
        message="Reference string is present and valid for metadata assessment" if image_reference_status == FieldAssessmentStatus.PRESENT_VALID else "image_reference must be a non-empty string.",
        value_summary=_safe_summary(image.image_reference),
    )

    ref_type = image.image_reference_type
    if ref_type is UnknownImageReferenceType.UNKNOWN:
        status = FieldAssessmentStatus.UNKNOWN
        message = "Reference type is unknown; no safe classification is available."
    elif ref_type is UnknownImageReferenceType.INVALID:
        status = FieldAssessmentStatus.INVALID
        message = "Reference type is invalid or malformed."
    else:
        status = FieldAssessmentStatus.PRESENT_VALID
        message = "Reference type is explicitly recorded."
    assessments["image_reference_type"] = FieldAssessment(
        field_name="image_reference_type",
        status=status,
        message=message,
        value_summary=ref_type.value if ref_type is not None else None,
    )

    if image.local_path is None:
        assessments["local_path"] = FieldAssessment("local_path", FieldAssessmentStatus.MISSING, "No local path supplied.")
    elif not image.local_path.strip():
        assessments["local_path"] = FieldAssessment("local_path", FieldAssessmentStatus.INVALID, "local_path is blank.")
    elif ref_type is UnknownImageReferenceType.LOCAL_AVAILABLE:
        assessments["local_path"] = FieldAssessment("local_path", FieldAssessmentStatus.PRESENT_VALID, "Local path is present and explicitly associated with a local image.")
    elif ref_type is UnknownImageReferenceType.LOCAL_MISSING:
        assessments["local_path"] = FieldAssessment("local_path", FieldAssessmentStatus.PRESENT_VALID, "Local path is explicitly recorded as missing.")
    else:
        assessments["local_path"] = FieldAssessment("local_path", FieldAssessmentStatus.MISSING, "Local path is not required for this reference mode.")

    if image.external_reference is None:
        assessments["external_reference"] = FieldAssessment("external_reference", FieldAssessmentStatus.MISSING, "No external reference supplied.")
    elif not image.external_reference.strip():
        assessments["external_reference"] = FieldAssessment("external_reference", FieldAssessmentStatus.INVALID, "external_reference is blank.")
    elif ref_type is UnknownImageReferenceType.EXTERNAL_REFERENCE:
        assessments["external_reference"] = FieldAssessment("external_reference", FieldAssessmentStatus.PRESENT_VALID, "External reference is explicitly recorded.")
    else:
        assessments["external_reference"] = FieldAssessment("external_reference", FieldAssessmentStatus.MISSING, "External reference is not required for this mode.")

    return assessments


def _assess_provenance_fields(image: UnknownImage) -> Dict[str, FieldAssessment]:
    assessments: Dict[str, FieldAssessment] = {}

    provenance = image.provenance
    if provenance is DataProvenance.UNAVAILABLE:
        status = FieldAssessmentStatus.UNKNOWN
        message = "Provenance is unavailable; no real-data origin is established."
    else:
        status = FieldAssessmentStatus.PRESENT_VALID
        message = "Provenance is explicitly recorded."
    assessments["provenance"] = FieldAssessment("provenance", status, message, provenance.value)

    if not image.provenance_source or not image.provenance_source.strip():
        assessments["provenance_source"] = FieldAssessment("provenance_source", FieldAssessmentStatus.MISSING, "No provenance source record was provided.")
    else:
        assessments["provenance_source"] = FieldAssessment("provenance_source", FieldAssessmentStatus.PRESENT_VALID, "Provenance source is recorded.", image.provenance_source)

    if image.is_real_data is True and provenance is not DataProvenance.REAL:
        assessments["is_real_data"] = FieldAssessment("is_real_data", FieldAssessmentStatus.INVALID, "is_real_data=True contradicts the provenance value.")
    elif image.is_real_data is False and provenance is DataProvenance.REAL:
        assessments["is_real_data"] = FieldAssessment("is_real_data", FieldAssessmentStatus.INVALID, "REAL provenance requires is_real_data=True.")
    else:
        assessments["is_real_data"] = FieldAssessment("is_real_data", FieldAssessmentStatus.PRESENT_VALID, "is_real_data is consistent with the provenance record.", str(image.is_real_data))

    return assessments


def _assess_generic_fields(image: UnknownImage) -> Dict[str, FieldAssessment]:
    assessments: Dict[str, FieldAssessment] = {}
    fields = {
        "image_id": (image.image_id, "string"),
        "source_id": (image.source_id, "string"),
        "product_id": (image.product_id, "string"),
        "width": (image.width, "numeric"),
        "height": (image.height, "numeric"),
        "channels": (image.channels, "numeric"),
        "image_format": (image.image_format, "string"),
        "dtype": (image.dtype, "string"),
        "bit_depth": (image.bit_depth, "numeric"),
        "gsd_m": (image.gsd_m, "numeric"),
        "crs": (image.crs, "string"),
        "geospatial_reference": (image.geospatial_reference, "mapping"),
        "footprint": (image.footprint, "mapping"),
        "acquisition_timestamp": (image.acquisition_timestamp, "string"),
        "acquisition_date": (image.acquisition_date, "string"),
        "sensor": (image.sensor, "string"),
        "source_name": (image.source_name, "string"),
        "illumination": (image.illumination, "mapping"),
        "view_geometry": (image.view_geometry, "mapping"),
        "metadata_coordinates": (image.metadata_coordinates, "mapping"),
        "metadata_quality": (image.metadata_quality, "string"),
        "validation_status": (image.validation_status, "string"),
    }

    for field_name, (value, kind) in fields.items():
        if value is None:
            assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.MISSING, "Field is absent from the image metadata.")
            continue
        if kind == "string":
            if not isinstance(value, str) or not value.strip():
                assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.INVALID, "Field is not a non-empty string.")
            else:
                assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.PRESENT_VALID, "Field is present and valid.", value)
        elif kind == "numeric":
            try:
                number = _finite_number(value)
                if number <= 0:
                    raise ValueError
                assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.PRESENT_VALID, "Field is present and positive.", str(number))
            except ValueError:
                assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.INVALID, "Field is present but invalid or non-positive.", _safe_summary(value))
        elif kind == "mapping":
            if not isinstance(value, dict) or not value:
                assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.INVALID, "Field is present but not a valid mapping.", _safe_summary(value))
            else:
                assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.PRESENT_VALID, "Field is present and structurally valid.", f"dict:{len(value)} entries")
        else:
            assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.PRESENT_VALID, "Field is present.", _safe_summary(value))

    if image.image_id is not None and not image.image_id.strip():
        assessments["image_id"] = FieldAssessment("image_id", FieldAssessmentStatus.INVALID, "image_id is blank.")

    return assessments


def _assess_timestamps(image: UnknownImage, assessments: Dict[str, FieldAssessment]) -> None:
    timestamp = image.acquisition_timestamp
    if timestamp is None:
        assessments["acquisition_timestamp"] = FieldAssessment("acquisition_timestamp", FieldAssessmentStatus.MISSING, "acquisition_timestamp is absent.")
    else:
        try:
            dt = _parse_iso_date(timestamp)
        except ValueError:
            assessments["acquisition_timestamp"] = FieldAssessment("acquisition_timestamp", FieldAssessmentStatus.INVALID, "acquisition_timestamp is not parseable ISO-8601 metadata.")
        else:
            status = FieldAssessmentStatus.PRESENT_VALID if dt.tzinfo is not None else FieldAssessmentStatus.LIMITED
            message = "acquisition_timestamp is parseable and timezone-aware." if status == FieldAssessmentStatus.PRESENT_VALID else "acquisition_timestamp is parseable but timezone-naive; precision is limited."
            assessments["acquisition_timestamp"] = FieldAssessment("acquisition_timestamp", status, message, timestamp)

    date_value = image.acquisition_date
    if date_value is None:
        assessments["acquisition_date"] = FieldAssessment("acquisition_date", FieldAssessmentStatus.MISSING, "acquisition_date is absent.")
    else:
        try:
            _parse_iso_date(date_value)
        except ValueError:
            assessments["acquisition_date"] = FieldAssessment("acquisition_date", FieldAssessmentStatus.INVALID, "acquisition_date is not valid ISO date metadata.")
        else:
            assessments["acquisition_date"] = FieldAssessment("acquisition_date", FieldAssessmentStatus.PRESENT_VALID, "acquisition_date is parseable.", date_value)

    if timestamp is not None and date_value is not None:
        try:
            ts_dt = _parse_iso_date(timestamp)
            date_dt = _parse_iso_date(date_value)
            if ts_dt is not None and date_dt is not None and ts_dt.date() != date_dt.date():
                assessments["acquisition_date"] = FieldAssessment("acquisition_date", FieldAssessmentStatus.INVALID, "acquisition_date and acquisition_timestamp disagree.")
                assessments["acquisition_timestamp"] = FieldAssessment("acquisition_timestamp", FieldAssessmentStatus.LIMITED, "acquisition_timestamp is present but conflicts with acquisition_date.")
        except ValueError:
            pass


def _assess_illumination_and_geometry(image: UnknownImage, assessments: Dict[str, FieldAssessment]) -> None:
    for field_name in ("illumination", "view_geometry"):
        value = getattr(image, field_name)
        if value is None:
            assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.MISSING, f"{field_name} is absent.")
            continue
        if not isinstance(value, dict) or not value:
            assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.INVALID, f"{field_name} is present but invalid.")
            continue
        if field_name == "illumination":
            valid_keys = {"sun_azimuth_deg", "sun_elevation_deg"}
            if not set(value).issubset(valid_keys):
                assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.LIMITED, "illumination contains metadata beyond the standard fields.")
                continue
            try:
                for key in valid_keys:
                    if key in value:
                        _finite_number(value[key])
                assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.PRESENT_VALID, "illumination fields are parseable numeric values.")
            except ValueError:
                assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.INVALID, "illumination contains a non-numeric or non-finite value.")
        else:
            for key in ("position_m", "target_m"):
                if key not in value:
                    continue
                vector = value[key]
                if isinstance(vector, dict):
                    if set(vector) < {"x", "y", "z"}:
                        assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.INVALID, f"{field_name}.{key} is incomplete.")
                        return
                    vector = [vector[axis] for axis in ("x", "y", "z")]
                if not isinstance(vector, (list, tuple)) or len(vector) != 3:
                    assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.INVALID, f"{field_name}.{key} is not a valid 3-vector.")
                    return
                try:
                    for coordinate in vector:
                        _finite_number(coordinate)
                except ValueError:
                    assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.INVALID, f"{field_name}.{key} contains non-finite values.")
                    return
            assessments[field_name] = FieldAssessment(field_name, FieldAssessmentStatus.PRESENT_VALID, "view_geometry is structurally valid.")


def _parity_status(field_name: str, value: Any) -> FieldAssessmentStatus:
    if value is None:
        return FieldAssessmentStatus.MISSING
    if field_name in {"width", "height", "channels", "bit_depth"}:
        try:
            if int(value) <= 0:
                return FieldAssessmentStatus.INVALID
        except (TypeError, ValueError):
            return FieldAssessmentStatus.INVALID
        return FieldAssessmentStatus.PRESENT_VALID
    if field_name == "gsd_m":
        try:
            if _finite_number(value) <= 0:
                return FieldAssessmentStatus.INVALID
        except ValueError:
            return FieldAssessmentStatus.INVALID
        return FieldAssessmentStatus.PRESENT_VALID
    return FieldAssessmentStatus.PRESENT_VALID


def _check_validity_constraints(image: UnknownImage) -> tuple[Dict[str, FieldAssessment], list[str], list[str]]:
    assessments = {}
    warnings: list[str] = []
    limitations: list[str] = []

    assessments.update(_assess_reference_fields(image))
    assessments.update(_assess_provenance_fields(image))
    assessments.update(_assess_generic_fields(image))
    _assess_timestamps(image, assessments)
    _assess_illumination_and_geometry(image, assessments)

    if image.metadata_coordinates is not None:
        coords = image.metadata_coordinates
        if not isinstance(coords, dict) or not coords:
            assessments["metadata_coordinates"] = FieldAssessment("metadata_coordinates", FieldAssessmentStatus.INVALID, "metadata_coordinates must be a non-empty dict when supplied.")
        else:
            try:
                for key in ("lon", "lat"):
                    if key in coords:
                        _finite_number(coords[key])
                assessments["metadata_coordinates"] = FieldAssessment("metadata_coordinates", FieldAssessmentStatus.PRESENT_VALID, "metadata_coordinates are structurally valid and metadata-only.")
            except ValueError:
                assessments["metadata_coordinates"] = FieldAssessment("metadata_coordinates", FieldAssessmentStatus.INVALID, "metadata_coordinates contain non-finite numeric values.")

    if image.footprint is not None:
        if not isinstance(image.footprint, dict) or not image.footprint:
            assessments["footprint"] = FieldAssessment("footprint", FieldAssessmentStatus.INVALID, "footprint is present but malformed.")
        else:
            bounds = image.footprint.get("bounds", image.footprint if {"west", "south", "east", "north"}.issubset(image.footprint) else None)
            if bounds is not None:
                try:
                    west = _finite_number(bounds.get("west"))
                    south = _finite_number(bounds.get("south"))
                    east = _finite_number(bounds.get("east"))
                    north = _finite_number(bounds.get("north"))
                    if east <= west or north <= south:
                        raise ValueError
                    assessments["footprint"] = FieldAssessment("footprint", FieldAssessmentStatus.PRESENT_VALID, "footprint bounds are finite and ordered.")
                except (AttributeError, TypeError, ValueError):
                    assessments["footprint"] = FieldAssessment("footprint", FieldAssessmentStatus.INVALID, "footprint bounds are malformed or logically inconsistent.")
            elif "coordinates" in image.footprint:
                coords = image.footprint["coordinates"]
                if not isinstance(coords, (list, tuple)) or not coords:
                    assessments["footprint"] = FieldAssessment("footprint", FieldAssessmentStatus.INVALID, "footprint coordinates are present but empty or malformed.")
                else:
                    assessments["footprint"] = FieldAssessment("footprint", FieldAssessmentStatus.PRESENT_VALID, "footprint coordinates are present and structurally valid.")
            else:
                assessments["footprint"] = FieldAssessment("footprint", FieldAssessmentStatus.INVALID, "footprint must include bounds or a non-empty coordinate container.")

    if image.crs is None:
        assessments["crs"] = FieldAssessment("crs", FieldAssessmentStatus.MISSING, "No CRS metadata was supplied.")
    elif not isinstance(image.crs, str) or not image.crs.strip():
        assessments["crs"] = FieldAssessment("crs", FieldAssessmentStatus.INVALID, "CRS value is blank or not a string.")
    else:
        assessments["crs"] = FieldAssessment("crs", FieldAssessmentStatus.PRESENT_VALID, "CRS is present and represented as a string.")

    if image.geospatial_reference is None:
        assessments["geospatial_reference"] = FieldAssessment("geospatial_reference", FieldAssessmentStatus.MISSING, "No geospatial reference metadata supplied.")
    elif not isinstance(image.geospatial_reference, dict) or not image.geospatial_reference:
        assessments["geospatial_reference"] = FieldAssessment("geospatial_reference", FieldAssessmentStatus.INVALID, "geospatial_reference is not a valid mapping.")
    else:
        assessments["geospatial_reference"] = FieldAssessment("geospatial_reference", FieldAssessmentStatus.PRESENT_VALID, "geospatial_reference is structurally valid.")

    if image.metadata_quality is None:
        assessments["metadata_quality"] = FieldAssessment("metadata_quality", FieldAssessmentStatus.MISSING, "No metadata quality description supplied.")
    elif not isinstance(image.metadata_quality, str) or not image.metadata_quality.strip():
        assessments["metadata_quality"] = FieldAssessment("metadata_quality", FieldAssessmentStatus.INVALID, "metadata_quality is blank or invalid.")
    else:
        assessments["metadata_quality"] = FieldAssessment("metadata_quality", FieldAssessmentStatus.PRESENT_VALID, "metadata_quality is a valid string.")

    if not isinstance(image.validation_status, str) or not image.validation_status.strip():
        assessments["validation_status"] = FieldAssessment("validation_status", FieldAssessmentStatus.INVALID, "validation_status must be a non-empty string.")
    else:
        assessments["validation_status"] = FieldAssessment("validation_status", FieldAssessmentStatus.PRESENT_VALID, "validation_status is present and valid.")

    # Cross-field consistency checks.
    if image.width is not None and image.height is not None:
        if int(image.width) <= 0 or int(image.height) <= 0:
            warnings.append("invalid_dimension_values")
            assessments["width"] = FieldAssessment("width", FieldAssessmentStatus.INVALID, "width or height is invalid or non-positive.")
            assessments["height"] = FieldAssessment("height", FieldAssessmentStatus.INVALID, "width or height is invalid or non-positive.")

    if image.acquisition_timestamp is not None and image.acquisition_date is not None:
        try:
            ts_dt = _parse_iso_date(image.acquisition_timestamp)
            date_dt = _parse_iso_date(image.acquisition_date)
            if ts_dt is not None and date_dt is not None and ts_dt.date() != date_dt.date():
                warnings.append("acquisition_date_timestamp_conflict")
                limitations.append("Date and timestamp disagree; the acquisition record is limited for downstream interpretation.")
        except ValueError:
            pass

    if image.metadata_coordinates is not None and image.gsd_m is not None and image.crs is None:
        warnings.append("coordinates_present_without_crs")
        limitations.append("Metadata coordinates exist without a CRS, so they remain metadata-only.")

    if image.provenance is DataProvenance.UNAVAILABLE and image.is_real_data:
        warnings.append("real_data_flag_without_provenance")
        assessments["is_real_data"] = FieldAssessment("is_real_data", FieldAssessmentStatus.INVALID, "is_real_data=True requires REAL provenance.")

    if image.provenance is DataProvenance.REAL and not image.is_real_data:
        warnings.append("real_provenance_without_real_flag")
        assessments["is_real_data"] = FieldAssessment("is_real_data", FieldAssessmentStatus.INVALID, "REAL provenance requires is_real_data=True.")

    if image.image_reference_type is UnknownImageReferenceType.LOCAL_AVAILABLE and not image.local_path:
        warnings.append("local_available_reference_missing_path")
        assessments["local_path"] = FieldAssessment("local_path", FieldAssessmentStatus.INVALID, "LOCAL_AVAILABLE requires a local path.")

    if image.image_reference_type is UnknownImageReferenceType.EXTERNAL_REFERENCE and not image.external_reference:
        warnings.append("external_reference_missing_url")
        assessments["external_reference"] = FieldAssessment("external_reference", FieldAssessmentStatus.INVALID, "EXTERNAL_REFERENCE requires an external reference.")

    return assessments, warnings, limitations


def assess_metadata_quality(image: UnknownImage) -> MetadataQualityResult:
    """Assess the completeness and validity of the metadata in an UnknownImage record.

    The function does not localize the image, estimate coordinates, or infer any
    missing spatial facts. It only evaluates the metadata contract as supplied.
    """
    if not isinstance(image, UnknownImage):
        raise TypeError("assess_metadata_quality requires an UnknownImage instance.")

    field_assessments, warnings, limitations = _check_validity_constraints(image)
    inherited_warnings = tuple(image.warnings) if isinstance(image.warnings, (list, tuple)) else ()
    warnings = list(dict.fromkeys([*inherited_warnings, *warnings]))
    limitations = list(dict.fromkeys(limitations))
    if warnings and not limitations:
        limitations.append("Metadata warnings indicate reduced confidence for downstream interpretation.")

    invalid_statuses = [
        assessment.status for assessment in field_assessments.values()
        if assessment.status is FieldAssessmentStatus.INVALID
    ]
    unknown_statuses = [
        assessment.status for assessment in field_assessments.values()
        if assessment.status is FieldAssessmentStatus.UNKNOWN
    ]
    limited_statuses = [
        assessment.status for assessment in field_assessments.values()
        if assessment.status is FieldAssessmentStatus.LIMITED
    ]

    weighted = []
    for assessment in field_assessments.values():
        if assessment.status is FieldAssessmentStatus.PRESENT_VALID:
            weighted.append(1.0)
        elif assessment.status is FieldAssessmentStatus.LIMITED:
            weighted.append(0.5)
        elif assessment.status in {FieldAssessmentStatus.UNKNOWN, FieldAssessmentStatus.MISSING}:
            weighted.append(0.0)
        elif assessment.status is FieldAssessmentStatus.INVALID:
            weighted.append(0.0)
    completeness_score = (sum(weighted) / len(weighted)) if weighted else 0.0
    completeness_score = round(completeness_score, 4)

    if invalid_statuses:
        overall_status = MetadataAssessmentStatus.METADATA_INVALID
        completeness_status = "insufficient"
    elif not weighted:
        overall_status = MetadataAssessmentStatus.METADATA_UNKNOWN
        completeness_status = "unknown"
    elif completeness_score >= 0.8:
        overall_status = MetadataAssessmentStatus.METADATA_VALID
        completeness_status = "complete"
    elif completeness_score >= 0.5:
        overall_status = MetadataAssessmentStatus.METADATA_PARTIAL
        completeness_status = "partial"
    elif unknown_statuses and not invalid_statuses:
        overall_status = MetadataAssessmentStatus.METADATA_UNKNOWN
        completeness_status = "unknown"
    elif limited_statuses and not invalid_statuses:
        overall_status = MetadataAssessmentStatus.METADATA_INSUFFICIENT
        completeness_status = "limited"
    else:
        overall_status = MetadataAssessmentStatus.METADATA_INSUFFICIENT
        completeness_status = "minimal"

    result = MetadataQualityResult(
        image_id=image.image_id,
        assessment_status=overall_status,
        completeness_status=completeness_status,
        completeness_score=completeness_score,
        field_assessments=field_assessments,
        warnings=tuple(warnings),
        limitations=tuple(limitations),
        provenance=image.provenance,
    )
    return result


__all__ = [
    "FieldAssessment",
    "FieldAssessmentStatus",
    "MetadataAssessmentStatus",
    "MetadataQualityResult",
    "assess_metadata_quality",
]
