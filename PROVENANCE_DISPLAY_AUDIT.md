# Frontend Provenance Display Audit

**Date:** 2026-09-02  
**Scope:** Frontend codebase (`web/src/`) analysis of `data_status`, `provenance`, and `display_label` field usage and display

---

## Summary

| Category | Count | Status |
|----------|-------|--------|
| Components CURRENTLY displaying provenance | 5 | ✅ Active |
| Components SHOULD display but don't | 7 | ❌ Gap |
| API payloads with provenance fields | 10 | Defined |
| Pages rendering API payloads | 10 | Enumerated |

---

## 1. Components Currently Displaying Provenance/Data Status

### ✅ MultiSensor.tsx
**Location:** `web/src/pages/MultiSensor.tsx`

**Displays:**
- `dataset.displayLabel` - Dataset identifier
- `dataset.dataStatus` - 'synthetic' | 'real' | 'unknown'
- `dataset.provenance.note` - Human-readable note (extracted via `provenanceNote()`)

**Context:** Multi-sensor data selection page; shows metadata for TMC, OHRC, and IIRS datasets when selected
**Function:** `SensorMetadata()` component renders sensor details including provenance

```typescript
function provenanceNote(provenance: Record<string, unknown>): string {
  const note = provenance.note;
  return typeof note === 'string' ? note : '';
}
```

---

### ✅ SpectralIntelligence.tsx
**Location:** `web/src/pages/SpectralIntelligence.tsx`

**Displays:**
- **Top-level:**
  - `payload.display_label`
  - `payload.data_status`
  - `payload.provenance` (whole object)
  
- **Per-region:**
  - `region.display_label`
  - `region.data_status`
  - `region.provenance` (region-specific)

**Context:** Mineral analysis overlay viewer; renders spectral metadata and band regions
**Data Structure:** `SpectralWorkspaceData` contains both payload-level and region-level provenance
**Coverage:** Both high-level (overlay) and low-level (individual mineral regions) provenance visible

---

### ✅ WaterIceIntelligence.tsx
**Location:** `web/src/pages/WaterIceIntelligence.tsx`

**Displays:**
- **Top-level:**
  - `data.display_label`
  - `data.data_status` (badge display)
  
- **Per-item:**
  - `item.display_label`
  - `item.data_status`
  - `item.provenance.note` (via `provenanceNote()`)

**Context:** Water-ice overlay inspection and provenance workspace
**Function:** `itemSummary()` helper combines display_label, data_status, and provenance note
**UI:** Status badge shows synthetic/estimated/real labels prominently

```typescript
function itemSummary(item: WaterIceItemPayload): string {
  const parts = [item.display_label, item.data_status];
  if (item.provenance && typeof item.provenance === 'object') {
    const note = provenanceNote(item.provenance as Record<string, unknown>);
    if (note) parts.push(note);
  }
  return parts.filter(Boolean).join(' · ');
}
```

---

### ✅ MissionControl.tsx
**Location:** `web/src/pages/MissionControl.tsx`

**Displays:**
- `OutputReadinessCard` with label "Dataset provenance"
- Static state: `state="synthetic"` (intentional placeholder)
- Detail: "Current dataset labels are intentionally synthetic or development-only and are clearly marked as such."

**Context:** System status and operational overview dashboard
**Coverage:** High-level system message; not tied to actual dataset metadata

---

### ✅ sensors.ts (loadSensorDataset utility)
**Location:** `web/src/sensors/sensors.ts`

**Displays:** (Data extraction layer)
- Extracts `payload.display_label` → `displayLabel`
- Extracts `payload.data_status` → `dataStatus`
- Extracts `payload.provenance` → `provenance`

**Context:** Normalization layer for sensor payload data
**Usage:** Called by `MultiSensor.tsx` to load and register all sensor datasets
**Pattern:** Transforms API payloads into `SelectedDataset` interface for downstream use

---

## 2. Components That SHOULD Display Provenance But Don't

### ❌ Landmarks Visualization (MISSING PAGE)
**Backend API defined:** `fetchLandmarks()` in `web/src/api/client.ts`  
**Frontend usage:** **NONE**

