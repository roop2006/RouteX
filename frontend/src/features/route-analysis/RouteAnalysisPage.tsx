import React, { useRef, useState } from "react";
import {
  Navigation,
  Video,
  Layers,
  Play,
  RotateCw,
  XCircle,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  UploadCloud,
  FileVideo,
  Route as RouteIcon,
  ShieldAlert,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
} from "recharts";
import { PageHeader } from "../../components/layout/PageHeader";
import { ErrorState } from "../../components/common/ErrorState";
import { RouteMap } from "./components/RouteMap";
import {
  useLocationSuggestions,
  useRouteAnalysis,
  useVideoUpload,
  useSampleVideoAnalysis,
  useVideoAnalysisStatus,
  useCancelVideoAnalysis,
  useCombinedAnalysis,
} from "../../hooks/useUserAnalysis";
import { useRoads, useIntersections, useZones } from "../../hooks/useGeography";
import type {
  RouteCoordinates,
  RouteAlternative,
  RouteAnalysisResponse,
  CombinedAnalysisResponse,
} from "../../types/userAnalysis";
import { getCongestionBadgeClass } from "../../utils/congestion";

type ActiveTab = "route" | "video" | "integrated";

const PRESET_QUICK_POINTS: { name: string; lat: number; lng: number }[] = [
  { name: "RouteX Test Intersection (INT_001)", lat: 13.0827, lng: 80.2707 },
  { name: "Chennai Central Junction", lat: 13.0824, lng: 80.2755 },
  { name: "Egmore Station Corridor", lat: 13.0782, lng: 80.2608 },
  { name: "Anna Nagar Roundtana", lat: 13.0850, lng: 80.2100 },
  { name: "T. Nagar Panagal Park", lat: 13.0405, lng: 80.2337 },
  { name: "Guindy Corridor", lat: 13.0067, lng: 80.2026 },
];

