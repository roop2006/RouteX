import React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { formatTimeOnly } from "../../utils/formatters";

export interface TrafficChartDataPoint {
  timestamp: string;
  total_vehicles: number;
  average_speed?: number;
  density?: number;
  congestion_level?: string;
}

interface TrafficChartProps {
  data: TrafficChartDataPoint[];
  title?: string;
  subtitle?: string;
  showSpeed?: boolean;
  className?: string;
}

export const TrafficChart: React.FC<TrafficChartProps> = ({
  data,
  title = "Traffic Volume & Speed Trends",
  subtitle = "Observed traffic flow over chronological intervals",
  showSpeed = true,
  className = "",
}) => {
  if (!data || data.length === 0) {
    return (
      <div className={`rounded-xl border border-slate-800 bg-slate-900/60 p-6 text-center text-slate-400 ${className}`}>
        <p className="text-sm font-medium">No historical traffic series data available</p>
      </div>
    );
  }

  // Format data for display (chronological order)
  const chartData = [...data]
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .map((item) => ({
      ...item,
      timeLabel: formatTimeOnly(item.timestamp),
    }));

  return (
    <div className={`rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm ${className}`}>
      <div className="mb-4">
        <h3 className="text-base font-semibold text-white">{title}</h3>
        {subtitle && <p className="text-xs text-slate-400">{subtitle}</p>}
      </div>

      <div className="h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="vehicleGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="speedGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="timeLabel"
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "#334155" }}
            />
            <YAxis
              yAxisId="left"
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: "#334155" }}
            />
            {showSpeed && (
              <YAxis
                yAxisId="right"
                orientation="right"
                stroke="#64748b"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: "#334155" }}
              />
            )}

            <Tooltip
              contentStyle={{
                backgroundColor: "#0f172a",
                borderColor: "#334155",
                borderRadius: "0.5rem",
                color: "#f8fafc",
                fontSize: "12px",
                boxShadow: "0 10px 15px -3px rgba(0,0,0,0.5)",
              }}
              labelStyle={{ color: "#94a3b8", fontWeight: 600, marginBottom: "4px" }}
            />
            <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }} />

            <Area
              yAxisId="left"
              type="monotone"
              dataKey="total_vehicles"
              name="Vehicles"
              stroke="#3b82f6"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#vehicleGradient)"
            />
            {showSpeed && (
              <Area
                yAxisId="right"
                type="monotone"
                dataKey="average_speed"
                name="Avg Speed (km/h)"
                stroke="#10b981"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#speedGradient)"
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