**LandmarksPayload structure:**
```typescript
interface LandmarksPayload {
  display_label: string;
  data_status: 'synthetic' | 'estimated' | 'real' | 'unknown';
  landmark_count: number;
  coordinate_convention: Record<string, string>;
  landmarks: LandmarkItemPayload[];
  provenance: Record<string, unknown>;
}

interface LandmarkItemPayload {
  landmark_id: string;
  display_label: string;
  estimated_position_m: { x; y; z };
  reference_position_m: { x; y; z } | null;
  diameter_m: number;
  depth_m: number | null;
  confidence: number | null;
  quality_score: number | null;
  localization_status: string;
  data_status: string;
  provenance: Record<string, unknown>;
}
```

**Provenance fields available:**
- Payload-level: `display_label`, `data_status`, `provenance`
- Item-level: `display_label`, `data_status`, `provenance`

**Gap:** No dedicated "Landmarks Intelligence" workspace exists (compare to SpectralIntelligence, WaterIceIntelligence)  
**Impact:** Crater/landmark detection results cannot display source data status or provenance
**Recommendation:** Create `LandmarksIntelligence.tsx` page with provenance display pattern matching Spectral/WaterIce

---

### ❌ Hazards Visualization (MISSING PAGE)
**Backend API defined:** `fetchHazards()` in `web/src/api/client.ts`  
**Frontend usage:** **NONE**

**HazardsPayload structure:**
```typescript
interface HazardsPayload {
  display_label: string;
  data_status: 'synthetic' | 'estimated' | 'real' | 'unknown';
  hazard_count: number;
  coordinate_convention: Record<string, string>;
  hazards: HazardItemPayload[];
  provenance: Record<string, unknown>;
}

interface HazardItemPayload {
  hazard_id: string;
  hazard_type: string;
  severity: 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW';
  risk_score: number;
  confidence: number | null;
  description: string;
  position_m: { x; y; z };
  radius_m: number | null;
  boundary_vertices_m: Array<{ x; y; z }> | null;
  data_status: string;
  provenance: Record<string, unknown>;
}
```

**Provenance fields available:**
- Payload-level: `display_label`, `data_status`, `provenance`
- Item-level: `data_status`, `provenance`

**Gap:** No dedicated "Hazards Intelligence" workspace  
**Current display:** `HazardMap.tsx` displays hazard results (slope, risk, binary mask images) but only from `MissionContext` result object, not from `fetchHazards()` API  
**Impact:** Hazard detection source status and provenance never visible to users
**Recommendation:** Create `HazardsIntelligence.tsx` page; integrate with HazardMap or replace with comprehensive hazard viewer

---

### ❌ RegistrationCockpit.tsx
**Location:** `web/src/pages/RegistrationCockpit.tsx`

**Current display:**
- Shows source and reference dataset selections
- Extracts dataset label via `datasetLabel()` helper
- Displays match points and registration metrics

**Missing provenance display:**
- `sourceDataset.dataStatus` not shown
- `sourceDataset.provenance` not visible
- `referenceDataset.dataStatus` not shown
- `referenceDataset.provenance` not visible

**Gap:** Source/reference dataset status and provenance context lost; users can't verify data status before registration  
**Recommendation:** Add dataset metadata panel showing `displayLabel`, `dataStatus`, and `provenance.note` for both source and reference datasets (similar to `SensorMetadata()` in MultiSensor)

---

### ❌ Terrain.tsx
**Location:** `web/src/pages/Terrain.tsx`

**Current display:**
- Shows DEM metadata from `MissionContext.result.pipeline` (M3 phase results):
  - Data Source: "TMCDTM (Physical DEM)"
  - Dimensions
  - Resolution
  - Elevation Range
  - Integration Status

**Payload available:** `DemTerrainPayload` from `fetchDemTerrain()` is defined in API client

**Missing provenance display:**
- `payload.metadata.display_label` not shown
- `payload.metadata.data_status` not shown
- `payload.metadata.provenance` not visible
- `payload.metadata.source_type` not shown

**Gap:** DEM provenance metadata available in API but never fetched or displayed  
**Current fallback:** Hardcoded "TMCDTM" label with static metadata; no real provenance tracking
**Recommendation:** 
  1. Add `useEffect` to fetch `fetchDemTerrain()` 
  2. Display `display_label`, `data_status`, `provenance.note`
  3. Show `source_type` and `vertical_units`

---

### ❌ HazardMap.tsx
**Location:** `web/src/pages/HazardMap.tsx`

**Current display:**
- Displays hazard visualizations (slope gradient map, crater/boulder risk, combined binary mask)
- Shows threshold values and safety parameters
- Uses hardcoded URLs from `result.pipeline`

