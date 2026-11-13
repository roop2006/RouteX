import React, { useState } from "react";
import { BellRing, Check, CheckCheck, Clock3, MapPin, Route, Settings2, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "../../components/layout/PageHeader";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { LoadingState } from "../../components/common/LoadingState";
import {
  useAlertActions,
  useAlertHistory,
  useAlertNotifications,
  useAlertRules,
  useAlertStatistics,
  useAlerts,
  usePatchAlertRule,
  useRouteAlerts,
} from "../../hooks/useAlerts";
import { useSelectedRoute } from "../../contexts/selectedRouteContext";
import type { AlertRule, TrafficAlert } from "../../types/alerts";
import { formatTimestamp } from "../../utils/formatters";

type AlertTab = "active" | "history" | "notifications" | "rules";

const severityClasses: Record<string, string> = {
  LOW: "border-slate-500/40 bg-slate-500/10 text-slate-300",
  MEDIUM: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  HIGH: "border-orange-500/40 bg-orange-500/10 text-orange-300",
  CRITICAL: "border-rose-500/50 bg-rose-500/15 text-rose-200",
};

function AlertCard({
  alert,
  distanceAlongRoute,
  routeSpecific,
  onAction,
  busy,
}: {
  alert: TrafficAlert;
  distanceAlongRoute?: number | null;
  routeSpecific?: boolean;
  onAction: (alertId: number, action: "acknowledge" | "resolve") => void;
  busy: boolean;
}) {
  return (
    <article className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3" data-alert-id={alert.id}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${severityClasses[alert.severity] || severityClasses.LOW}`}>
              {alert.severity}
            </span>
            <span className="text-[10px] uppercase tracking-wide text-slate-400">{alert.category.replaceAll("_", " ")}</span>
            {(routeSpecific || alert.route_id) && <span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] text-blue-300">Route-specific</span>}
          </div>
          <h3 className="mt-2 font-semibold text-white">{alert.title}</h3>
        </div>
        <span className="text-[11px] text-slate-400">{alert.status}</span>
      </div>

      <p className="text-sm text-slate-300">{alert.description}</p>

      <div className="flex flex-wrap gap-x-4 gap-y-2 text-[11px] text-slate-400">
        {(alert.road_name || alert.road_id) && <span><Route className="mr-1 inline h-3 w-3" />{alert.road_name || alert.road_id}</span>}
        {alert.intersection_id && <span><MapPin className="mr-1 inline h-3 w-3" />{alert.intersection_id}</span>}
        {alert.latitude != null && alert.longitude != null && <span>{alert.latitude.toFixed(4)}, {alert.longitude.toFixed(4)}</span>}
        {distanceAlongRoute != null && <span>{Math.round(distanceAlongRoute)} m along selected route</span>}
        <span>Source: {alert.source}</span>
        <span><Clock3 className="mr-1 inline h-3 w-3" />{formatTimestamp(alert.source_timestamp || alert.created_at)}</span>
      </div>

      {alert.status !== "RESOLVED" && (
        <div className="flex justify-end gap-2 border-t border-slate-800 pt-3">
          {alert.status === "ACTIVE" && (
            <button type="button" disabled={busy} onClick={() => onAction(alert.id, "acknowledge")} className="rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-50">
              <Check className="mr-1 inline h-3.5 w-3.5" />Acknowledge
            </button>
          )}
          <button type="button" disabled={busy} onClick={() => onAction(alert.id, "resolve")} className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-50">
            <CheckCheck className="mr-1 inline h-3.5 w-3.5" />Resolve
          </button>
        </div>
      )}
    </article>
  );
}

function AlertRuleCard({ rule, save, busy }: { rule: AlertRule; save: (ruleKey: string, patch: Partial<AlertRule>) => void; busy: boolean }) {
  const [thresholdText, setThresholdText] = useState(JSON.stringify(rule.thresholds, null, 2));
  const [cooldownText, setCooldownText] = useState(String(rule.cooldown_seconds));
  const [parseError, setParseError] = useState<string | null>(null);
  const saveThresholds = () => {
    try {
      const thresholds = JSON.parse(thresholdText) as Record<string, unknown>;
      setParseError(null);
      save(rule.rule_key, { thresholds });
    } catch {
      setParseError("Enter valid JSON thresholds before saving.");
    }
  };

  return (
    <article className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h3 className="text-sm font-semibold text-white">{rule.name}</h3><p className="text-[11px] text-slate-400">{rule.rule_key} · {rule.category}</p></div>
        <label className="flex items-center gap-2 text-xs text-slate-300">
          <input type="checkbox" checked={rule.enabled} disabled={busy} onChange={(event) => save(rule.rule_key, { enabled: event.target.checked })} />Enabled
        </label>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="text-[11px] text-slate-400">Severity
          <select value={rule.severity} disabled={busy} onChange={(event) => save(rule.rule_key, { severity: event.target.value as AlertRule["severity"] })} className="mt-1 block w-full rounded-md border border-slate-700 bg-slate-950 p-2 text-xs text-white">
            {(["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const).map((severity) => <option key={severity}>{severity}</option>)}
          </select>
        </label>
        <label className="text-[11px] text-slate-400">Cooldown (seconds)
          <div className="mt-1 flex gap-2"><input type="number" min={0} max={86400} value={cooldownText} disabled={busy} onChange={(event) => setCooldownText(event.target.value)} className="block w-full rounded-md border border-slate-700 bg-slate-950 p-2 text-xs text-white" /><button type="button" disabled={busy || !Number.isFinite(Number(cooldownText)) || Number(cooldownText) < 0 || Number(cooldownText) > 86400} onClick={() => save(rule.rule_key, { cooldown_seconds: Number(cooldownText) })} className="rounded-md border border-slate-700 px-2 text-[10px] text-slate-200 hover:bg-slate-800 disabled:opacity-50">Save</button></div>
        </label>
      </div>
      <details>
        <summary className="cursor-pointer text-xs text-blue-300">Threshold configuration</summary>
        <textarea value={thresholdText} onChange={(event) => setThresholdText(event.target.value)} rows={4} className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 p-2 font-mono text-[11px] text-slate-200" aria-label={`${rule.name} thresholds JSON`} />
        {parseError && <p className="text-xs text-rose-300">{parseError}</p>}
        <button type="button" disabled={busy} onClick={saveThresholds} className="mt-2 rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-800 disabled:opacity-50">Save thresholds</button>
      </details>
    </article>
  );
}

export const AlertsPage: React.FC = () => {
  const [tab, setTab] = useState<AlertTab>("active");
  const route = useSelectedRoute();
  const hasRoute = Boolean(route.selectedRoute && route.routeId && route.geometry);
  const activeQuery = useAlerts({}, tab === "active" && !hasRoute);
  const routeQuery = useRouteAlerts(hasRoute ? route.routeId : null, hasRoute ? route.geometry as Record<string, unknown> : null, tab === "active");
  const historyQuery = useAlertHistory(tab === "history");
  const notificationsQuery = useAlertNotifications(tab === "notifications");
  const rulesQuery = useAlertRules();
  const statisticsQuery = useAlertStatistics();
  const alertAction = useAlertActions();
  const rulePatch = usePatchAlertRule();

  const activeAlerts = activeQuery.data || [];
  const matchedAlerts = routeQuery.data || [];
  const routeAlertIds = new Set(matchedAlerts.map((item) => item.alert.id));
  const generalAlerts = hasRoute ? activeAlerts.filter((item) => !routeAlertIds.has(item.id) && !item.route_id) : activeAlerts;

  const tabs: { id: AlertTab; label: string }[] = [
    { id: "active", label: "Active alerts" },
    { id: "history", label: "History" },
    { id: "notifications", label: "Notifications" },
    { id: "rules", label: "Rules" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Traffic Alerts"
        subtitle={hasRoute ? "Active alerts matched against the selected route corridor, with citywide alerts kept separate" : "Validated traffic conditions and incidents with acknowledgement and resolution history"}
        badge={<span className="rounded-full border border-blue-500/20 bg-blue-500/10 px-2.5 py-1 text-xs text-blue-300"><BellRing className="mr-1 inline h-3.5 w-3.5" />{statisticsQuery.data?.active ?? 0} active</span>}
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[["Active", statisticsQuery.data?.active], ["Acknowledged", statisticsQuery.data?.acknowledged], ["Resolved", statisticsQuery.data?.resolved], ["Unread", statisticsQuery.data?.unread_notifications]].map(([label, value]) => (
          <div key={String(label)} className="rounded-lg border border-slate-800 bg-slate-900/50 p-3"><span className="text-[11px] text-slate-400">{label}</span><strong className="mt-1 block text-xl text-white">{value ?? "—"}</strong></div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-2">
        {tabs.map((item) => <button type="button" key={item.id} onClick={() => setTab(item.id)} className={`rounded-md px-3 py-2 text-xs ${tab === item.id ? "bg-blue-600 text-white" : "text-slate-400 hover:bg-slate-800 hover:text-white"}`}>{item.label}</button>)}
      </div>

      {tab === "active" && (
        <div className="space-y-6">
          {hasRoute && (
            <section className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div><h2 className="text-sm font-semibold text-white"><Route className="mr-1.5 inline h-4 w-4 text-blue-300" />Selected route alerts</h2><p className="text-[11px] text-slate-400">{route.origin?.name || "Origin"} → {route.destination?.name || "Destination"} · corridor matched from current route geometry</p></div>
                <span className="text-xs text-slate-400">{matchedAlerts.length} matched</span>
              </div>
              {routeQuery.isLoading ? <LoadingState message="Matching alerts to the selected route..." skeletonLines={2} /> : routeQuery.error ? <ErrorState title="Route Alerts Unavailable" error={routeQuery.error} onRetry={() => routeQuery.refetch()} /> : matchedAlerts.length === 0 ? <EmptyState title="No Active Alerts Along This Route" description="No active traffic alerts fall within the configured route corridor." /> : matchedAlerts.map((item) => <AlertCard key={item.alert.id} alert={item.alert} routeSpecific distanceAlongRoute={item.distance_along_route_meters} busy={alertAction.isPending} onAction={(alertId, action) => alertAction.mutate({ alertId, action })} />)}
            </section>
          )}

          <section className="space-y-3">
            <div className="flex items-center justify-between"><h2 className="text-sm font-semibold text-white">{hasRoute ? "Citywide alerts" : "Active and acknowledged alerts"}</h2><span className="text-xs text-slate-400">{generalAlerts.length} alerts</span></div>
            {activeQuery.isLoading ? <LoadingState message="Loading active alerts..." skeletonLines={3} /> : activeQuery.error ? <ErrorState title="Alerts Unavailable" error={activeQuery.error} onRetry={() => activeQuery.refetch()} /> : generalAlerts.length === 0 ? <EmptyState title="No Active Traffic Alerts" description="The enabled rules have not matched a current traffic observation." /> : generalAlerts.map((alert) => <AlertCard key={alert.id} alert={alert} busy={alertAction.isPending} onAction={(alertId, action) => alertAction.mutate({ alertId, action })} />)}
          </section>
        </div>
      )}

      {tab === "history" && (
        historyQuery.isLoading ? <LoadingState message="Loading alert history..." skeletonLines={3} /> : historyQuery.error ? <ErrorState title="Alert History Unavailable" error={historyQuery.error} onRetry={() => historyQuery.refetch()} /> : !historyQuery.data?.length ? <EmptyState title="No Alert History" description="Resolved and acknowledged alerts will appear here." /> : <div className="space-y-3">{historyQuery.data.map((alert) => <AlertCard key={alert.id} alert={alert} busy={alertAction.isPending} onAction={(alertId, action) => alertAction.mutate({ alertId, action })} />)}</div>
      )}

      {tab === "notifications" && (
        notificationsQuery.isLoading ? <LoadingState message="Loading notification history..." skeletonLines={3} /> : notificationsQuery.error ? <ErrorState title="Notifications Unavailable" error={notificationsQuery.error} onRetry={() => notificationsQuery.refetch()} /> : !notificationsQuery.data?.notifications.length ? <EmptyState title="No Notifications" description="New alert notifications will appear here." /> : <div className="space-y-2">{notificationsQuery.data.notifications.map((notification) => <div key={notification.id} className={`flex items-start justify-between gap-3 rounded-lg border p-3 ${notification.is_read ? "border-slate-800 bg-slate-900/40" : "border-blue-500/30 bg-blue-950/20"}`}><div><p className="text-sm font-medium text-white">{notification.title}</p><p className="mt-1 text-xs text-slate-300">{notification.message}</p><p className="mt-1 text-[10px] text-slate-500">{formatTimestamp(notification.created_at)}</p></div>{!notification.is_read && <span className="rounded-full bg-blue-500 px-2 py-0.5 text-[10px] text-white">Unread</span>}</div>)}</div>
      )}

      {tab === "rules" && (
        rulesQuery.isLoading ? <LoadingState message="Loading alert rules..." skeletonLines={3} /> : rulesQuery.error ? <ErrorState title="Alert Rules Unavailable" error={rulesQuery.error} onRetry={() => rulesQuery.refetch()} /> : <div className="space-y-3"><div className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-xs text-slate-400"><Settings2 className="mr-1.5 inline h-4 w-4 text-blue-300" />Thresholds and cooldowns apply to validated observations. Rule changes are stored in PostgreSQL.</div>{(rulesQuery.data || []).map((rule) => <AlertRuleCard key={rule.rule_key} rule={rule} busy={rulePatch.isPending} save={(ruleKey, patch) => rulePatch.mutate({ ruleKey, patch })} />)}</div>
      )}

      <div className="text-[11px] text-slate-500"><ShieldAlert className="mr-1 inline h-3.5 w-3.5" />Alerts retain source provenance. Historical video detections are not labeled as current TomTom traffic.</div>
      <Link to="/live-traffic" className="sr-only">Return to Live Traffic</Link>
    </div>
  );
};
