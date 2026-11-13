import React, { useState } from "react";
import { Bell, Menu, ShieldCheck, ShieldAlert, RefreshCw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { checkBackendConnection } from "../../api/health";
import { useQuery } from "@tanstack/react-query";
import { useAlertNotifications, useMarkNotificationRead } from "../../hooks/useAlerts";
import { formatTimestamp } from "../../utils/formatters";

interface TopbarProps {
  onMenuToggle: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({ onMenuToggle }) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const { data: notifications } = useAlertNotifications();
  const markRead = useMarkNotificationRead();

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
        <div className="relative">
          <button
            type="button"
            aria-label={`Notifications${notifications?.unread_count ? `, ${notifications.unread_count} unread` : ""}`}
            aria-expanded={notificationsOpen}
            onClick={() => setNotificationsOpen((open) => !open)}
            className="relative rounded-lg border border-slate-700/60 bg-slate-900/80 p-2 text-slate-300 hover:bg-slate-800 hover:text-white"
          >
            <Bell className="h-4 w-4" />
            {Boolean(notifications?.unread_count) && <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[9px] font-bold text-white">{notifications?.unread_count}</span>}
          </button>
          {notificationsOpen && (
            <div className="absolute right-0 z-50 mt-2 w-80 rounded-xl border border-slate-700 bg-slate-950 p-3 shadow-2xl">
              <div className="mb-2 flex items-center justify-between"><h2 className="text-xs font-semibold text-white">Notifications</h2><span className="text-[10px] text-slate-400">{notifications?.unread_count ?? 0} unread</span></div>
              {!notifications?.notifications.length ? <p className="py-5 text-center text-xs text-slate-400">No unread alert notifications.</p> : <div className="max-h-80 space-y-1 overflow-y-auto">{notifications.notifications.map((notification) => (
                <button type="button" key={notification.id} onClick={() => {
                  if (!notification.is_read) markRead.mutate(notification.id);
                  setNotificationsOpen(false);
                  navigate("/alerts");
                }} className="block w-full rounded-lg p-2 text-left hover:bg-slate-900">
                  <span className="block text-xs font-medium text-white">{notification.title}</span>
                  <span className="mt-0.5 block truncate text-[11px] text-slate-300">{notification.message}</span>
                  <span className="mt-1 block text-[10px] text-slate-500">{formatTimestamp(notification.created_at)}</span>
                </button>
              ))}</div>}
              <Link to="/alerts" onClick={() => setNotificationsOpen(false)} className="mt-2 block border-t border-slate-800 pt-2 text-center text-xs text-blue-300 hover:text-blue-200">View alerts and history</Link>
            </div>
          )}
        </div>

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
