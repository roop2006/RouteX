import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Activity,
  Map as MapIcon,
  BarChart3,
  Route,
  Network,
  Sparkles,
  History,
  Server,
  Car,
  X,
  Navigation,
  BellRing,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { checkBackendConnection } from "../../api/health";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

interface NavItem {
  label: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

const navItems: NavItem[] = [
  { label: "Overview", path: "/", icon: LayoutDashboard },
  { label: "Live Traffic", path: "/live-traffic", icon: Activity, badge: "Live" },
  { label: "Traffic Alerts", path: "/alerts", icon: BellRing },
  { label: "Traffic Map", path: "/map", icon: MapIcon },
  { label: "Traffic Analysis", path: "/analysis", icon: BarChart3 },
  { label: "Route & Video Analysis", path: "/route-analysis", icon: Navigation, badge: "AI" },
  { label: "Roads", path: "/roads", icon: Route },
  { label: "Intersections", path: "/intersections", icon: Network },
  { label: "AI Predictions", path: "/predictions", icon: Sparkles },
  { label: "Prediction History", path: "/predictions/history", icon: History },
  { label: "System Status", path: "/system", icon: Server },
];

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { data: isBackendHealthy } = useQuery({
    queryKey: ["backend-health-ping"],
    queryFn: checkBackendConnection,
    refetchInterval: 15000,
  });
  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-slate-950/95 border-r border-slate-800/80 backdrop-blur flex flex-col transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Brand Header */}
        <div className="h-16 flex items-center justify-between px-5 border-b border-slate-800/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
              <Car className="w-5 h-5" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-white flex items-center gap-1">
                Route<span className="text-blue-500">X</span>
              </span>
              <span className="block text-[10px] uppercase tracking-wider font-semibold text-slate-400">
                Traffic Intelligence
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60 lg:hidden"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Links */}
        <div className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Navigation
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.path === "/"}
                onClick={() => {
                  if (window.innerWidth < 1024) onClose();
                }}
                className={({ isActive }) =>
                  `flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? "bg-blue-600/15 text-blue-400 border border-blue-500/30 shadow-sm shadow-blue-500/10"
                      : "text-slate-300 hover:text-white hover:bg-slate-900/80 border border-transparent"
                  }`
                }
              >
                <div className="flex items-center gap-3">
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className="px-1.5 py-0.5 text-[10px] font-bold rounded uppercase tracking-wider bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            );
          })}
        </div>

        {/* Footer info */}
        <div className="p-4 border-t border-slate-800/80 text-xs text-slate-400 space-y-1">
          <div className="flex items-center justify-between">
            <span>RouteX Engine</span>
            <span className="font-mono text-[11px] text-slate-300">Phase 9</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px]">
            <span
              className={`w-2 h-2 rounded-full ${
                isBackendHealthy ? "bg-emerald-500 animate-pulse" : "bg-rose-500"
              }`}
            />
            <span className={isBackendHealthy ? "text-slate-300" : "text-rose-400 font-medium"}>
              {isBackendHealthy ? "Backend Live :8001" : "Backend Offline"}
            </span>
          </div>
        </div>
      </aside>
    </>
  );
};