**Payload available:** `HazardsPayload` from `fetchHazards()` defined in API client

**Missing provenance display:**
- No `data_status` indicator
- No source provenance context
- No hazard count or metadata summary with status

**Gap:** Hazard results shown without status/provenance context  
**Recommendation:** 
  1. Fetch `fetchHazards()` alongside existing result
  2. Display hazard count, `data_status`, and provenance badge
  3. Link individual hazard items to `HazardsIntelligence` (new) page

---

### ❌ Imagery.tsx
**Location:** `web/src/pages/Imagery.tsx`

**Current display:**
- File upload interface
- Super-resolution enhancement results (original vs. SR images)
- Links to `HazardMap` for downstream analysis

**Payload available:** None explicitly; uses generic `MissionData` or pipeline result object

**Missing provenance display:**
- No processing status/data provenance for uploaded imagery
- No indication of whether results are synthetic/test or real
- No pipeline metadata or processing provenance

**Gap:** Data ingestion page has no provenance context; users don't know status of processed data
**Recommendation:**
  1. Display processing status (synthetic? real?)
  2. Add timestamp or processing metadata
  3. Show data source/import provenance note

---

### ❌ TemporalChange.tsx
**Location:** `web/src/pages/TemporalChange.tsx`

**Current display:**
- Temporal comparison state management
- Dataset pair selection (Before/After)
- Status indicators (loading, ready, empty, unavailable)

**Datasets available:** `beforeDataset` and `afterDataset` from `useDatasetSelection()`  
**Fields available:** `displayLabel`, `dataStatus`, `provenance`

**Missing provenance display:**
- `beforeDataset.dataStatus` not shown
- `afterDataset.dataStatus` not shown
- Observation-level provenance not visible
- No status badges for data sources

**Gap:** Temporal analysis doesn't establish provenance context of compared observations  
**Recommendation:**
  1. Add metadata panel for before/after datasets
  2. Display `displayLabel`, `dataStatus`, `provenance.note`
  3. Mark synthetic vs. real observations clearly

---

## 3. API Payloads Defined but Underutilized

| Payload | Endpoint | Provenance Fields | Display Status |
|---------|----------|-------------------|---|
| `DemTerrainPayload` | `/terrain/dem` | `metadata.display_label`, `metadata.data_status`, `metadata.provenance` | ❌ Never fetched |
| `TmcCameraPayload` | `/cameras/tmc` | `display_label`, `data_status`, `provenance` | ✅ MultiSensor |
| `OhrcCameraPayload` | `/cameras/ohrc` | `display_label`, `data_status`, `provenance` | ✅ MultiSensor |
| `IirsFootprintPayload` | `/cameras/iirs` | `display_label`, `data_status`, `provenance` | ✅ MultiSensor |
| `LandmarksPayload` | `/landmarks` | `display_label`, `data_status`, `provenance` | ❌ API defined, page missing |
| `HazardsPayload` | `/hazards` | `display_label`, `data_status`, `provenance` | ❌ API defined, page missing |
| `SpectralOverlayPayload` | `/spectral` | `display_label`, `data_status`, `provenance` (payload + regions) | ✅ SpectralIntelligence |
| `WaterIceOverlayPayload` | `/water-ice` | `display_label`, `data_status`, `provenance` (payload + items) | ✅ WaterIceIntelligence |

---

## 4. Current Provenance Display Patterns

### Pattern 1: Sensor Selection (MultiSensor.tsx)
```
[Sensor Name] — [Display Label]
├─ Status: [Data Status Badge]
├─ Coordinate Convention: [Convention String]
├─ Provenance Note: [provenance.note if string]
└─ Metadata details...
```

### Pattern 2: Overlay Intelligence (Spectral/WaterIce)
```
[Page Title]

[Display Label] [Data Status Badge]

Region/Item List:
├─ [Item Label] · [Item Status] · [Provenance Note]
├─ [Item Label] · [Item Status] · [Provenance Note]
└─ ...

Footer: [Provenance Note from top-level payload]
```

### Pattern 3: Status Card (MissionControl)
```
[Status Label]
├─ State: [Status Badge]
└─ Detail: [Text Description]
```

---

## 5. Recommended Coverage Improvements

### High Priority (Critical Gaps)

