"""
M4-07.3 — Counterfactual Sun-Position Generation.

Deterministically generates alternative SunState configurations from a baseline
without simulating their effects on terrain.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from lunar_hazard_mapper.scientific.common.types import SunState


def _wrap_azimuth(azimuth_deg: float) -> float:
    """
    Wrap azimuth to [0, 360) range.

    Azimuth is circular; values outside this range wrap correctly.
    """
    azimuth = float(azimuth_deg)
    # Normalize to [0, 360)
    azimuth = azimuth % 360.0
    if azimuth < 0.0:
        azimuth += 360.0
    return azimuth


def _clamp_elevation(elevation_deg: float) -> Optional[float]:
    """
    Clamp elevation to [0, 90] range if possible, or return None if physically invalid.

    Elevation is NOT circular. If a requested elevation is outside [0, 90],
    return None to signal rejection.
    """
    elevation = float(elevation_deg)
    if elevation < 0.0 or elevation > 90.0:
        return None
    return elevation


def generate_counterfactual_sun_states(
    baseline: SunState,
    azimuth_offsets: Optional[Sequence[float]] = None,
    elevation_offsets: Optional[Sequence[float]] = None,
) -> Tuple[SunState, ...]:
    """
    Generate alternative SunState configurations from a baseline.

    Creates a deterministic sequence of counterfactual Sun positions by applying
    specified offsets to azimuth and/or elevation. The baseline is never mutated.

    Args:
        baseline: The base SunState from which to generate alternatives.
        azimuth_offsets: Sequence of azimuth offsets (in degrees) to apply.
                         If None, no azimuth variations are generated.
        elevation_offsets: Sequence of elevation offsets (in degrees) to apply.
                          If None, no elevation variations are generated.

    Returns:
        Tuple of generated SunState objects in deterministic order.
        If both azimuth_offsets and elevation_offsets are provided,
        elevation variations are applied to each azimuth variant.

    Raises:
        TypeError: if baseline is not a SunState, or if offsets are not sequences.
        ValueError: if any offset would result in an invalid SunState.
    """
    if not isinstance(baseline, SunState):
        raise TypeError("baseline must be a SunState instance.")

    # Convert inputs to lists for consistent ordering
    az_offsets = list(azimuth_offsets) if azimuth_offsets is not None else []
    el_offsets = list(elevation_offsets) if elevation_offsets is not None else []

    if not az_offsets and not el_offsets:
        raise ValueError(
            "At least one of azimuth_offsets or elevation_offsets must be provided."
        )

    generated = []

    # Apply azimuth offsets first (if any), then elevation offsets to each result
    if az_offsets and el_offsets:
        # Cross-product: each azimuth offset combined with each elevation offset
        for az_offset in az_offsets:
            new_az = _wrap_azimuth(baseline.azimuth_deg + float(az_offset))
            for el_offset in el_offsets:
                new_el = baseline.elevation_deg + float(el_offset)
                new_el_clamped = _clamp_elevation(new_el)
                if new_el_clamped is None:
                    raise ValueError(
                        f"Requested elevation {new_el:.1f}° is outside valid range [0, 90]. "
                        f"baseline elevation: {baseline.elevation_deg}°, "
                        f"offset: {el_offset}°"
                    )
                state = SunState(azimuth_deg=new_az, elevation_deg=new_el_clamped)
                generated.append(state)
    elif az_offsets:
        # Only azimuth offsets
        for az_offset in az_offsets:
            new_az = _wrap_azimuth(baseline.azimuth_deg + float(az_offset))
            state = SunState(azimuth_deg=new_az, elevation_deg=baseline.elevation_deg)
            generated.append(state)
    else:
        # Only elevation offsets
        for el_offset in el_offsets:
            new_el = baseline.elevation_deg + float(el_offset)
            new_el_clamped = _clamp_elevation(new_el)
            if new_el_clamped is None:
                raise ValueError(
                    f"Requested elevation {new_el:.1f}° is outside valid range [0, 90]. "
                    f"baseline elevation: {baseline.elevation_deg}°, "
                    f"offset: {el_offset}°"
                )
            state = SunState(azimuth_deg=baseline.azimuth_deg, elevation_deg=new_el_clamped)
            generated.append(state)

    # Deduplicate while preserving order
    seen = set()
    deduplicated = []
    for state in generated:
        state_tuple = state.as_tuple()
        if state_tuple not in seen:
            deduplicated.append(state)
            seen.add(state_tuple)

    if not deduplicated:
        raise ValueError(
            "Generation resulted in no valid, non-duplicate SunStates."
        )

    return tuple(deduplicated)


def generate_elevation_sweep(
    baseline: SunState,
    elevation_values: Sequence[float],
) -> Tuple[SunState, ...]:
    """
    Generate Sun positions at a fixed azimuth with varying elevations.

    Convenience function for sweeping elevation while keeping azimuth constant.

    Args:
        baseline: Base SunState (azimuth will be preserved).
        elevation_values: Explicit elevation values (in degrees) to use.
                         Each must be in [0, 90].

    Returns:
        Tuple of SunState objects with the baseline azimuth and specified elevations.

    Raises:
        TypeError: if baseline is not a SunState.
        ValueError: if any elevation value is outside [0, 90].
    """
    if not isinstance(baseline, SunState):
        raise TypeError("baseline must be a SunState instance.")

    states = []
    for el_value in elevation_values:
        el_value_float = float(el_value)
        if not 0.0 <= el_value_float <= 90.0:
            raise ValueError(
                f"Elevation {el_value_float}° is outside valid range [0, 90]."
            )
        state = SunState(azimuth_deg=baseline.azimuth_deg, elevation_deg=el_value_float)
        states.append(state)

    # Deduplicate while preserving order
    seen = set()
    deduplicated = []
    for state in states:
        state_tuple = state.as_tuple()
        if state_tuple not in seen:
            deduplicated.append(state)
            seen.add(state_tuple)

    if not deduplicated:
        raise ValueError("Elevation sweep resulted in no valid SunStates.")

    return tuple(deduplicated)


def generate_azimuth_sweep(
    baseline: SunState,
    azimuth_values: Sequence[float],
) -> Tuple[SunState, ...]:
    """
    Generate Sun positions at a fixed elevation with varying azimuths.

    Convenience function for sweeping azimuth while keeping elevation constant.

    Args:
        baseline: Base SunState (elevation will be preserved).
        azimuth_values: Explicit azimuth values (in degrees) to use.
                       Values in [0, 360) are preferred; others are wrapped.

    Returns:
        Tuple of SunState objects with specified azimuths and the baseline elevation.
    """
    if not isinstance(baseline, SunState):
        raise TypeError("baseline must be a SunState instance.")

    states = []
    for az_value in azimuth_values:
        az_value_wrapped = _wrap_azimuth(float(az_value))
        state = SunState(azimuth_deg=az_value_wrapped, elevation_deg=baseline.elevation_deg)
        states.append(state)

    # Deduplicate while preserving order
    seen = set()
    deduplicated = []
    for state in states:
        state_tuple = state.as_tuple()
        if state_tuple not in seen:
            deduplicated.append(state)
            seen.add(state_tuple)

    if not deduplicated:
        raise ValueError("Azimuth sweep resulted in no valid SunStates.")

    return tuple(deduplicated)
