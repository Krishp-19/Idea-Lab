import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { 
  ShieldAlert, 
  Video, 
  ListOrdered, 
  BarChart2, 
  MapPin, 
  Layers, 
  UploadCloud, 
  LogOut 
} from 'lucide-react';
import { api } from '../api/client';

export default function Navbar({ user, onLogout }) {
  const location = useLocation();

  const navItems = [
    { label: 'Live / Feed', path: '/', icon: Video },
    { label: 'Violations', path: '/violations', icon: ShieldAlert },
    { label: 'Trends', path: '/trends', icon: BarChart2 },
    { label: 'Heatmap', path: '/heatmap', icon: MapPin },
    { label: 'Zones', path: '/zones', icon: Layers },
    { label: 'Upload & Process', path: '/upload', icon: UploadCloud },
  ];

  return (
    <header className="bg-slate-800 border-b border-slate-700 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-3">
            <div className="h-9 w-9 rounded-lg bg-sky-600 flex items-center justify-center font-bold text-white shadow">
              🏍️
            </div>
            <div>
              <span className="font-semibold text-lg text-white tracking-wide">
                ParkWatch AI
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs bg-sky-950 text-sky-400 border border-sky-800 px-2 py-0.5 rounded-full">
                Two-Wheeler Monitoring
              </span>
            </div>
          </div>

          <nav className="hidden md:flex space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-slate-900 text-sky-400 border border-slate-700'
                      : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center space-x-4">
            {user ? (
              <div className="flex items-center space-x-3">
                <span className="text-xs text-slate-400 bg-slate-900 px-2.5 py-1 rounded-full border border-slate-700">
                  {user.username} ({user.role})
                </span>
                <button
                  onClick={onLogout}
                  title="Log out"
                  className="p-1.5 text-slate-400 hover:text-rose-400 rounded-lg hover:bg-slate-700/50"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <span className="text-xs text-slate-400 bg-emerald-950 text-emerald-400 border border-emerald-800 px-2 py-0.5 rounded">
                System Active
              </span>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
