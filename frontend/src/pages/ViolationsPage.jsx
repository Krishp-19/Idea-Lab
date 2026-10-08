import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { 
  Filter, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Eye, 
  ChevronLeft, 
  ChevronRight, 
  RefreshCw 
} from 'lucide-react';
import { api } from '../api/client';
import ReviewModal from '../components/ReviewModal';

export default function ViolationsPage() {
  const [violations, setViolations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [meta, setMeta] = useState({ page: 1, page_size: 15, total: 0 });

  // Filters
  const [statusFilter, setStatusFilter] = useState('');
  const [labelFilter, setLabelFilter] = useState('');

  // Active modal
  const [selectedViolation, setSelectedViolation] = useState(null);

  const fetchViolations = async (page = 1) => {
    setLoading(true);
    try {
      const params = { page, page_size: meta.page_size };
      if (statusFilter) params.status = statusFilter;
      if (labelFilter) params.label = labelFilter;

      const res = await api.getViolations(params);
      setViolations(res.data.items || []);
      setMeta(res.data.meta || { page, page_size: 15, total: 0 });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchViolations(1);
  }, [statusFilter, labelFilter]);

  const handleConfirm = async (id, notes) => {
    await api.reviewViolation(id, 'confirm', notes);
    fetchViolations(meta.page);
  };

  const handleDismiss = async (id, notes) => {
    await api.reviewViolation(id, 'dismiss', notes);
    fetchViolations(meta.page);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white">Parking Violations & Case Review</h1>
          <p className="text-xs text-slate-400">
            Verify AI-flagged two-wheeler parking cases before escalating to authority enforcement.
          </p>
        </div>

        {/* Filters */}
        <div className="flex items-center space-x-3">
          <select
            value={labelFilter}
            onChange={(e) => setLabelFilter(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:border-sky-500"
          >
            <option value="">All Classifications</option>
            <option value="violation">Violations Only</option>
            <option value="risk">Risk Warnings</option>
            <option value="safe">Safe Parking</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-xs text-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:border-sky-500"
          >
            <option value="">All Review Statuses</option>
            <option value="pending">Pending Review</option>
            <option value="confirmed">Confirmed</option>
            <option value="dismissed">Dismissed</option>
          </select>

          <button
            onClick={() => fetchViolations(meta.page)}
            className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700"
            title="Refresh list"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Table */}
      <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/80 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-700">
              <tr>
                <th className="py-3.5 px-4 font-semibold">Snapshot</th>
                <th className="py-3.5 px-4 font-semibold">Track & Zone</th>
                <th className="py-3.5 px-4 font-semibold">Classification</th>
                <th className="py-3.5 px-4 font-semibold">Dwell Time</th>
                <th className="py-3.5 px-4 font-semibold">Status</th>
                <th className="py-3.5 px-4 font-semibold">Timestamp</th>
                <th className="py-3.5 px-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/60">
              {loading ? (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-slate-500">
                    Loading parking events...
                  </td>
                </tr>
              ) : violations.length === 0 ? (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-slate-500">
                    No violation cases found matching current filters.
                  </td>
                </tr>
              ) : (
                violations.map((v) => (
                  <tr key={v.id} className="hover:bg-slate-700/20 transition-colors">
                    <td className="py-3 px-4">
                      {v.parking_event?.snapshot_path ? (
                        <img
                          src={api.getEvidenceUrl(v.parking_event.snapshot_path)}
                          alt="Snapshot"
                          className="w-14 h-10 object-cover rounded border border-slate-700"
                        />
                      ) : (
                        <div className="w-14 h-10 bg-slate-900 rounded border border-slate-700 flex items-center justify-center text-[10px] text-slate-500">
                          No Pic
                        </div>
                      )}
                    </td>

                    <td className="py-3 px-4 font-medium text-white">
                      <div>Track #{v.vehicle?.track_id || 'N/A'}</div>
                      <div className="text-[11px] text-slate-400">{v.zone_name || 'Outside Zones'}</div>
                    </td>

                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider ${
                          v.label === 'violation'
                            ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                            : v.label === 'risk'
                            ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                            : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        }`}
                      >
                        {v.label}
                      </span>
                      {v.parking_event?.ml_confidence && (
                        <span className="block text-[10px] text-slate-400 font-mono mt-0.5">
                          {Math.round(v.parking_event.ml_confidence * 100)}% conf
                        </span>
                      )}
                    </td>

                    <td className="py-3 px-4 font-mono">
                      {v.parking_event?.dwell_seconds
                        ? `${Math.round(v.parking_event.dwell_seconds)}s`
                        : 'N/A'}
                    </td>

                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-medium capitalize ${
                          v.review_status === 'confirmed'
                            ? 'text-rose-400 bg-rose-500/10'
                            : v.review_status === 'dismissed'
                            ? 'text-slate-400 bg-slate-700/50'
                            : 'text-amber-400 bg-amber-500/10'
                        }`}
                      >
                        {v.review_status === 'confirmed' && <CheckCircle2 className="w-3 h-3" />}
                        {v.review_status === 'dismissed' && <XCircle className="w-3 h-3" />}
                        {v.review_status === 'pending' && <Clock className="w-3 h-3" />}
                        <span>{v.review_status}</span>
                      </span>
                    </td>

                    <td className="py-3 px-4 text-slate-400">
                      {new Date(v.created_at).toLocaleString()}
                    </td>

                    <td className="py-3 px-4 text-right space-x-2">
                      <button
                        onClick={() => setSelectedViolation(v)}
                        className="px-2.5 py-1 text-xs font-medium text-sky-400 bg-sky-950/60 border border-sky-800/80 rounded hover:bg-sky-900 transition-colors"
                      >
                        Review
                      </button>
                      <Link
                        to={`/violations/${v.id}`}
                        className="px-2.5 py-1 text-xs font-medium text-slate-300 bg-slate-700 hover:bg-slate-600 rounded transition-colors"
                      >
                        Details
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination bar */}
        <div className="flex items-center justify-between px-4 py-3 bg-slate-900/60 border-t border-slate-700 text-xs text-slate-400">
          <div>
            Showing {violations.length} of {meta.total} cases
          </div>
          <div className="flex items-center space-x-2">
            <button
              disabled={meta.page <= 1}
              onClick={() => fetchViolations(meta.page - 1)}
              className="p-1.5 rounded border border-slate-700 hover:bg-slate-700 disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="font-mono">Page {meta.page}</span>
            <button
              disabled={meta.page * meta.page_size >= meta.total}
              onClick={() => fetchViolations(meta.page + 1)}
              className="p-1.5 rounded border border-slate-700 hover:bg-slate-700 disabled:opacity-40"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <ReviewModal
        isOpen={Boolean(selectedViolation)}
        onClose={() => setSelectedViolation(null)}
        violation={selectedViolation}
        onConfirm={handleConfirm}
        onDismiss={handleDismiss}
      />
    </div>
  );
}
