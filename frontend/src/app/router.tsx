import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
const OverviewPage = React.lazy(() => import("../features/overview/OverviewPage").then(module => ({ default: module.OverviewPage })));
const LiveTrafficPage = React.lazy(() => import("../features/live-traffic/LiveTrafficPage").then(module => ({ default: module.LiveTrafficPage })));
const MapPage = React.lazy(() => import("../features/map/MapPage").then(module => ({ default: module.MapPage })));
const AnalysisPage = React.lazy(() => import("../features/analysis/AnalysisPage").then(module => ({ default: module.AnalysisPage })));
const RouteAnalysisPage = React.lazy(() => import("../features/route-analysis/RouteAnalysisPage").then(module => ({ default: module.RouteAnalysisPage })));
const RoadsPage = React.lazy(() => import("../features/roads/RoadsPage").then(module => ({ default: module.RoadsPage })));
const IntersectionsPage = React.lazy(() => import("../features/intersections/IntersectionsPage").then(module => ({ default: module.IntersectionsPage })));
const PredictionsPage = React.lazy(() => import("../features/predictions/PredictionsPage").then(module => ({ default: module.PredictionsPage })));
const PredictionHistoryPage = React.lazy(() => import("../features/predictions/PredictionHistoryPage").then(module => ({ default: module.PredictionHistoryPage })));
const SystemStatusPage = React.lazy(() => import("../features/system/SystemStatusPage").then(module => ({ default: module.SystemStatusPage })));
const AlertsPage = React.lazy(() => import("../features/alerts/AlertsPage").then(module => ({ default: module.AlertsPage })));

export const AppRouter: React.FC = () => {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="overview" element={<OverviewPage />} />
        <Route path="live-traffic" element={<LiveTrafficPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="map" element={<MapPage />} />
        <Route path="analysis" element={<AnalysisPage />} />
        <Route path="route-analysis" element={<RouteAnalysisPage />} />
        <Route path="roads" element={<RoadsPage />} />
        <Route path="intersections" element={<IntersectionsPage />} />
        <Route path="predictions" element={<PredictionsPage />} />
        <Route path="predictions/history" element={<PredictionHistoryPage />} />
        <Route path="system" element={<SystemStatusPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
};
