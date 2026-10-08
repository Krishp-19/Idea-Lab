import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  ArrowLeft, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  ShieldAlert, 
  Compass, 
  Maximize2, 
  AlertOctagon 
} from 'lucide-react';
import { api } from '../api/client';
import BoundingBoxCanvas from '../components/BoundingBoxCanvas';

export default function ViolationDetailPage() {
  const { id } = useParams();
  const [violation, setViolation] = useState(null);
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [notes, setNotes] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');

  const fetchDetail = async () => {
    try {
      const [vRes, zRes] = await Promise.all([
        api.getViolationDetail(id),
        api.getZones(),
      ]);
      setViolation(vRes.data);
      setZones(zRes.data || []);
      setNotes(vRes.data.reviewer_notes || '');
    } catch (e) {
      console.error('Failed to load violation detail:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [id]);

  const handleReview = async (action) => {
    try {
      await api.reviewViolation(id, action, notes);
      setActionSuccess(`Case successfully updated to ${action}ed.`);
      fetchDetail();
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return (
      <div className="py-20 text-center text-slate-500 text-sm">
        Loading case details...
      </div>
    );
  }

  if (!violation) {
    return (
      <div className="py-20 text-center space-y-3">
        <p className="text-white text-base">Violation record not found.</p>
        <Link to="/violations" className="text-sky-400 text-sm hover:underline">
          ← Back to violations list
        </Link>
      </div>
    );
  }

  const pe = violation.parking_event;
  const features = pe?.features || {};
  const bbox = [
    features.bbox_x1,
    features.bbox_y1,
    features.bbox_x2,
    features.bbox_y2,
  ].filter((v) => v !== undefined && v !== null);

  const imageUrl = pe?.snapshot_path ? api.getEvidenceUrl(pe.snapshot_path) : null;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <Link
            to="/violations"
            className="p-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-400 hover:text-white"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-white flex items-center space-x-2">
              <span>Case #{violation.id.slice(0, 8)}</span>
              <span
                className={`text-xs px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider ${
                  violation.label === 'violation'
                    ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                    : violation.label === 'risk'
                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                    : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                }`}
              >
                {violation.label}
              </span>
            </h1>
            <p className="text-xs text-slate-400">
              Captured {new Date(violation.created_at).toLocaleString()} • Vehicle Track #{violation.vehicle?.track_id || 'N/A'}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-xs text-slate-400 mr-2 capitalize">
            Status: <strong className="text-white">{violation.review_status}</strong>
          </span>
          <button
            onClick={() => handleReview('dismiss')}
            className="px-3 py-1.5 text-xs font-medium text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg"
          >
            Dismiss
          </button>
          <button
            onClick={() => handleReview('confirm')}
            className="px-3 py-1.5 text-xs font-medium text-white bg-rose-600 hover:bg-rose-500 rounded-lg shadow"
          >
            Confirm Violation
          </button>
        </div>
      </div>

      {actionSuccess && (
        <div className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs p-3 rounded-lg flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Main Grid: Visual Evidence Canvas + Feature Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Visual Canvas Evidence */}
        <div className="lg:col-span-2 bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-white text-sm">Visual Evidence & Spatial Overlays</h2>
            <span className="text-xs text-slate-400 font-mono">
              Bay: {violation.zone_name || 'Outside Zones'}
            </span>
          </div>

          <BoundingBoxCanvas
            imageUrl={imageUrl}
            bbox={bbox.length === 4 ? bbox : null}
            label={violation.label}
            zones={zones}
          />

          <p className="text-xs text-slate-500 italic">
            Overlay shows designated parking bays (blue), fire lanes (red), and walkways (yellow) alongside vehicle bounding box.
          </p>
        </div>

        {/* Feature Engineering Attributes */}
        <div className="space-y-6">
          <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-sm space-y-4">
            <h2 className="font-semibold text-white text-sm">Engineered Parking Features</h2>
            
            <div className="space-y-3 text-xs">
              <div className="flex justify-between py-1.5 border-b border-slate-700/50">
                <span className="text-slate-400">Inside Designated Bay:</span>
                <span className={`font-semibold ${features.inside_zone ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {features.inside_zone ? 'Yes (Inside)' : 'No (Outside)'}
                </span>
              </div>

              <div className="flex justify-between py-1.5 border-b border-slate-700/50">
                <span className="text-slate-400">Distance to Nearest Bay:</span>
                <span className="font-mono text-white">
                  {features.distance_to_nearest_zone_m !== undefined ? `${features.distance_to_nearest_zone_m}m` : '0.0m'}
                </span>
              </div>

              <div className="flex justify-between py-1.5 border-b border-slate-700/50">
                <span className="text-slate-400">Orientation Delta:</span>
                <span className="font-mono text-white">
                  {features.orientation_delta_deg !== undefined ? `${features.orientation_delta_deg}°` : '0°'}
                </span>
              </div>

              <div className="flex justify-between py-1.5 border-b border-slate-700/50">
                <span className="text-slate-400">Nearest Vehicle Distance:</span>
                <span className="font-mono text-white">
                  {features.nearest_neighbor_dist_px !== undefined ? `${features.nearest_neighbor_dist_px} px` : 'N/A'}
                </span>
              </div>

              <div className="flex justify-between py-1.5 border-b border-slate-700/50">
                <span className="text-slate-400">Obstructs Walkway:</span>
                <span className={`font-semibold ${features.obstructs_walkway ? 'text-rose-400' : 'text-emerald-400'}`}>
                  {features.obstructs_walkway ? 'YES (Obstruction)' : 'No'}
                </span>
              </div>

              <div className="flex justify-between py-1.5 border-b border-slate-700/50">
                <span className="text-slate-400">Obstructs Fire Lane:</span>
                <span className={`font-semibold ${features.obstructs_fire_lane ? 'text-rose-400' : 'text-emerald-400'}`}>
                  {features.obstructs_fire_lane ? 'YES (Hazard)' : 'No'}
                </span>
              </div>

              <div className="flex justify-between py-1.5 border-b border-slate-700/50">
                <span className="text-slate-400">Bay Sequence Violation:</span>
                <span className={`font-semibold ${features.bay_sequence_violation ? 'text-amber-400' : 'text-slate-300'}`}>
                  {features.bay_sequence_violation ? 'Yes (Skipped Bay)' : 'No'}
                </span>
              </div>

              <div className="flex justify-between py-1.5 border-b border-slate-700/50">
                <span className="text-slate-400">Stationary Dwell Duration:</span>
                <span className="font-mono text-white">
                  {pe?.dwell_seconds ? `${Math.round(pe.dwell_seconds)}s` : '0s'}
                </span>
              </div>
            </div>
          </div>

          {/* ML Probabilities Card */}
          <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-sm space-y-3">
            <h2 className="font-semibold text-white text-sm">ML Classifier Output</h2>
            {pe?.ml_probabilities ? (
              <div className="space-y-2 text-xs">
                {Object.entries(pe.ml_probabilities).map(([lbl, prob]) => (
                  <div key={lbl} className="space-y-1">
                    <div className="flex justify-between capitalize text-slate-300">
                      <span>{lbl}</span>
                      <span className="font-mono">{Math.round(prob * 100)}%</span>
                    </div>
                    <div className="w-full h-1.5 bg-slate-900 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          lbl === 'violation' ? 'bg-rose-500' : lbl === 'risk' ? 'bg-amber-500' : 'bg-emerald-500'
                        }`}
                        style={{ width: `${Math.round(prob * 100)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">No ML probability distribution available.</p>
            )}
          </div>

          {/* Reviewer Notes Editor */}
          <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-sm space-y-3">
            <h2 className="font-semibold text-white text-sm">Reviewer Assessment</h2>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add verification notes or reason for dismissal/confirmation..."
              className="w-full h-24 bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500"
            />
            <button
              onClick={() => handleReview(violation.review_status)}
              className="w-full py-2 bg-slate-700 hover:bg-slate-600 text-xs font-semibold text-white rounded-lg transition-colors"
            >
              Save Notes
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
