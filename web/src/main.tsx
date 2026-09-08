import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MissionProvider } from './context/MissionContext';
import { DatasetSelectionProvider } from './context/DatasetSelectionProvider';
import { Layout } from './components/layout/Layout';
import { MissionControl } from './pages/MissionControl';
import { MultiSensor } from './pages/MultiSensor';
import { RegistrationCockpit } from './pages/RegistrationCockpit';
import { SpectralIntelligence } from './pages/SpectralIntelligence';
import { WaterIceIntelligence } from './pages/WaterIceIntelligence';
import { TemporalChange } from './pages/TemporalChange';
import { Landing } from './pages/Landing';
import { Registration } from './pages/Registration';
import { Imagery } from './pages/Imagery';
import { Terrain } from './pages/Terrain';
import { HazardMap } from './pages/HazardMap';
import { LandingSites } from './pages/LandingSites';
import { Trajectory } from './pages/Trajectory';
import { Simulation } from './pages/Simulation';
import MultiSensorCockpit from './pages/MultiSensorCockpit';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MissionProvider>
      <DatasetSelectionProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Landing />} />
            <Route path="dashboard" element={<MissionControl />} />
            <Route path="registration" element={<Registration />} />
            <Route path="imagery" element={<Imagery />} />
            <Route path="sensors" element={<MultiSensor />} />
            <Route path="terrain" element={<Terrain />} />
            <Route path="hazard-map" element={<HazardMap />} />
            <Route path="landing-sites" element={<LandingSites />} />
            <Route path="trajectory" element={<Trajectory />} />
            <Route path="simulation" element={<Simulation />} />
            <Route path="cockpit" element={<MultiSensorCockpit />} />
            <Route path="registration-cockpit" element={<RegistrationCockpit />} />
            <Route path="scientific" element={<SpectralIntelligence />} />
            <Route path="spectral" element={<SpectralIntelligence />} />
            <Route path="water-ice" element={<WaterIceIntelligence />} />
            <Route path="temporal" element={<TemporalChange />} />
            <Route path="digital-twin" element={<Simulation />} />
          </Route>
        </Routes>
      </BrowserRouter>
      </DatasetSelectionProvider>
    </MissionProvider>
  </React.StrictMode>,
);
