import React, { useState, useEffect } from 'react';
import { UploadCloud, FileVideo, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { api } from '../api/client';

export default function UploadPage() {
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [errorMsg, setErrorMsg] = useState('');

  const fetchJobs = async () => {
    try {
      const res = await api.getJobs();
      setJobs(res.data || []);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;

    setErrorMsg('');
    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      await api.uploadFootage(formData);
      setFile(null);
      // Reset input
      const inputEl = document.getElementById('footage-upload');
      if (inputEl) inputEl.value = '';
      fetchJobs();
    } catch (err) {
      setErrorMsg(err.response?.data?.detail || 'Upload failed. Ensure file is a video (.mp4) or image (.jpg).');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Footage Ingestion & Batch Processing</h1>
        <p className="text-xs text-slate-400">
          Upload CCTV video footage or camera images to run detection, tracking, dwell-time analysis, and feature classification.
        </p>
      </div>

      {/* Upload Box */}
      <form onSubmit={handleUpload} className="bg-slate-800/80 border border-slate-700/80 rounded-xl p-6 shadow-sm space-y-4">
        <div className="border-2 border-dashed border-slate-700 hover:border-slate-600 rounded-xl p-8 text-center flex flex-col items-center justify-center cursor-pointer relative bg-slate-900/40">
          <input
            id="footage-upload"
            type="file"
            accept=".mp4,.avi,.mov,.mkv,.jpg,.jpeg,.png"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
          />
          <UploadCloud className="w-12 h-12 text-sky-400 mb-3" />
          <p className="text-sm font-semibold text-white">
            {file ? file.name : 'Click or drag video / image file here'}
          </p>
          <p className="text-xs text-slate-400 mt-1">
            Supported formats: MP4, AVI, MOV, MKV, JPG, PNG
          </p>
          {file && (
            <p className="text-xs text-sky-400 font-mono mt-2">
              Selected: {(file.size / (1024 * 1024)).toFixed(2)} MB
            </p>
          )}
        </div>

        {errorMsg && (
          <div className="p-3 bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs rounded-lg flex items-center space-x-2">
            <AlertCircle className="w-4 h-4" />
            <span>{errorMsg}</span>
          </div>
        )}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={!file || isUploading}
            className="flex items-center space-x-2 px-5 py-2.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg shadow transition-colors"
          >
            {isUploading && <Loader2 className="w-4 h-4 animate-spin" />}
            <span>{isUploading ? 'Uploading & Queuing...' : 'Start AI Processing'}</span>
          </button>
        </div>
      </form>

      {/* Jobs status table */}
      <div className="bg-slate-800/80 border border-slate-700/80 rounded-xl overflow-hidden shadow-sm space-y-3 p-5">
        <h2 className="font-semibold text-white text-sm">Processing Queue & History</h2>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/80 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-700">
              <tr>
                <th className="py-3 px-4 font-semibold">File</th>
                <th className="py-3 px-4 font-semibold">Status</th>
                <th className="py-3 px-4 font-semibold">Progress Message</th>
                <th className="py-3 px-4 font-semibold">Submitted</th>
                <th className="py-3 px-4 font-semibold text-right">Summary</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/60">
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan="5" className="py-8 text-center text-slate-500">
                    No processing jobs recorded yet.
                  </td>
                </tr>
              ) : (
                jobs.map((j) => (
                  <tr key={j.job_id} className="hover:bg-slate-700/20">
                    <td className="py-3 px-4 font-medium text-white flex items-center space-x-2">
                      <FileVideo className="w-4 h-4 text-sky-400" />
                      <span>{j.filename}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold capitalize ${
                          j.status === 'completed'
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : j.status === 'failed'
                            ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                            : 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                        }`}
                      >
                        {j.status === 'processing' && <Loader2 className="w-3 h-3 animate-spin mr-1" />}
                        {j.status === 'completed' && <CheckCircle className="w-3 h-3 mr-1" />}
                        <span>{j.status}</span>
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-400">{j.message}</td>
                    <td className="py-3 px-4 text-slate-400 font-mono">
                      {new Date(j.created_at).toLocaleTimeString()}
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-xs">
                      {j.result_summary ? (
                        <span className="text-emerald-400">
                          {j.result_summary.parking_events} events / {j.result_summary.frames_processed} frames
                        </span>
                      ) : (
                        '-'
                      )}
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
