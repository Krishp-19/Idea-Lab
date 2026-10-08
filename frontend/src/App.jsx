import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import LiveFeedPage from './pages/LiveFeedPage';
import ViolationsPage from './pages/ViolationsPage';
import ViolationDetailPage from './pages/ViolationDetailPage';
import TrendsPage from './pages/TrendsPage';
import HeatmapPage from './pages/HeatmapPage';
import ZonesPage from './pages/ZonesPage';
import UploadPage from './pages/UploadPage';
import { api } from './api/client';

export default function App() {
  const [user, setUser] = useState(null);

  useEffect(() => {
    const savedUser = localStorage.getItem('parking_user');
    if (savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch (e) {}
    }
  }, []);

  const handleLogout = () => {
    api.logout();
    setUser(null);
  };

  return (
    <Router>
      <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col font-sans">
        <Navbar user={user} onLogout={handleLogout} />
        
        <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
          <Routes>
            <Route path="/" element={<LiveFeedPage />} />
            <Route path="/violations" element={<ViolationsPage />} />
            <Route path="/violations/:id" element={<ViolationDetailPage />} />
            <Route path="/trends" element={<TrendsPage />} />
            <Route path="/heatmap" element={<HeatmapPage />} />
            <Route path="/zones" element={<ZonesPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>

        <footer className="border-t border-slate-800 bg-slate-950 py-4 text-center text-xs text-slate-500">
          Two-Wheeler Illegal Parking Detection & Monitoring System • YOLOv8 + ByteTrack + Classical ML
        </footer>
      </div>
    </Router>
  );
}
