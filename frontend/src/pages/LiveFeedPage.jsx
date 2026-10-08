import React, { useState, useEffect } from 'react';
import { Video, ShieldAlert, CheckCircle2, Clock, RefreshCw, Eye } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import StatCard from '../components/StatCard';

export default function LiveFeedPage() {
  const [stats, setStats] = useState(null);
  const [recentViolations, setRecentViolations] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [statsRes, viosRes] = await Promise.all([
        api.getStats(),
        api.getViolations({ page: 1, page_size: 6 }),
      ]);
      setStats(statsRes.data);
      setRecentViolations(viosRes.data.items || []);
    } catch (e) {
      console.error('Failed to fetch dashboard data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 6000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Metrics Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Violations"
          value={stats ? stats.total_violations : '-'}
          subtitle="All-time recorded"
          icon={ShieldAlert}
          color="rose"
        />
        <StatCard
          title="Pending Review"
          value={stats ? stats.pending_review : '-'}
          subtitle="Action required"
          icon={Clock}
          color="amber"
        />
        <StatCard
          title="Confirmed"
          value={stats ? stats.confirmed : '-'}
          subtitle="Human verified"
          icon={CheckCircle2}
          color="emerald"
        />
        <StatCard
          title="Today's Violations"
          value={stats ? stats.today_violations : '-'}
          subtitle="Since midnight UTC"
          icon={Video}
          color="sky"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Feed Simulator / Camera Status */}
        <div className="lg:col-span-2 bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
              <h2 className="font-semibold text-white">Live Monitoring Stream</h2>
            </div>
            <span className="text-xs bg-slate-900 border border-slate-700 text-slate-400 px-2.5 py-1 rounded-full">
              CCTV Camera #1 (Main Parking Lot)
            </span>
          </div>

          <div className="relative aspect-video rounded-lg overflow-hidden bg-slate-950 border border-slate-800 flex items-center justify-center">
            {recentViolations.length > 0 && recentViolations[0].parking_event?.snapshot_path ? (
              <img
                src={api.getEvidenceUrl(recentViolations[0].parking_event.snapshot_path)}
                alt="Latest Capture"
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="text-center p-6 space-y-2">
                <Video className="w-10 h-10 text-slate-600 mx-auto animate-bounce" />
                <p className="text-sm font-medium text-slate-400">Stream Connected</p>
                <p className="text-xs text-slate-500 max-w-sm">
                  Waiting for detection events. Upload video files via "Upload & Process" or stream live RTSP feeds.
                </p>
              </div>
            )}
            <div className="absolute top-3 left-3 bg-black/60 backdrop-blur-md px-2.5 py-1 rounded text-xs font-mono text-emerald-400 border border-emerald-500/30">
              AI INFERENCE ACTIVE • YOLOV8 + BYTETRACK
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-700/60">
            <span>Dwell-time threshold: 30s</span>
            <span>Target classes: motorcycle, bicycle</span>
            <Link to="/upload" className="text-sky-400 hover:underline">
              Upload footage →
            </Link>
          </div>
        </div>

        {/* Live Event Activity Feed */}
        <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-white">Recent Activity</h2>
            <button
              onClick={fetchData}
              className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-700"
              title="Refresh"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="space-y-3">
            {recentViolations.length === 0 ? (
              <p className="text-xs text-slate-500 text-center py-8">No parking events logged yet.</p>
            ) : (
              recentViolations.map((v) => (
                <div
                  key={v.id}
                  className="bg-slate-900/90 border border-slate-700/60 rounded-lg p-3 hover:border-slate-600 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span
                        className={`inline-block w-2 h-2 rounded-full ${
                          v.label === 'violation'
                            ? 'bg-rose-500'
                            : v.label === 'risk'
                            ? 'bg-amber-500'
                            : 'bg-emerald-500'
                        }`}
                      />
                      <span className="text-xs font-bold text-white uppercase tracking-wider">
                        {v.label}
                      </span>
                    </div>
                    <span className="text-[11px] font-mono text-slate-400">
                      {new Date(v.created_at).toLocaleTimeString()}
                    </span>
                  </div>

                  <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
                    <span>
                      Track #{v.vehicle?.track_id || '0'} • {v.zone_name || 'No Bay'}
                    </span>
                    <Link
                      to={`/violations/${v.id}`}
                      className="text-sky-400 hover:text-sky-300 flex items-center space-x-1"
                    >
                      <span>Review</span>
                      <Eye className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
