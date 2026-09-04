import { useContext } from 'react';
import { MissionContext } from './MissionContextValue';

export function useMission() {
  const context = useContext(MissionContext);
  if (context === undefined) {
    throw new Error('useMission must be used within a MissionProvider');
  }
  return context;
}
