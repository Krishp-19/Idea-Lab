import React, { useState, useEffect, useRef } from 'react';
import { MapPin, AlertTriangle, ShieldCheck } from 'lucide-react';
import { api } from '../api/client';

export default function HeatmapPage() {
  const [heatmapData, setHeatmapData] = useState([]);
  const [loading, setLoading] = useState(true);
  const canvasRef = useRef(null);

  useEffect(() => {
    const fetchHeatmap = async () => {
      try {
        const res = await api.getHeatmap();
        setHeatmapData(res.data || []);
      } catch (e) {
        console.error('Failed to load heatmap:', e);
      } finally {
        setLoading(false);
      }
    };
    fetchHeatmap();
  }, []);

  // Render canvas visual overview of zones
  useEffect(() => {
    if (!heatmapData.length || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    canvas.width = 800;
    canvas.height = 450;

    // Draw background
    ctx.fillStyle = '#090d16';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw grid
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }

    // Find max violation count for color normalization
    const maxViolations = Math.max(1, ...heatmapData.map((z) => z.violation_count));

    heatmapData.forEach((z) => {
      if (!z.boundary_polygon || z.boundary_polygon.length < 3) return;

      const poly = z.boundary_polygon;
      ctx.beginPath();
      ctx.moveTo(poly[0][0], poly[0][1]);
      for (let i = 1; i < poly.length; i++) {
        ctx.lineTo(poly[i][0], poly[i][1]);
      }
      ctx.closePath();

      // Color intensity based on violations
      const intensity = z.violation_count / maxViolations;
      const alpha = 0.2 + intensity * 0.6;
      ctx.fillStyle = `rgba(239, 68, 68, ${alpha})`;
      ctx.strokeStyle = '#ef4444';
      ctx.lineWidth = 2;
      ctx.fill();
      ctx.stroke();

      // Label
      const cx = poly.reduce((acc, p) => acc + p[0], 0) / poly.length;
      const cy = poly.reduce((acc, p) => acc + p[1], 0) / poly.length;

      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 12px sans-serif';
      ctx.fillText(z.zone_name, cx - 30, cy);
      ctx.fillStyle = '#fca5a5';
      ctx.font = '10px sans-serif';
      ctx.fillText(`${z.violation_count} violations`, cx - 30, cy + 14);
    });
  }, [heatmapData]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Zone Violation Heatmap</h1>
        <p className="text-xs text-slate-400">
          Spatial distribution of parking non-compliance across designated zones.
        </p>
      </div>

      {/* Visual Canvas Heatmap */}
      <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-white text-sm">Spatial Hotspots</h2>
          <div className="flex items-center space-x-2 text-xs">
            <span className="inline-block w-3 h-3 rounded bg-red-500/30 border border-red-500" />
            <span className="text-slate-400">Low Intensity</span>
            <span className="inline-block w-3 h-3 rounded bg-red-600 border border-red-400 ml-2" />
            <span className="text-slate-400">High Non-Compliance Hotspot</span>
          </div>
        </div>

        <div className="flex justify-center bg-slate-950 rounded-lg p-2 border border-slate-700 overflow-hidden">
          <canvas ref={canvasRef} className="max-w-full h-auto rounded" />
        </div>
      </div>

      {/* Zone Aggregation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {heatmapData.map((z) => (
          <div
            key={z.zone_id}
            className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-4 shadow-sm space-y-2"
          >
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-white text-sm">{z.zone_name}</h3>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-400">
                {z.zone_type}
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2 pt-2 text-center text-xs">
              <div className="bg-rose-500/10 border border-rose-500/20 rounded-lg p-2">
                <p className="text-rose-400 font-bold text-base">{z.violation_count}</p>
                <p className="text-[10px] text-slate-400 uppercase">Violations</p>
              </div>
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-2">
                <p className="text-amber-400 font-bold text-base">{z.risk_count}</p>
                <p className="text-[10px] text-slate-400 uppercase">Risk</p>
              </div>
              <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-2">
                <p className="text-emerald-400 font-bold text-base">{z.safe_count}</p>
                <p className="text-[10px] text-slate-400 uppercase">Safe</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