export const RouteAnalysisPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>("route");

  // Route Form State
  const [originText, setOriginText] = useState("RouteX Test Intersection (INT_001)");
  const [originCoords, setOriginCoords] = useState<RouteCoordinates | null>({
    lat: 13.0827,
    lng: 80.2707,
    name: "RouteX Test Intersection (INT_001)",
  });
  const [destText, setDestText] = useState("Chennai Central Junction");
  const [destCoords, setDestCoords] = useState<RouteCoordinates | null>({
    lat: 13.0824,
    lng: 80.2755,
    name: "Chennai Central Junction",
  });

  const [mapClickMode, setMapClickMode] = useState<"origin" | "destination" | null>(null);
  const [activeSearchTarget, setActiveSearchTarget] = useState<"origin" | "destination" | null>(null);

  // Video Form State - Defaults to Standalone camera (unassociated unless user chooses an intersection)
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [videoIntersectionId, setVideoIntersectionId] = useState("STANDALONE_CAMERA");
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Analysis Results State
  const [routeResult, setRouteResult] = useState<RouteAnalysisResponse | null>(null);
  const [activeAlternative, setActiveAlternative] = useState<RouteAlternative | null>(null);
  const [combinedResult, setCombinedResult] = useState<CombinedAnalysisResponse | null>(null);

  // Queries & Mutations
  const searchQuery =
    activeSearchTarget === "origin" ? originText : activeSearchTarget === "destination" ? destText : "";
  const { data: suggestions = [] } = useLocationSuggestions(
    searchQuery,
    Boolean(activeSearchTarget)
  );
  const { data: roads = [] } = useRoads();
  const { data: intersections = [] } = useIntersections();
  const { data: zones = [] } = useZones();

  const routeMutation = useRouteAnalysis();
  const uploadMutation = useVideoUpload();
  const sampleVideoMutation = useSampleVideoAnalysis();
  const cancelMutation = useCancelVideoAnalysis();
  const combinedMutation = useCombinedAnalysis();

  const { data: jobStatus } = useVideoAnalysisStatus(activeJobId);

  // Derive video result strictly isolated by active workflow mode to prevent stale cross-tab leaking
  const videoResult =
    activeTab === "integrated"
      ? combinedResult?.video_analysis || (jobStatus?.status === "COMPLETED" ? jobStatus.result : null)
      : jobStatus?.status === "COMPLETED"
      ? jobStatus.result
      : null;

  // Handle map clicks for pin placement
  const handleMapClick = (
    lat: number,
    lng: number,
    customName?: string,
    forceTarget?: "origin" | "destination"
  ) => {
    const targetMode = forceTarget || mapClickMode;

    const coords: RouteCoordinates = {
      lat: Number(lat.toFixed(5)),
      lng: Number(lng.toFixed(5)),
      name: customName || `Custom Point (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
    };

    if (targetMode === "origin") {
      setOriginCoords(coords);
      setOriginText(coords.name || "");
      setMapClickMode(null);
    } else if (targetMode === "destination") {
      setDestCoords(coords);
      setDestText(coords.name || "");
      setMapClickMode(null);
    } else {
      // Direct click on map when no mode was explicitly selected:
      if (!originCoords) {
        setOriginCoords(coords);
        setOriginText(coords.name || "");
      } else {
        setDestCoords(coords);
        setDestText(coords.name || "");
      }
    }
  };

  const sameLocationSelected =
    Boolean(originCoords) &&
    Boolean(destCoords) &&
    originCoords !== null &&
    destCoords !== null &&
    Math.abs(originCoords.lat - destCoords.lat) < 1e-6 &&
    Math.abs(originCoords.lng - destCoords.lng) < 1e-6;

  // Submit Route Analysis
  const handleRunRouteAnalysis = () => {
    if (!originCoords || !destCoords || sameLocationSelected) return;
    setRouteResult(null);
    routeMutation.mutate(
      {
        origin: originCoords,
        destination: destCoords,
        include_alternatives: true,
      },
      {
        onSuccess: (data) => {
          setRouteResult(data);
          setActiveAlternative(data.selected_route);
        },
      }
    );
  };

  // Submit Video Upload
  const handleUploadVideo = () => {
    if (!selectedFile) return;
    setActiveJobId(null);
    setCombinedResult(null);
    uploadMutation.mutate(
      { file: selectedFile, intersectionId: videoIntersectionId },
      {
        onSuccess: (data) => {
          setActiveJobId(data.job_id);
        },
      }
    );
  };

  // Run Sample Video directly
  const handleRunSampleVideo = () => {
    setActiveJobId(null);
    setCombinedResult(null);
    sampleVideoMutation.mutate(
      { videoPath: "data/videos/traffic.mp4", intersectionId: videoIntersectionId },
      {
        onSuccess: (data) => {
          setActiveJobId(data.job_id);
        },
      }
    );
  };

  // Cancel Video Job
  const handleCancelJob = () => {
    if (activeJobId) {
      cancelMutation.mutate(activeJobId);
    }
  };

  const handleClearSelectedFile = () => {
    setSelectedFile(null);
    setActiveJobId(null);
    setCombinedResult(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // Run Combined Analysis
  const handleRunCombined = () => {
    if (!originCoords || !destCoords || !activeJobId || jobStatus?.status !== "COMPLETED") return;
    setCombinedResult(null);
    combinedMutation.mutate(
      {
        route_request: {
          origin: originCoords,
          destination: destCoords,
          include_alternatives: true,
        },
        video_job_id: activeJobId,
      },
      {
        onSuccess: (data) => {
          setCombinedResult(data);
          setRouteResult(data.route_analysis);
        },
      }
    );
  };

  const isVideoProcessing = jobStatus?.status === "PROCESSING" || jobStatus?.status === "PENDING";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Intelligent Route & Traffic Analysis"
        subtitle="User-driven origin-to-destination routing, custom video AI analysis, and corridor intelligence"
        badge={
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            Interactive AI Engine
          </span>
        }
      />

      {/* Workflow Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
        <button
          type="button"
          onClick={() => setActiveTab("route")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
            activeTab === "route"
              ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
              : "text-slate-400 hover:text-white hover:bg-slate-900"
          }`}
        >
          <RouteIcon className="w-4 h-4" />
          <span>Route Intelligence</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("video")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
            activeTab === "video"
              ? "bg-blue-600 text-white shadow-lg shadow-blue-600/20"
              : "text-slate-400 hover:text-white hover:bg-slate-900"
          }`}
        >
          <Video className="w-4 h-4" />
          <span>Video Analysis</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("integrated")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
            activeTab === "integrated"
              ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20"
              : "text-slate-400 hover:text-white hover:bg-slate-900"
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Integrated Analysis</span>
        </button>
      </div>

      {/* Main Grid: Inputs & Map */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Control Form Panel */}
        <div className="lg:col-span-5 space-y-5">
          {/* 1. Origin & Destination Card */}
          {(activeTab === "route" || activeTab === "integrated") && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Navigation className="w-4 h-4 text-blue-400" />
                  <span>Route Parameters</span>
                </h3>
                <span className="text-xs text-slate-400">PostGIS Corridor</span>
              </div>

              {/* Origin Input */}
              <div className="space-y-1.5 relative">
                <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 flex items-center justify-center text-[8px] text-white font-bold">A</span>
                    Origin / Start Location
                  </span>
                  <div className="flex items-center gap-1.5">
                    {originCoords && (
                      <button
                        type="button"
                        onClick={() => {
                          setOriginCoords(null);
                          setOriginText("");
                        }}
                        className="text-[11px] px-2 py-0.5 rounded text-slate-400 hover:text-slate-200 bg-slate-800"
                      >
                        Clear
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setMapClickMode(mapClickMode === "origin" ? null : "origin")}
                      className={`text-[11px] px-2 py-0.5 rounded transition-colors ${
                        mapClickMode === "origin"
                          ? "bg-emerald-600 text-white font-bold"
                          : "text-slate-400 hover:text-slate-200 bg-slate-800"
                      }`}
                    >
                      {mapClickMode === "origin" ? "Cancel Pick" : "Pick on Map"}
                    </button>
                  </div>
                </label>

                <div className="relative">
                  <input
                    type="text"
                    value={originText}
                    onChange={(e) => {
                      setOriginText(e.target.value);
                      setActiveSearchTarget("origin");
                    }}
                    onFocus={() => setActiveSearchTarget("origin")}
                    placeholder="Search intersection, road, or landmark..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                  />
                  {originCoords && (
                    <span className="absolute right-3 top-2.5 text-[10px] font-mono text-emerald-400">
                      {originCoords.lat.toFixed(3)}, {originCoords.lng.toFixed(3)}
                    </span>
                  )}
                </div>

                {/* Suggestions Dropdown */}
                {activeSearchTarget === "origin" && suggestions.length > 0 && (
                  <div className="absolute z-50 left-0 right-0 mt-1 bg-slate-900 border border-slate-800 rounded-lg shadow-xl max-h-48 overflow-y-auto">
                    {suggestions.map((item) => (
                      <button
                        key={`orig-${item.id}`}
                        type="button"
                        onClick={() => {
                          setOriginCoords({ lat: item.lat, lng: item.lng, name: item.name });
                          setOriginText(item.name);
                          setActiveSearchTarget(null);
                        }}
                        className="w-full text-left px-3 py-2 text-xs hover:bg-slate-800/80 border-b border-slate-800/50 flex flex-col"
                      >
                        <span className="font-semibold text-white">{item.name}</span>
                        <span className="text-[10px] text-slate-400">{item.description}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Destination Input */}
              <div className="space-y-1.5 relative">
                <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-500 flex items-center justify-center text-[8px] text-white font-bold">B</span>
                    Destination / End Location
                  </span>
                  <div className="flex items-center gap-1.5">
                    {destCoords && (
                      <button
                        type="button"
                        onClick={() => {
                          setDestCoords(null);
                          setDestText("");
                        }}
                        className="text-[11px] px-2 py-0.5 rounded text-slate-400 hover:text-slate-200 bg-slate-800"
                      >
                        Clear
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => setMapClickMode(mapClickMode === "destination" ? null : "destination")}
                      className={`text-[11px] px-2 py-0.5 rounded transition-colors ${
                        mapClickMode === "destination"
                          ? "bg-rose-600 text-white font-bold"
                          : "text-slate-400 hover:text-slate-200 bg-slate-800"
                      }`}
                    >
                      {mapClickMode === "destination" ? "Cancel Pick" : "Pick on Map"}
                    </button>
                  </div>
                </label>

                <div className="relative">
                  <input
                    type="text"
                    value={destText}
                    onChange={(e) => {
                      setDestText(e.target.value);
                      setActiveSearchTarget("destination");
                    }}
                    onFocus={() => setActiveSearchTarget("destination")}
                    placeholder="Search destination junction..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                  />
                  {destCoords && (
                    <span className="absolute right-3 top-2.5 text-[10px] font-mono text-rose-400">
                      {destCoords.lat.toFixed(3)}, {destCoords.lng.toFixed(3)}
                    </span>
                  )}
                </div>

                {/* Suggestions Dropdown */}
                {activeSearchTarget === "destination" && suggestions.length > 0 && (
                  <div className="absolute z-50 left-0 right-0 mt-1 bg-slate-900 border border-slate-800 rounded-lg shadow-xl max-h-48 overflow-y-auto">
                    {suggestions.map((item) => (
                      <button
                        key={`dest-${item.id}`}
                        type="button"
                        onClick={() => {
                          setDestCoords({ lat: item.lat, lng: item.lng, name: item.name });
                          setDestText(item.name);
                          setActiveSearchTarget(null);
                        }}
                        className="w-full text-left px-3 py-2 text-xs hover:bg-slate-800/80 border-b border-slate-800/50 flex flex-col"
                      >
                        <span className="font-semibold text-white">{item.name}</span>
                        <span className="text-[10px] text-slate-400">{item.description}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Quick Preset Location Chips */}
              <div className="pt-2 border-t border-slate-800/60">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block mb-1.5">
                  RouteX Junction Presets
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {PRESET_QUICK_POINTS.slice(0, 4).map((preset) => (
                    <button
                      key={preset.name}
                      type="button"
                      onClick={() => {
                        if (activeSearchTarget === "origin") {
                          setOriginCoords(preset);
                          setOriginText(preset.name);
                        } else if (activeSearchTarget === "destination") {
                          setDestCoords(preset);
                          setDestText(preset.name);
                        } else if (!originCoords) {
                          setOriginCoords(preset);
                          setOriginText(preset.name);
                        } else if (originCoords.name === preset.name) {
                          // Already set as origin, keep it
                        } else {
                          setDestCoords(preset);
                          setDestText(preset.name);
                        }
                      }}
                      className="px-2 py-1 rounded bg-slate-800/60 hover:bg-slate-800 text-[11px] text-slate-300 transition-colors"
                    >
                      {preset.name.split(" ")[0]}
                    </button>
                  ))}
                </div>
              </div>

              {/* Action Button for Route */}
              {activeTab === "route" && (
                <>
                  {(!originCoords || !destCoords) && (
                    <p className="text-[11px] text-amber-300">Select both an origin and a destination before calculating a route.</p>
                  )}
                  {sameLocationSelected && (
                    <p className="text-[11px] text-amber-300">Origin and destination must be different locations.</p>
                  )}
                  <button
                    type="button"
                    onClick={handleRunRouteAnalysis}
                    disabled={routeMutation.isPending || !originCoords || !destCoords || sameLocationSelected}
                    className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold text-xs transition-colors flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20"
                  >
                    <RouteIcon className={`w-4 h-4 ${routeMutation.isPending ? "animate-spin" : ""}`} />
                    <span>{routeMutation.isPending ? "Calculating Route..." : "Analyze Route"}</span>
                  </button>
                  {routeMutation.isError && (
                    <ErrorState
                      title="Route calculation failed"
                      error={routeMutation.error}
                      onRetry={handleRunRouteAnalysis}
                      className="p-4"
                    />
                  )}
                </>
              )}
            </div>
          )}

          {/* 2. Video Analysis Input Card */}
          {(activeTab === "video" || activeTab === "integrated") && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Video className="w-4 h-4 text-indigo-400" />
                  <span>Traffic Video Analysis</span>
                </h3>
                <span className="text-xs text-slate-400">YOLO + Vision AI</span>
              </div>

              {/* File Upload Zone */}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-300 block">
                  Select Traffic Video File (.mp4, .avi, .mov, .mkv)
                </label>
                <div className="border-2 border-dashed border-slate-800 hover:border-slate-700 rounded-xl p-4 text-center transition-colors bg-slate-950/40">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".mp4,.avi,.mov,.mkv"
                    id="traffic-video-file-input"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setSelectedFile(e.target.files[0]);
                      }
                    }}
                    className="hidden"
                  />
                  <label htmlFor="traffic-video-file-input" className="cursor-pointer space-y-2 block">
                    <UploadCloud className="w-8 h-8 text-blue-400 mx-auto" />
                    <div className="text-xs text-slate-300">
                      {selectedFile ? (
                        <span className="font-semibold text-emerald-400 flex items-center justify-center gap-1.5">
                          <FileVideo className="w-4 h-4" />
                          {selectedFile.name} ({(selectedFile.size / (1024 * 1024)).toFixed(1)} MB)
                        </span>
                      ) : (
                        <span>Click to browse or drag & drop video</span>
                      )}
                    </div>
                    <span className="text-[10px] text-slate-400 block">Max size: 100MB</span>
                  </label>
                  {selectedFile && (
                    <button
                      type="button"
                      onClick={handleClearSelectedFile}
                      className="mt-2 text-[11px] text-slate-400 hover:text-white"
                    >
                      Remove selected file
                    </button>
                  )}
                </div>
              </div>

              {/* Associated Intersection Selector */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-300 block">
                  Associated Camera / Intersection
                </label>
                <select
                  value={videoIntersectionId}
                  onChange={(e) => setVideoIntersectionId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                >
                  <option value="STANDALONE_CAMERA">Standalone / no location metadata (Independent upload)</option>
                  <option value="INT_001">INT_001 - RouteX Test Intersection (Monitored)</option>
                  {intersections
                    .filter((i) => i.intersection_id !== "INT_001")
                    .map((i) => (
                      <option key={i.intersection_id} value={i.intersection_id}>
                        {i.intersection_id} - {i.name}
                      </option>
                    ))}
                </select>
                <p className="text-[10px] text-slate-500">
                  Combined analysis requires a real intersection on the selected corridor. Standalone recordings stay independent.
                </p>
              </div>

              {/* Action Buttons */}
              <div className="space-y-2 pt-2">
                <button
                  type="button"
                  onClick={handleUploadVideo}
                  disabled={uploadMutation.isPending || !selectedFile || isVideoProcessing}
                  className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold text-xs transition-colors flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20"
                >
                  <Play className={`w-4 h-4 ${uploadMutation.isPending ? "animate-spin" : ""}`} />
                  <span>{uploadMutation.isPending ? "Uploading..." : "Process Uploaded Video"}</span>
                </button>
                {uploadMutation.isError && (
                  <ErrorState title="Video upload failed" error={uploadMutation.error} className="p-4" />
                )}
                {sampleVideoMutation.isError && (
                  <ErrorState title="Sample video analysis failed" error={sampleVideoMutation.error} className="p-4" />
                )}

                <button
                  type="button"
                  onClick={handleRunSampleVideo}
                  disabled={sampleVideoMutation.isPending || isVideoProcessing}
                  className="w-full py-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 font-medium text-xs transition-colors flex items-center justify-center gap-2 border border-slate-700/60"
                >
                  <FileVideo className="w-3.5 h-3.5 text-blue-400" />
                  <span>Analyze Server Sample (traffic.mp4)</span>
                </button>
              </div>

              {/* Active Processing Progress Card */}
              {isVideoProcessing && jobStatus && (
                <div className="p-3.5 rounded-lg border border-blue-500/30 bg-blue-950/20 space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-blue-400 flex items-center gap-1.5">
                      <RotateCw className="w-3.5 h-3.5 animate-spin text-blue-400" />
                      YOLO Detection & Tracking
                    </span>
                    <span className="font-mono font-bold text-white">{jobStatus.progress_percent}%</span>
                  </div>

                  {/* Progress Bar */}
                  <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-300"
                      style={{ width: `${jobStatus.progress_percent}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    <span>
                      Frames: {jobStatus.frames_processed} / {jobStatus.total_frames || "?"}
                    </span>
                    <span>Speed: {jobStatus.current_fps} FPS</span>
                    <button
                      type="button"
                      onClick={handleCancelJob}
                      className="text-rose-400 hover:underline flex items-center gap-1"
                    >
                      <XCircle className="w-3 h-3" />
                      Cancel
                    </button>
                  </div>
                  <p className="text-[10px] font-mono text-slate-500">Job {jobStatus.job_id}</p>
                </div>
              )}
              {jobStatus?.status === "FAILED" && (
                <ErrorState
                  title="Video analysis failed"
                  message={jobStatus.error || "Video processing failed before results were produced."}
                  className="p-4"
                />
              )}
              {jobStatus?.status === "CANCELLED" && (
                <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-950/20 text-xs text-amber-200">
                  Job {jobStatus.job_id} was cancelled. Processing stopped before completion.
                </div>
              )}
            </div>
          )}

          {/* 3. Combined Analysis Trigger Button */}
          {activeTab === "integrated" && (
            <div className="space-y-2">
              {(!originCoords || !destCoords) && (
                <p className="text-[11px] text-amber-300">Route origin and destination are required for combined analysis.</p>
              )}
              {(!activeJobId || jobStatus?.status !== "COMPLETED") && (
                <p className="text-[11px] text-amber-300">
                  Combined analysis needs a completed video job. Route and video workflows can still run independently.
                </p>
              )}
              <button
                type="button"
                onClick={handleRunCombined}
                disabled={
                  combinedMutation.isPending ||
                  !originCoords ||
                  !destCoords ||
                  !activeJobId ||
                  jobStatus?.status !== "COMPLETED" ||
                  sameLocationSelected
                }
                className="w-full py-3 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 hover:opacity-90 disabled:opacity-40 text-white font-bold text-sm shadow-xl transition-all flex items-center justify-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                <span>Run Integrated Route + Video Analysis</span>
              </button>
              {combinedMutation.isError && (
                <ErrorState title="Combined analysis failed" error={combinedMutation.error} className="p-4" />
              )}
            </div>
          )}
        </div>

        {/* Right Map Panel */}
        <div className="lg:col-span-7 h-[560px] relative">
          <RouteMap
            origin={originCoords}
            destination={destCoords}
            selectedRoute={activeAlternative || routeResult?.selected_route}
            alternatives={routeResult?.alternatives}
            onSelectAlternative={(alt) => setActiveAlternative(alt)}
            roads={roads}
            intersections={intersections}
            zones={zones}
            onMapClick={handleMapClick}
            clickMode={mapClickMode}
            className="h-full shadow-2xl"
          />
        </div>
      </div>

      {/* Results Section */}
      <div className="space-y-6 pt-4">
        {/* Combined Synthesis Banner */}
        {activeTab === "integrated" && combinedResult && (
          <div
            className={`p-5 rounded-xl border ${
              combinedResult.is_associated
                ? "border-emerald-500/40 bg-emerald-950/20"
                : "border-amber-500/40 bg-amber-950/20"
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2 font-bold text-sm">
                  {combinedResult.is_associated ? (
                    <>
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                      <span className="text-emerald-300">Corridor Video Integration Verified</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="w-5 h-5 text-amber-400" />
                      <span className="text-amber-300">Corridor Disconnected From Video Recording</span>
                    </>
                  )}
                </div>
                <p className="text-xs text-slate-300">{combinedResult.association_reason}</p>
                {combinedResult.integrated_traffic_summary.traffic_note && (
                  <p className="text-xs font-mono text-slate-200 mt-2 bg-slate-900/60 p-2 rounded">
                    {combinedResult.integrated_traffic_summary.traffic_note}
                  </p>
                )}
                {!combinedResult.is_associated && combinedResult.integrated_traffic_summary.advice && (
                  <p className="text-xs text-slate-400 mt-2">
                    {combinedResult.integrated_traffic_summary.advice}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Route Analysis Results */}
        {(activeTab === "route" || activeTab === "integrated") && routeResult && (() => {
          const currentDisplayRoute = activeAlternative || routeResult.selected_route;
          return (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    <RouteIcon className="w-5 h-5 text-blue-400" />
                    <span>Route Intelligence & Corridor Assessment</span>
                  </h3>
                  <span className="text-xs text-slate-400">{routeResult.data_freshness_note}</span>
                </div>

                {/* Congestion Badge */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-400 font-medium">Corridor Status:</span>
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-bold ${getCongestionBadgeClass(
                      currentDisplayRoute.congestion_level
                    )}`}
                  >
                    {currentDisplayRoute.congestion_level}
                  </span>
                </div>
              </div>

              {/* Route Recommendation Banner */}
              {routeResult.recommendation_explanation && (
                <div className="p-4 rounded-xl border border-blue-500/30 bg-blue-950/30 flex items-start gap-3 shadow-lg">
                  <Sparkles className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-blue-400">
                        Evidence-Based Recommendation
                      </span>
                      {routeResult.recommended_route_summary && (
                        <span className="text-xs font-semibold text-white bg-blue-900/50 px-2 py-0.5 rounded border border-blue-700/50">
                          {routeResult.recommended_route_summary}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-200">
                      {routeResult.recommendation_explanation}
                    </p>
                    {routeResult.recommendation_basis && (
                      <span className="text-[11px] text-slate-400 font-mono block">
                        Evaluation basis: {routeResult.recommendation_basis}
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Corridor Incidents Alert Banner */}
              {Boolean(routeResult.corridor.active_incidents_count && routeResult.corridor.active_incidents_count > 0) && (
                <div className="p-4 rounded-xl border border-rose-500/30 bg-rose-950/20 flex items-start gap-3">
                  <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                  <div className="space-y-1 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-rose-300">
                        {routeResult.corridor.active_incidents_count} Live Incident(s) Detected Along Route Corridor
                      </span>
                      <span className="px-1.5 py-0.5 rounded bg-rose-900/60 text-rose-200 text-[10px] font-mono">
                        TomTom Traffic
                      </span>
                    </div>
                    {routeResult.corridor.incident_delay_seconds ? (
                      <span className="text-slate-300 block">
                        Cumulative traffic delay: +{Math.round(routeResult.corridor.incident_delay_seconds / 60)} min
                      </span>
                    ) : null}
                    {routeResult.corridor.incidents_summary && routeResult.corridor.incidents_summary.length > 0 && (
                      <ul className="list-disc list-inside text-slate-300 pt-1 space-y-0.5">
                        {routeResult.corridor.incidents_summary.map((summary, idx) => (
                          <li key={idx}>{summary}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              )}

              {/* Route KPI Metrics Strip */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60">
                  <span className="text-xs font-semibold text-slate-400 block">Distance</span>
                  <div className="text-2xl font-bold font-mono text-white mt-1">
                    {currentDisplayRoute.distance_km} <span className="text-sm font-normal text-slate-400">km</span>
                  </div>
                  <span className="text-[11px] text-slate-400">{currentDisplayRoute.distance_meters} m</span>
                </div>

                <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60">
                  <span className="text-xs font-semibold text-slate-400 block">Free-Flow Time</span>
                  <div className="text-2xl font-bold font-mono text-white mt-1">
                    {currentDisplayRoute.free_flow_duration_minutes} <span className="text-sm font-normal text-slate-400">min</span>
                  </div>
                  <span className="text-[11px] text-slate-400">Base road geometry</span>
                </div>

                <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60">
                  <span className="text-xs font-semibold text-slate-400 block">Traffic-Aware Time</span>
                  <div className="text-2xl font-bold font-mono text-white mt-1">
                    {currentDisplayRoute.traffic_duration_minutes !== null ? (
                      <>
                        {currentDisplayRoute.traffic_duration_minutes} <span className="text-sm font-normal text-slate-400">min</span>
                      </>
                    ) : (
                      <span className="text-slate-400 text-sm">No Telemetry</span>
                    )}
                  </div>
                  <span className="text-[11px] text-slate-400">
                    {currentDisplayRoute.delay_minutes
                      ? `+${currentDisplayRoute.delay_minutes} min delay`
                      : "No telemetry delay computed"}
                  </span>
                </div>

                <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60">
                  <span className="text-xs font-semibold text-slate-400 block">Corridor Samples</span>
                  <div className="text-2xl font-bold font-mono text-white mt-1">
                    {routeResult.corridor.telemetry_sample_count} <span className="text-sm font-normal text-slate-400">events</span>
                  </div>
                  <span className="text-[11px] text-emerald-400 font-mono">
                    {routeResult.corridor.telemetry_status === "AVAILABLE"
                      ? (routeResult.corridor.telemetry_source || "Live PostGIS stream")
                      : "Sensor unavailable"}
                  </span>
                </div>
              </div>

              {/* Alternatives Route Selector Strip */}
              {routeResult.alternatives.length > 1 && (
                <div className="space-y-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 block">
                    Available Route Options ({routeResult.alternatives.length})
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                    {routeResult.alternatives.map((alt, index) => {
                      const isSelected = (activeAlternative?.summary || routeResult.selected_route.summary) === alt.summary;
                      return (
                        <button
                          key={`alt-card-${index}`}
                          type="button"
                          onClick={() => setActiveAlternative(alt)}
                          className={`p-3 rounded-lg border text-left transition-all ${
                            isSelected
                              ? "border-blue-500 bg-blue-950/20 shadow-md shadow-blue-500/10"
                              : "border-slate-800 bg-slate-950/40 hover:border-slate-700"
                          }`}
                        >
                          <div className="flex items-center justify-between text-xs font-bold text-white">
                            <span className="truncate mr-2">{alt.summary || `Route Alternative ${index + 1}`}</span>
                            {alt.is_recommended ? (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold shrink-0">
                                Recommended
                              </span>
                            ) : alt.rank ? (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-medium shrink-0">
                                Rank {alt.rank}
                              </span>
                            ) : null}
                          </div>
                          <div className="flex items-center justify-between text-xs text-slate-300 mt-1">
                            <span>{alt.distance_km} km • {alt.traffic_duration_minutes ?? alt.free_flow_duration_minutes} min</span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${getCongestionBadgeClass(alt.congestion_level)}`}>
                              {alt.congestion_level}
                            </span>
                          </div>
                          {alt.recommendation_reason && (
                            <div className="text-[10px] text-slate-400 mt-1 truncate">
                              {alt.recommendation_reason}
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Corridor Infrastructure & AI Forecast Dual Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                {/* Corridor Assets Breakdown */}
                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-blue-400" />
                    <span>Monitored Road Corridors & Intersections</span>
                  </h4>

                  <div className="space-y-2">
                    {routeResult.corridor.matched_roads.length > 0 ? (
                      routeResult.corridor.matched_roads.map((road) => (
                        <div
                          key={road.road_id}
                          className="p-3 rounded-lg border border-slate-800/80 bg-slate-950/40 flex items-center justify-between text-xs"
                        >
                          <div>
                            <span className="font-semibold text-white">{road.road_name}</span>
                            <span className="block text-[10px] text-slate-400 font-mono">
                              {road.road_id} • {road.lanes} lanes
                            </span>
                          </div>
                          <span className="font-mono font-bold text-blue-400">{road.speed_limit} km/h</span>
                        </div>
                      ))
                    ) : (
                      <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/30 text-xs text-slate-400">
                        No registered RouteX road segments intersecting this route corridor.
                      </div>
                    )}

                    {routeResult.corridor.nearby_intersections.map((inter) => (
                      <div
                        key={inter.intersection_id}
                        className="p-2.5 rounded-lg border border-indigo-900/40 bg-indigo-950/20 flex items-center justify-between text-xs"
                      >
                        <span className="text-indigo-300 font-medium">{inter.name}</span>
                        <span className="font-mono text-[10px] text-slate-400">{inter.intersection_id}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* AI Prediction Model Output Card */}
                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                    <span>RouteX AI Model Forecast</span>
                  </h4>

                  <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-white">Production Predictor</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          routeResult.ai_prediction.status === "AVAILABLE"
                            ? "bg-purple-500/20 text-purple-300 border border-purple-500/30"
                            : "bg-slate-800 text-slate-400"
                        }`}
                      >
                        {routeResult.ai_prediction.status}
                      </span>
                    </div>

                    {routeResult.ai_prediction.status === "AVAILABLE" ? (
                      <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div className="bg-slate-900 p-2.5 rounded-lg">
                            <span className="text-slate-400 text-[10px] block">Predicted Congestion</span>
                            <span
                              className={`font-bold mt-0.5 inline-block px-1.5 py-0.5 rounded text-xs ${getCongestionBadgeClass(
                                routeResult.ai_prediction.predicted_congestion || "LOW"
                              )}`}
                            >
                              {routeResult.ai_prediction.predicted_congestion}
                            </span>
                          </div>
                          <div className="bg-slate-900 p-2.5 rounded-lg">
                            <span className="text-slate-400 text-[10px] block">Prediction Confidence</span>
                            <span className="font-mono font-bold text-white text-sm">
                              {routeResult.ai_prediction.prediction_confidence != null
                                ? `${(routeResult.ai_prediction.prediction_confidence * 100).toFixed(1)}%`
                                : "Unavailable"}
                            </span>
                          </div>
                        </div>

                        <p className="text-xs text-slate-300 font-mono bg-slate-900/80 p-2.5 rounded-lg">
                          {routeResult.ai_prediction.explanation}
                        </p>
                      </div>
                    ) : (
                      <div className="p-3 rounded-lg bg-slate-900/50 text-xs text-slate-400 space-y-1">
                        <span className="font-semibold text-slate-300 block">Insufficient Corridor Data</span>
                        <p>{routeResult.ai_prediction.explanation}</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })()}

        {/* Video Analysis Results */}
        {(activeTab === "video" || activeTab === "integrated") && videoResult && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Video className="w-5 h-5 text-indigo-400" />
                  <span>Computer Vision & Traffic Telemetry Output</span>
                </h3>
                <span className="text-xs text-slate-400">
                  Source: {videoResult.filename} • {videoResult.processed_frames ?? videoResult.total_frames} processed / {videoResult.total_frames} frames ({videoResult.duration_seconds}s)
                  {videoResult.intersection_id ? ` • Camera ${videoResult.intersection_id}` : " • No location metadata"}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Congestion:</span>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-bold ${getCongestionBadgeClass(
                    videoResult.congestion_level
                  )}`}
                >
                  {videoResult.congestion_level}
                </span>
              </div>
            </div>

            {/* Video KPI Strip */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60">
                <span className="text-xs font-semibold text-slate-400 block">Total Vehicles</span>
                <div className="text-2xl font-bold font-mono text-white mt-1">
                  {videoResult.total_vehicles_detected}
                </div>
                <span className="text-[11px] text-slate-400">Unique YOLO tracks</span>
              </div>

              <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60">
                <span className="text-xs font-semibold text-slate-400 block">Estimated Speed</span>
                <div className="text-2xl font-bold font-mono text-white mt-1">
                  {videoResult.average_speed} <span className="text-sm font-normal text-slate-400">km/h</span>
                </div>
                <span className="text-[11px] text-slate-400">Uncalibrated pixel estimate, not survey-grade</span>
              </div>

              <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60">
                <span className="text-xs font-semibold text-slate-400 block">Density Ratio</span>
                <div className="text-2xl font-bold font-mono text-white mt-1">
                  {videoResult.density}
                </div>
                <span className="text-[11px] text-slate-400">Vehicles per lane capacity</span>
              </div>

              <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60">
                <span className="text-xs font-semibold text-slate-400 block">AI Forecast</span>
                <div className="text-2xl font-bold font-mono text-purple-400 mt-1">
                  {videoResult.ai_prediction?.predicted_vehicle_count != null
                    ? videoResult.ai_prediction.predicted_vehicle_count
                    : "Unavailable"}
                </div>
                <span className="text-[11px] text-slate-400">
                  {videoResult.ai_prediction?.prediction_confidence != null
                    ? `Model confidence ${((videoResult.ai_prediction.prediction_confidence) * 100).toFixed(0)}%`
                    : videoResult.ai_prediction?.reason || "No forecast when the model cannot run"}
                </span>
              </div>
            </div>
            {(videoResult.line_crossing_total ?? 0) > 0 && (
              <p className="text-xs text-slate-400">
                Virtual line crossings: {videoResult.line_crossing_total}
                {videoResult.line_crossing_counts
                  ? ` (${Object.entries(videoResult.line_crossing_counts)
                      .map(([type, count]) => `${type}: ${count}`)
                      .join(", ")})`
                  : ""}
              </p>
            )}

            {/* Vehicle Classes & Time-Series Dual Chart Grid */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
              {/* Category Breakdown Chart */}
              <div className="md:col-span-5 p-4 rounded-xl border border-slate-800 bg-slate-950/60 space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Detected Vehicle Categories
                </h4>
                <div className="h-48 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={Object.entries(videoResult.vehicle_types).map(([type, count]) => ({
                        type: type.toUpperCase(),
                        count,
                      }))}
                    >
                      <XAxis dataKey="type" stroke="#64748b" fontSize={11} />
                      <YAxis stroke="#64748b" fontSize={11} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#0f172a",
                          borderColor: "#1e293b",
                          borderRadius: "8px",
                          fontSize: "12px",
                        }}
                      />
                      <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Time-Series Activity Trend Chart */}
              <div className="md:col-span-7 p-4 rounded-xl border border-slate-800 bg-slate-950/60 space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Video Recording Timeline Volume & Speed
                </h4>
                <div className="h-48 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={videoResult.frame_samples}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="second" unit="s" stroke="#64748b" fontSize={11} />
                      <YAxis stroke="#64748b" fontSize={11} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#0f172a",
                          borderColor: "#1e293b",
                          borderRadius: "8px",
                          fontSize: "12px",
                        }}
                      />
                      <Line
                        type="monotone"
                        dataKey="vehicles_in_frame"
                        name="Active Vehicles"
                        stroke="#38bdf8"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                      />
                      <Line
                        type="monotone"
                        dataKey="speed"
                        name="Speed (km/h)"
                        stroke="#a855f7"
                        strokeWidth={2}
                        dot={{ r: 2 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Visual Verification & Annotated Video Playback */}
            {videoResult.annotated_video_url ? (
              <div className="p-4 rounded-xl border border-indigo-500/30 bg-slate-950/60 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-2">
                    <Video className="w-4 h-4 text-indigo-400" />
                    <span>Processed & Annotated Traffic Video (Full Tracking Playback)</span>
                  </span>
                  <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-500/30">
                    AI Annotations Active
                  </span>
                </div>
                <div className="rounded-lg overflow-hidden border border-slate-800 bg-black flex items-center justify-center">
                  <video
                    controls
                    playsInline
                    src={videoResult.annotated_video_url}
                    className="w-full max-h-96 object-contain"
                  >
                    Your browser does not support HTML5 video playback.
                  </video>
                </div>
              </div>
            ) : videoResult.preview_image_base64 ? (
              <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/60 space-y-2">
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400 block">
                  Computer Vision Detection Sample (Annotated Frame)
                </span>
                <div className="rounded-lg overflow-hidden border border-slate-800 max-h-96 flex items-center justify-center bg-black">
                  <img
                    src={videoResult.preview_image_base64}
                    alt="YOLO Detection Preview"
                    className="object-contain max-h-96 w-full"
                  />
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
};
