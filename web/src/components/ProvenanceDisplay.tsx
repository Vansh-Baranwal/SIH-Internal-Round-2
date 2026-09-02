/**
 * Phase 15.10 — Provenance Display Component
 *
 * Reusable component for displaying data provenance/status information.
 * Ensures synthetic data is clearly marked and real data is appropriately labeled.
 */

import React from 'react';
import { DataProvenance } from '../types/provenance';
import type { ProvenanceMetadata } from '../types/provenance';

export interface ProvenanceBadgeProps {
  classification: DataProvenance | string;
  compact?: boolean;
  className?: string;
}

/**
 * Badge component for displaying data provenance classification.
 * Colors and styling make the distinction between synthetic/real/unavailable very clear.
 */
export const ProvenanceBadge: React.FC<ProvenanceBadgeProps> = ({
  classification,
  compact = false,
  className = '',
}) => {
  const classMap: Record<string, string> = {
    [DataProvenance.REAL]: 'bg-green-100 text-green-900 border-green-300',
    [DataProvenance.SYNTHETIC]: 'bg-blue-100 text-blue-900 border-blue-300',
    [DataProvenance.ESTIMATED]: 'bg-yellow-100 text-yellow-900 border-yellow-300',
    [DataProvenance.ILLUSTRATIVE]: 'bg-gray-100 text-gray-900 border-gray-300',
    [DataProvenance.DEFERRED]: 'bg-gray-100 text-gray-700 border-gray-300',
    [DataProvenance.UNAVAILABLE]: 'bg-gray-200 text-gray-800 border-gray-400',
  };

  const labelMap: Record<string, string> = {
    [DataProvenance.REAL]: 'REAL',
    [DataProvenance.SYNTHETIC]: 'SYNTHETIC',
    [DataProvenance.ESTIMATED]: 'ESTIMATED',
    [DataProvenance.ILLUSTRATIVE]: 'ILLUSTRATIVE',
    [DataProvenance.DEFERRED]: 'DEFERRED',
    [DataProvenance.UNAVAILABLE]: 'UNAVAILABLE',
  };

  const classValue = classMap[classification] || classMap[DataProvenance.UNAVAILABLE];
  const label = labelMap[classification] || 'UNKNOWN';
  const size = compact ? 'px-2 py-1 text-xs' : 'px-3 py-1 text-sm';

  return (
    <span
      className={`inline-block border rounded-full font-semibold ${size} ${classValue} ${className}`}
    >
      {label}
    </span>
  );
};

export interface ProvenanceInfoProps {
  metadata: ProvenanceMetadata;
  showNotes?: boolean;
  className?: string;
}

/**
 * Detailed component for displaying full provenance metadata.
 * Shows classification, source module, data type, and optional notes.
 */
export const ProvenanceInfo: React.FC<ProvenanceInfoProps> = ({
  metadata,
  showNotes = true,
  className = '',
}) => {
  return (
    <div className={`provenance-info space-y-2 ${className}`}>
      <div className="flex items-center gap-2">
        <ProvenanceBadge classification={metadata.classification} />
        <span className="text-gray-700 text-sm font-medium">
          {metadata.dataType}
        </span>
      </div>

      {showNotes && metadata.notes && (
        <p className="text-gray-600 text-sm bg-gray-50 p-2 rounded border-l-2 border-gray-300">
          {metadata.notes}
        </p>
      )}

      <div className="text-gray-500 text-xs">
        <span>Module: {metadata.sourceModule}</span>
      </div>
    </div>
  );
};

export interface ProvenanceWarningProps {
  message?: string;
  className?: string;
}

/**
 * Warning component displayed when synthetic/deferred data might be misunderstood.
 * Used in places where users might otherwise assume data is real/authoritative.
 */
export const SyntheticDataWarning: React.FC<ProvenanceWarningProps> = ({
  message = 'This is synthetic development data. It does not represent real lunar observations or scientific validation.',
  className = '',
}) => {
  return (
    <div
      className={`bg-blue-50 border-l-4 border-blue-400 p-3 rounded text-sm text-blue-800 ${className}`}
    >
      <div className="flex items-start gap-2">
        <span className="text-lg">ⓘ</span>
        <p>{message}</p>
      </div>
    </div>
  );
};

export interface UnavailableDataNoticeProps {
  message?: string;
  className?: string;
}

/**
 * Notice component displayed when a feature is unavailable.
 */
export const UnavailableDataNotice: React.FC<UnavailableDataNoticeProps> = ({
  message = 'This feature is not available in the current build.',
  className = '',
}) => {
  return (
    <div
      className={`bg-gray-50 border-l-4 border-gray-400 p-3 rounded text-sm text-gray-700 ${className}`}
    >
      <div className="flex items-start gap-2">
        <span className="text-lg">—</span>
        <p>{message}</p>
      </div>
    </div>
  );
};

export interface DeferredDataNoticeProps {
  message?: string;
  className?: string;
}

/**
 * Notice component displayed when a feature is deferred/not yet implemented.
 */
export const DeferredDataNotice: React.FC<DeferredDataNoticeProps> = ({
  message = 'This feature is planned but not yet implemented.',
  className = '',
}) => {
  return (
    <div
      className={`bg-gray-50 border-l-4 border-gray-300 p-3 rounded text-sm text-gray-600 ${className}`}
    >
      <div className="flex items-start gap-2">
        <span className="text-lg">⏱</span>
        <p>{message}</p>
      </div>
    </div>
  );
};
