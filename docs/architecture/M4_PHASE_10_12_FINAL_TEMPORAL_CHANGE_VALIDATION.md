# M4 Phase 10.12: Final Temporal-Change Validation

## 1. Purpose

Phase 10.12 is the final deterministic gate for the M4 temporal-change evidence chain. It consumes the authoritative outputs from Phases 10.3 through 10.11 and decides whether the chain may be considered a valid temporal-change candidate under conservative, evidence-only rules.

This stage does not confirm a physical lunar process, geological interpretation, crater formation, ejecta deposition, impact event, or material change. It only decides whether the full evidence chain remained consistent and free of decisive false-positive evidence.

## 2. Pipeline position

The final gate sits after the upstream sequence:
- 10.1 observation contract
- 10.2 temporal metadata
- 10.3 pair selection
- 10.4 registration
- 10.5 differencing
- 10.6 illumination filtering
- 10.7 noise suppression
- 10.8 candidate detection
- 10.9 classification
- 10.10 crater/ejecta screening
- 10.11 false-positive validation

The implementation accepts the outputs of that chain without re-running upstream stages or inventing new evidence.

## 3. Scientific-integrity boundary

The stage intentionally enforces strict evidence requirements:
- real-data provenance only
- distinct observation timestamps
- eligible pair selection
- successful registration quality gate
- sufficient valid data fraction
- no decisive false-positive evidence
- no candidate-loss or chain inconsistency

A final positive status is not a claim that a crater, impact, ejecta deposit, or other event occurred. It is only the status label for an accepted evidence chain under the project’s conservative scientific protocol.

## 4. Valid statuses

The validator emits one of the following statuses:
- `VALIDATED_TEMPORAL_CHANGE`
- `REJECTED_FALSE_POSITIVE`
- `NO_CANDIDATES`
- `INCONCLUSIVE`
- `VALIDATION_BLOCKED`

These status names are intentionally scientific and conservative. They do not state any physical interpretation beyond the gate result itself.

## 5. Acceptance logic

The final gate performs deterministic checks in order:
1. real-data provenance and temporal distinctness
2. pair eligibility and registration quality thresholds
3. illumination and differencing reliability
4. noise suppression and candidate production
5. classification and specialized screening
6. false-positive validation with decisive evidence exclusion
7. final acceptance only if all required gates pass

If any upstream stage is missing, malformed, mismatched to the pair, or fails its gate, the final result shifts to `INCONCLUSIVE` or `VALIDATION_BLOCKED` rather than silently accepting the chain.

## 6. Guardrails

The implementation deliberately avoids:
- crater confirmation
- ejecta confirmation
- impact interpretation
- confidence/probability claims
- synthetic-data bypasses
- fabricated support evidence
- post hoc scientific narratives beyond the final gate status

## 7. Provenance and artifacts

The result retains provenance metadata documenting:
- phase label: `m4_10.12`
- upstream chain: `m4_10.7_to_m4_10.11`
- gate outcomes
- warnings and failure reasons
- scientific interpretation language describing the conservative boundary

## 8. Test coverage

The focused suite covers:
- accepted real-data evidence chain
- decisive false-positive rejection
- missing false-positive result handling
- same-timestamp or blocked pairs
- no-candidate outcome

## 9. Final status

Phase 10.12 is implemented as a conservative final gate for temporal-change acceptance. It ensures the project only emits a positive temporal-change result when the entire evidence chain is real, consistent, and free of decisive false-positive evidence.
