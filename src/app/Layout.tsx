import React, { useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Activity, LayoutDashboard, Users, FilePlus2, Share2, History, AlertCircle, Settings, Info, Box, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { useBackendStatus, backendStatusLevel } from '@/features/useBackendStatus';
import { useOnClickOutside } from '@/features/useOnClickOutside';

const navItems = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Patients', path: '/patients', icon: Users },
  { name: 'New Analysis', path: '/analysis/new', icon: FilePlus2 },
  { name: 'Fusion Analysis', path: '/fusion', icon: Share2 },
  { name: 'History', path: '/history', icon: History },
  { name: 'Risk Flags', path: '/flags', icon: AlertCircle },
  { name: 'Models', path: '/models', icon: Box },
];

const bottomItems = [
  { name: 'About', path: '/about', icon: Info },
  { name: 'Settings', path: '/settings', icon: Settings },
];

const STATUS_STYLES: Record<string, { dot: string; text: string; label: (n: number, total: number) => string }> = {
  connected: { dot: 'bg-green-500', text: 'text-slate-600', label: (n, total) => `Backend connected — ${n} of ${total} models loaded` },
  degraded: { dot: 'bg-amber-500', text: 'text-amber-700', label: (n, total) => `Some models missing (${n} of ${total} loaded)` },
  offline: { dot: 'bg-red-500', text: 'text-red-700', label: () => 'Backend offline' },
  loading: { dot: 'bg-slate-300 animate-pulse', text: 'text-slate-400', label: () => 'Checking backend…' }
};

const MOCK_MODE = import.meta.env.VITE_INFERENCE_MODE === 'mock';

export function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const { data: health, isError, isLoading } = useBackendStatus();
  const level = backendStatusLevel(health, isError, isLoading);
  const style = STATUS_STYLES[level];
  const loadedCount = health?.models.filter(m => m.state === 'loaded').length ?? 0;
  const totalCount = health?.models.length ?? 0;
  const [popoverOpen, setPopoverOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);
  useOnClickOutside(popoverRef, () => setPopoverOpen(false), popoverOpen);

  if (location.pathname === '/login') {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Sidebar */}
      <aside className="w-64 flex flex-col border-r border-slate-200 bg-white">
        <div className="flex h-16 shrink-0 items-center px-6 border-b border-slate-200">
          <Activity className="h-6 w-6 text-teal-600 mr-2" />
          <span className="text-xl font-bold text-slate-900 tracking-tight">Med<span className="text-teal-600">Fusion</span></span>
        </div>
        
        <nav className="flex-1 space-y-1 px-3 py-4 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
            return (
              <Link
                key={item.name}
                to={item.path}
                className={cn(
                  "flex items-center px-3 py-2 text-sm font-medium rounded-md group transition-colors",
                  isActive 
                    ? "bg-teal-50 text-teal-700" 
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                )}
              >
                <item.icon className={cn("mr-3 h-5 w-5 flex-shrink-0", isActive ? "text-teal-600" : "text-slate-400 group-hover:text-slate-500")} />
                {item.name}
              </Link>
            );
          })}
        </nav>
        
        <div className="border-t border-slate-200 p-3 space-y-1">
          {bottomItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.name}
                to={item.path}
                className={cn(
                  "flex items-center px-3 py-2 text-sm font-medium rounded-md group transition-colors",
                  isActive 
                    ? "bg-slate-100 text-slate-900" 
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                )}
              >
                <item.icon className={cn("mr-3 h-5 w-5 flex-shrink-0", isActive ? "text-slate-600" : "text-slate-400 group-hover:text-slate-500")} />
                {item.name}
              </Link>
            );
          })}
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col relative overflow-hidden">
        {/* Top Banner */}
        {MOCK_MODE && (
          <div className="bg-teal-700 px-4 py-1.5 text-center flex items-center justify-center shrink-0">
            <span className="text-teal-50 text-sm font-medium">Demo Mode — Synthetic Data</span>
          </div>
        )}
        
        {/* Top Header */}
        <header className="h-14 shrink-0 border-b border-slate-200 bg-white flex items-center justify-between px-6">
          <div className="flex items-center text-sm text-slate-500">
            <span className="font-medium text-slate-900 capitalize">
              {location.pathname === '/' ? 'Dashboard' : location.pathname.split('/')[1]}
            </span>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="relative" ref={popoverRef}>
              <button
                type="button"
                onClick={() => setPopoverOpen(o => !o)}
                className={cn("flex items-center space-x-2 text-sm rounded-md px-1.5 py-1 hover:bg-slate-50", style.text)}
                title={style.label(loadedCount, totalCount)}
              >
                <span className={cn("h-2 w-2 rounded-full shrink-0", style.dot)}></span>
                <span>{style.label(loadedCount, totalCount)}</span>
              </button>
              {popoverOpen && (
                <div className="absolute right-0 mt-2 w-80 bg-white border border-slate-200 rounded-md shadow-lg z-50 p-3 space-y-2">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide px-1">Models</div>
                  {health?.models.length ? health.models.map(m => {
                    const StateIcon = m.state === 'loaded' ? CheckCircle2 : m.state === 'error' ? AlertTriangle : XCircle;
                    const stateColor = m.state === 'loaded' ? 'text-green-600' : m.state === 'error' ? 'text-amber-600' : 'text-slate-400';
                    return (
                      <div key={m.id} className="flex items-start space-x-2 px-1 py-1 text-xs">
                        <StateIcon className={cn("w-3.5 h-3.5 mt-0.5 shrink-0", stateColor)} />
                        <div>
                          <div className="font-medium text-slate-800">{m.id} <span className="text-slate-400">({m.state})</span></div>
                          {m.reason && <div className="text-slate-500">{m.reason}</div>}
                          {m.source && <div className="text-slate-400">source: {m.source}</div>}
                        </div>
                      </div>
                    );
                  }) : <div className="text-xs text-slate-400 px-1">No model status available.</div>}
                </div>
              )}
            </div>
            <div className="h-8 w-8 rounded-full bg-slate-200 flex items-center justify-center text-slate-600 font-medium">
              Dr
            </div>
          </div>
        </header>
        
        <div className="flex-1 overflow-auto bg-slate-50 p-6 md:p-8">
          <div className="max-w-6xl mx-auto">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