| Component | Gap | Recommended Action |
|-----------|-----|-------------------|
| **Landmarks Intelligence** | Page doesn't exist | Create `LandmarksIntelligence.tsx` matching Spectral/WaterIce pattern |
| **Hazards Intelligence** | Page doesn't exist | Create `HazardsIntelligence.tsx` matching Spectral/WaterIce pattern |
| **DEM Terrain Provenance** | API payload never fetched | Add `useEffect` in `Terrain.tsx` to fetch and display `DemTerrainPayload` metadata |
| **RegistrationCockpit** | Source/reference status hidden | Add dataset metadata panels showing `dataStatus` and `provenance` |

### Medium Priority (Consistency Gaps)

| Component | Gap | Recommended Action |
|-----------|-----|-------------------|
| **HazardMap** | No provenance context for hazard results | Integrate with `HazardsIntelligence` page; add status badge |
| **TemporalChange** | No observation-level provenance display | Add dataset metadata showing `dataStatus`, `provenance.note` |
| **Imagery** | No processing status indicator | Display `data_status` for processed results |

### Low Priority (Nice-to-Have)

| Component | Gap | Recommended Action |
|-----------|-----|-------------------|
| **MissionControl** | Static "Dataset provenance" card | Replace with dynamic status from actual dataset selection |
| **LandingSites** | No provenance for site evaluation results | Add status context for feasible zones |

---

## 6. Suggested Implementation Pattern

For new pages displaying provenance:

```typescript
// 1. Fetch payload
const [data, setData] = useState<OverlayPayload | null>(null);

// 2. Extract provenance helper
function provenanceNote(provenance: Record<string, unknown>): string {
  const note = provenance.note;
  return typeof note === 'string' ? note : '';
}

// 3. Display top-level status
<div className="flex items-center justify-between">
  <h2>{data?.display_label}</h2>
  <span className="badge">{data?.data_status}</span>
</div>

// 4. Display item-level status with summary
{data?.items.map(item => (
  <div key={item.id}>
    <span>{item.display_label} · {item.data_status}</span>
    {item.provenance?.note && <p>{item.provenance.note}</p>}
  </div>
))}

// 5. Show top-level provenance
{provenanceNote(data?.provenance || {})}
```

---

## 7. Files Analyzed

### Pages (14 total)
- ✅ `MultiSensor.tsx` - Displays provenance
- ✅ `SpectralIntelligence.tsx` - Displays provenance
- ✅ `WaterIceIntelligence.tsx` - Displays provenance
- ❌ `Landmarks*.tsx` - Does not exist
- ❌ `Hazards*.tsx` - Does not exist
- ❌ `RegistrationCockpit.tsx` - Missing display
- ❌ `Terrain.tsx` - Missing display
- ❌ `HazardMap.tsx` - Missing display
- ❌ `TemporalChange.tsx` - Missing display
- ❌ `Imagery.tsx` - Missing display
- ⚠️ `MissionControl.tsx` - Partial/static display
- ⚠️ `LandingSites.tsx` - No provenance
- ⚠️ `ComingSoonWorkspace.tsx` - Placeholder

### API Client (`api/client.ts`)
- 8 payload types with `display_label` and `data_status` fields
- 10 payloads with `provenance` fields
- 10 fetch functions defined

### Context & Utilities
- `datasetSelectionContext.ts` - Stores `displayLabel`, `dataStatus`, `provenance`
- `sensors.ts` - Normalizes sensor payload data
- `MissionContext.ts` - Used by older pages (Imagery, HazardMap, Terrain)

---

## Conclusion

**Coverage Summary:**
- ✅ **Actively displayed:** 5 components (Multi-Sensor, Spectral, WaterIce, MissionControl status card, sensors utility)
- ❌ **Should display but don't:** 7 components/gaps
- ⚠️ **Partially displayed:** 2 components
- **Missing pages:** 2 (Landmarks, Hazards Intelligence)

**Key Insight:** Provenance infrastructure is well-established in the backend (all payloads include `display_label`, `data_status`, `provenance`) and partially adopted in the frontend (sensors and overlays), but coverage is incomplete. Modern "Intelligence" workspaces (Spectral, WaterIce) follow a consistent pattern that should be extended to all scientific result pages.

**Recommended Next Steps:**
1. Create `LandmarksIntelligence.tsx` and `HazardsIntelligence.tsx` pages
2. Update `Terrain.tsx` and `RegistrationCockpit.tsx` to fetch and display provenance
3. Integrate hazard display into `HazardsIntelligence` (replace or supplement `HazardMap.tsx`)
4. Document the provenance display pattern for future component development
