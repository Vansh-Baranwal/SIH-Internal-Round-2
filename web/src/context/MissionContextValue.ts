import { createContext } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { RegistrationSession } from '../types/registration';

export type MissionContextType = {
  // Legacy state (unchanged shape/behavior)
  result: any;
  setResult: (data: any) => void;

  // Typed state for the multi-modal correspondence workflow.
  session: RegistrationSession;
  setSession: Dispatch<SetStateAction<RegistrationSession>>;
  resetSession: () => void;

  // Explicit hand-off from registration into the legacy mission pipeline.
  sendToMissionPipeline: (overlayImageUrl: string) => void;

  // Isolated hand-off from the digital twin into a fresh registration session.
  startCounterfactualSession: (capture: {
    dataUrl: string;
    azimuthDeg: number;
    elevationDeg: number;
  }) => void;
};

export const MissionContext = createContext<MissionContextType | undefined>(undefined);

