import React, { useState, useEffect } from 'react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer, 
  BarChart, 
  Bar 
} from 'recharts';
import { BarChart2, Calendar } from 'lucide-react';
import { api } from '../api/client';

export default function TrendsPage() {
  const [trendData, setTrendData] = useState([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTrend = async () => {
      setLoading(true);
      try {
        const res = await api.getTrend(days);
        setTrendData(res.data || []);
      } catch (e) {
        console.error('Failed to load trend data:', e);
      } finally {
        setLoading(false);
      }
    };
    fetchTrend();
  }, [days]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-white">Parking Compliance Trends</h1>
          <p className="text-xs text-slate-400">
            Historical progression of safe parking, risk warnings, and confirmed violations.
          </p>
        </div>

        <div className="flex items-center space-x-2 bg-slate-800 border border-slate-700 rounded-lg p-1">
          {[7, 14, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                days === d ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              {d} Days
            </button>
          ))}
        </div>
      </div>

      {/* Main Line Chart */}
      <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-sm space-y-4">
        <h2 className="font-semibold text-white text-sm">Classification Trend (Daily)</h2>
        <div className="h-80 w-full">
          {loading ? (
            <div className="h-full flex items-center justify-center text-xs text-slate-500">
              Loading trend analytics...
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                  itemStyle={{ fontSize: '12px' }}
                />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                <Line type="monotone" dataKey="violation" stroke="#ef4444" strokeWidth={2} name="Violations" />
                <Line type="monotone" dataKey="risk" stroke="#f59e0b" strokeWidth={2} name="Risk Warnings" />
                <Line type="monotone" dataKey="safe" stroke="#10b981" strokeWidth={2} name="Safe Parking" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Total Activity Bar Chart */}
      <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-5 shadow-sm space-y-4">
        <h2 className="font-semibold text-white text-sm">Daily Total Parking Volume</h2>
        <div className="h-64 w-full">
          {!loading && (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trendData} margin={{ top: 10, right: 20, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                  itemStyle={{ fontSize: '12px' }}
                />
                <Bar dataKey="total" fill="#0284c7" radius={[4, 4, 0, 0]} name="Total Parked Vehicles" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
