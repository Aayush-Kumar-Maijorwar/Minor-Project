import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Activity, LayoutDashboard, Users, FilePlus2, Share2, History, AlertCircle, Settings, Info, Box } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppStore } from '@/store/useAppStore';
import { Badge } from '@/components/ui/badge';

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

export function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const demoMode = useAppStore(state => state.demoMode);
  
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
        {demoMode && (
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
            <div className="flex items-center space-x-2 text-sm text-slate-600">
              <span className="h-2 w-2 rounded-full bg-green-500"></span>
              <span>Systems Operational</span>
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
