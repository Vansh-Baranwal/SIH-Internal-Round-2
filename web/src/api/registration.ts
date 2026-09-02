/**
 * Phase 13.4 — registration contract & capability seam.
 *
 * The real correspondence engine / registration endpoint is NOT implemented in
 * the backend for this build. This module is the single seam where the real
 * engine will be wired later, so the Registration Cockpit does not need to be
 * redesigned. No registration results, match points, RMSE or inlier metrics
 * are fabricated anywhere here.
 */

export type RegistrationSensor = 'tmc' | 'ohrc' | 'iirs';

export interface RegistrationPoint {
  x: number;
  y: number;
}

export interface RegistrationMatchPair {
  id?: string;
  source: RegistrationPoint;
  reference: RegistrationPoint;
}

export interface RegistrationMatchData {
  pairs: RegistrationMatchPair[];
  sourceLabel?: string;
  referenceLabel?: string;
}

export interface RegistrationRequest {
  sourceSensor: RegistrationSensor;
  referenceSensor: RegistrationSensor;
}

export type RegistrationOutcome =
  | { status: 'unavailable'; message: string }
  | { status: 'error'; message: string }
  | {
      status: 'success';
      registrationId: string;
      metrics: Record<string, unknown>;
      matches?: RegistrationMatchData | null;
    };

export interface RegistrationCapability {
  available: boolean;
  reason: string;
}

/**
 * The correspondence engine/model is not available in this build. Flip this to
 * `true` (and implement `submitRegistration`) when the real engine is wired.
 */
export const REGISTRATION_ENGINE_AVAILABLE = false;

export function getRegistrationCapability(): RegistrationCapability {
  return {
    available: REGISTRATION_ENGINE_AVAILABLE,
    reason:
      'The correspondence engine/model is not available in this build. Registration cannot be executed and no result is produced.',
  };
}

/**
 * Initiate registration through the backend contract.
 *
 * With the engine unavailable this returns an explicit `unavailable` outcome
 * rather than a fabricated success, so the UI never claims a result that does
 * not exist. When the real endpoint is connected, replace the body with a POST
 * to the registration endpoint and surface the genuine response.
 */
export async function submitRegistration(
  request: RegistrationRequest,
): Promise<RegistrationOutcome> {
  void request;
  return {
    status: 'unavailable',
    message:
      'Registration is not available: the correspondence engine/model is not implemented in this build. No result, match points or metrics were produced.',
  };
}
