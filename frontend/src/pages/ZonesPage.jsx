import React, { useState, useEffect } from 'react';
import { Layers, RefreshCw, Trash2, Plus, Terminal } from 'lucide-react';
import { api } from '../api/client';

export default function ZonesPage() {
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncMessage, setSyncMessage] = useState('');

  const fetchZones = async () => {
    setLoading(true);
    try {
      const res = await api.getZones();
      setZones(res.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchZones();
  }, []);

  const handleSync = async () => {
    try {
      await api.syncZones();
      setSyncMessage('Zones re-synchronized from config/zones.json');
      fetchZones();
      setTimeout(() => setSyncMessage(''), 4000);
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (zoneId) => {
    if (!confirm(`Are you sure you want to delete zone ${zoneId}?`)) return;
    try {
      await api.deleteZone(zoneId);
      fetchZones();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white">Zone Configuration</h1>
          <p className="text-xs text-slate-400">
            Define designated parking bays, walkways, and emergency fire lanes per parking lot site.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleSync}
            className="flex items-center space-x-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg border border-slate-700"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Sync from File</span>
          </button>
        </div>
      </div>

      {syncMessage && (
        <div className="p-3 bg-sky-950 border border-sky-800 text-sky-400 text-xs rounded-lg">
          {syncMessage}
        </div>
      )}

      {/* Terminal drawer prompt tip */}
      <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-sm space-y-2">
        <div className="flex items-center space-x-2 text-sky-400 text-xs font-semibold">
          <Terminal className="w-4 h-4" />
          <span>Interactive Polygon Drawer</span>
        </div>
        <p className="text-xs text-slate-300">
          To mark new bays directly on a CCTV frame with polygon drawing tools, run in your terminal:
        </p>
        <div className="bg-slate-950 rounded-lg p-3 text-xs font-mono text-emerald-400 border border-slate-800 select-all">
          python ml/zone_config/zone_drawer.py --frame data/raw_images/sample.jpg
        </div>
      </div>

      {/* Zones list table */}
      <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/80 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-700">
              <tr>
                <th className="py-3 px-4 font-semibold">Zone ID</th>
                <th className="py-3 px-4 font-semibold">Name</th>
                <th className="py-3 px-4 font-semibold">Type</th>
                <th className="py-3 px-4 font-semibold">Expected Angle</th>
                <th className="py-3 px-4 font-semibold">Polygon Vertices</th>
                <th className="py-3 px-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/60">
              {loading ? (
                <tr>
                  <td colSpan="6" className="py-8 text-center text-slate-500">
                    Loading zones...
                  </td>
                </tr>
              ) : zones.length === 0 ? (
                <tr>
                  <td colSpan="6" className="py-8 text-center text-slate-500">
                    No zones defined yet. Run the zone drawer tool to add parking bays.
                  </td>
                </tr>
              ) : (
                zones.map((z) => (
                  <tr key={z.zone_id} className="hover:bg-slate-700/20">
                    <td className="py-3 px-4 font-mono font-medium text-white">{z.zone_id}</td>
                    <td className="py-3 px-4">{z.name}</td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          z.zone_type === 'parking_bay'
                            ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                            : z.zone_type === 'fire_lane'
                            ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                            : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                        }`}
                      >
                        {z.zone_type}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono">{z.expected_angle_degrees}°</td>
                    <td className="py-3 px-4 font-mono">
                      {z.boundary_polygon ? `${z.boundary_polygon.length} points` : '0 points'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleDelete(z.zone_id)}
                        className="p-1 text-slate-400 hover:text-rose-400 rounded hover:bg-slate-700"
                        title="Delete zone"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
