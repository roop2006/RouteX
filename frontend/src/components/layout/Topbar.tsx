import React from "react";
import { Menu, ShieldCheck, ShieldAlert, RefreshCw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { checkBackendConnection } from "../../api/health";
import { useQuery } from "@tanstack/react-query";

interface TopbarProps {
  onMenuToggle: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({ onMenuToggle }) => {
  const queryClient = useQueryClient();

  const { data: isBackendHealthy, isLoading, isFetching } = useQuery({
    queryKey: ["backend-health-ping"],
    queryFn: checkBackendConnection,
    refetchInterval: 15000,
  });

  const handleRefreshAll = () => {
    queryClient.invalidateQueries();
  };

  return (
    <header className="sticky top-0 z-30 h-16 bg-slate-950/80 backdrop-blur-md border-b border-slate-800/80 px-4 sm:px-6 flex items-center justify-between">
      {/* Left: Mobile hamburger & title */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenuToggle}
          className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60 lg:hidden"
          aria-label="Toggle navigation"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="hidden sm:flex items-center gap-2 text-xs font-medium text-slate-400">
          <span className="w-2 h-2 rounded-full bg-blue-500"></span>
          <span>Urban Traffic Operations Center</span>
        </div>
      </div>

      {/* Right: Status indicators & actions */}
      <div className="flex items-center gap-3">
        {/* Backend Connectivity Badge */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border bg-slate-900/80">
          {isLoading ? (
            <span className="flex items-center gap-1.5 text-slate-400">
              <span className="w-2 h-2 rounded-full bg-slate-500 animate-pulse"></span>
              Checking backend...
            </span>
          ) : isBackendHealthy ? (
            <span className="flex items-center gap-1.5 text-emerald-400">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>FastAPI Connected</span>
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-rose-400">
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>Backend Offline</span>
            </span>
          )}
        </div>

        {/* Global Manual Refresh Button */}
        <button
          type="button"
          onClick={handleRefreshAll}
          title="Refresh dashboard data"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? "animate-spin text-blue-400" : ""}`} />
          <span className="hidden md:inline">Refresh</span>
        </button>
      </div>
    </header>
  );
};
