import React, { useState } from 'react';
import { CheckCircle2, XCircle, AlertTriangle, X } from 'lucide-react';

export default function ReviewModal({ isOpen, onClose, violation, onConfirm, onDismiss }) {
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen || !violation) return null;

  const handleAction = async (action) => {
    setIsSubmitting(true);
    try {
      if (action === 'confirm') {
        await onConfirm(violation.id, notes);
      } else {
        await onDismiss(violation.id, notes);
      }
      onClose();
    } catch (e) {
      console.error(e);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="bg-slate-800 border border-slate-700 rounded-xl max-w-lg w-full p-6 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-3 mb-4">
          <div className="p-2 rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Review Parking Case</h3>
            <p className="text-xs text-slate-400">
              Track ID: #{violation.vehicle?.track_id || 'N/A'} • Zone: {violation.zone_name || 'N/A'}
            </p>
          </div>
        </div>

        <div className="bg-slate-900 rounded-lg p-3 border border-slate-700/60 mb-4 text-sm">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-slate-400">Current Label:</span>{' '}
              <span className={`font-semibold uppercase ${
                violation.label === 'violation' ? 'text-rose-400' :
                violation.label === 'risk' ? 'text-amber-400' : 'text-emerald-400'
              }`}>
                {violation.label}
              </span>
            </div>
            <div>
              <span className="text-slate-400">Confidence:</span>{' '}
              <span className="font-mono text-white">
                {violation.parking_event?.ml_confidence ? `${Math.round(violation.parking_event.ml_confidence * 100)}%` : 'N/A'}
              </span>
            </div>
            <div>
              <span className="text-slate-400">Dwell Time:</span>{' '}
              <span className="text-white">
                {violation.parking_event?.dwell_seconds ? `${Math.round(violation.parking_event.dwell_seconds)}s` : 'N/A'}
              </span>
            </div>
            <div>
              <span className="text-slate-400">Status:</span>{' '}
              <span className="text-slate-300 capitalize">{violation.review_status}</span>
            </div>
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-xs font-medium text-slate-300 mb-1">
            Supervisor Notes (Optional):
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g. Verified two-wheeler blocking pedestrian passage..."
            className="w-full h-24 bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500"
          />
        </div>

        <div className="flex items-center justify-end space-x-3 pt-2 border-t border-slate-700">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-white bg-slate-700/50 hover:bg-slate-700 rounded-lg"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => handleAction('dismiss')}
            className="flex items-center space-x-1.5 px-4 py-2 text-sm font-medium text-slate-200 bg-slate-700 hover:bg-slate-600 rounded-lg disabled:opacity-50"
          >
            <XCircle className="w-4 h-4 text-slate-400" />
            <span>Dismiss (No Violation)</span>
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={() => handleAction('confirm')}
            className="flex items-center space-x-1.5 px-4 py-2 text-sm font-medium text-white bg-rose-600 hover:bg-rose-500 rounded-lg shadow disabled:opacity-50"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Confirm Violation</span>
          </button>
        </div>
      </div>
    </div>
  );
}
