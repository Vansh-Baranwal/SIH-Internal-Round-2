"""
Member 4 Counterfactual Sun Simulator.
"""

from .simulator import (
    CounterfactualSunSimulator,
    SunSimulationResult,
)

from .experiment import (
    SunAngleExperiment,
    SunAngleExperimentRunner,
    SunExperimentRecord,
)

from .export import (
    export_simulation_result,
)

from .visualization import (
    plot_simulation,
    plot_experiment,
)

from .scene import SunScene

from .counterfactual import (
    generate_counterfactual_sun_states,
    generate_elevation_sweep,
    generate_azimuth_sweep,
)

from .shadow import (
    SyntheticShadow,
    simulate_synthetic_shadow,
)

from .observation import (
    CounterfactualObservation,
    generate_counterfactual_observation,
)

from .invariance import (
    DEFAULT_CENTER_TOLERANCE_M,
    DEFAULT_GEOMETRY_TOLERANCE_FRAC,
    SunInvarianceConditionResult,
    SunInvarianceExperimentResult,
    run_sun_invariance_experiment,
)

from .landmark_matching import (
    LandmarkMatchRecord,
    SunConditionMatchingResult,
    SunLandmarkMatchingResult,
    match_landmarks_across_sun_conditions,
)

from .sensitivity import (
    SunSensitivityCondition,
    SunSensitivityResult,
    run_sun_position_sensitivity_experiment,
)


__all__ = [
    "CounterfactualSunSimulator",
    "SunSimulationResult",
    "SunAngleExperiment",
    "SunAngleExperimentRunner",
    "SunExperimentRecord",
    "export_simulation_result",
    "plot_simulation",
    "plot_experiment",
    "SunScene",
    "generate_counterfactual_sun_states",
    "generate_elevation_sweep",
    "generate_azimuth_sweep",
    "SyntheticShadow",
    "simulate_synthetic_shadow",
    "CounterfactualObservation",
    "generate_counterfactual_observation",
    "DEFAULT_CENTER_TOLERANCE_M",
    "DEFAULT_GEOMETRY_TOLERANCE_FRAC",
    "SunInvarianceConditionResult",
    "SunInvarianceExperimentResult",
    "run_sun_invariance_experiment",
    "LandmarkMatchRecord",
    "SunConditionMatchingResult",
    "SunLandmarkMatchingResult",
    "match_landmarks_across_sun_conditions",
    "SunSensitivityCondition",
    "SunSensitivityResult",
    "run_sun_position_sensitivity_experiment",
]