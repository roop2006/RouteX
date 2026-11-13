import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { OverviewPage } from "../features/overview/OverviewPage";
import { LiveTrafficPage } from "../features/live-traffic/LiveTrafficPage";
import { MapPage } from "../features/map/MapPage";
import { AnalysisPage } from "../features/analysis/AnalysisPage";
import { RouteAnalysisPage } from "../features/route-analysis/RouteAnalysisPage";
import { RoadsPage } from "../features/roads/RoadsPage";
import { IntersectionsPage } from "../features/intersections/IntersectionsPage";
import { PredictionsPage } from "../features/predictions/PredictionsPage";
import { PredictionHistoryPage } from "../features/predictions/PredictionHistoryPage";
import { SystemStatusPage } from "../features/system/SystemStatusPage";
import { AlertsPage } from "../features/alerts/AlertsPage";

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
