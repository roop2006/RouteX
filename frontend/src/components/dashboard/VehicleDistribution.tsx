import React from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from "recharts";
import { Car, Truck, Bus, Bike } from "lucide-react";

interface VehicleDistributionProps {
  vehicleTypes?: Record<string, number> | null;
  title?: string;
  className?: string;
}

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#06b6d4"];

export const VehicleDistribution: React.FC<VehicleDistributionProps> = ({
  vehicleTypes,
  title = "Vehicle Category Distribution",
  className = "",
}) => {
  const entries = Object.entries(vehicleTypes || {}).filter(([, count]) => count >= 0);
  const total = entries.reduce((acc, [, count]) => acc + count, 0);

  const data = entries.map(([category, count], idx) => ({
    name: category.charAt(0).toUpperCase() + category.slice(1),
    count,
    percentage: total > 0 ? Math.round((count / total) * 100) : 0,
    color: COLORS[idx % COLORS.length],
  }));

  const getCategoryIcon = (name: string) => {
    const lower = name.toLowerCase();
    if (lower.includes("car")) return <Car className="w-4 h-4 text-blue-400" />;
    if (lower.includes("truck")) return <Truck className="w-4 h-4 text-amber-400" />;
    if (lower.includes("bus")) return <Bus className="w-4 h-4 text-emerald-400" />;
    if (lower.includes("bike") || lower.includes("motorcycle"))
      return <Bike className="w-4 h-4 text-purple-400" />;
    return <Car className="w-4 h-4 text-slate-400" />;
  };

  return (
    <div className={`rounded-xl border border-slate-800 bg-slate-900/60 p-5 backdrop-blur-sm ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-white">{title}</h3>
          <p className="text-xs text-slate-400">
            Detected breakdown ({total} total categorized)
          </p>
        </div>
      </div>

      {data.length === 0 ? (
        <div className="py-8 text-center text-sm text-slate-400">
          No vehicle category distribution detected.
        </div>
      ) : (
        <div className="space-y-4">
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} layout="vertical" margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
                <XAxis type="number" stroke="#64748b" fontSize={11} tickLine={false} axisLine={{ stroke: "#334155" }} />
                <YAxis
                  dataKey="name"
                  type="category"
                  stroke="#94a3b8"
                  fontSize={12}
                  tickLine={false}
                  axisLine={{ stroke: "#334155" }}
                  width={80}
                />
                <Tooltip
                  formatter={(val: unknown) => [`${val ?? 0} vehicles`, "Count"]}
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    borderColor: "#334155",
                    borderRadius: "0.5rem",
                    color: "#f8fafc",
                    fontSize: "12px",
                  }}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {data.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-800/80">
            {data.map((item) => (
              <div
                key={item.name}
                className="p-2.5 rounded-lg bg-slate-800/40 border border-slate-800/80 flex items-center justify-between"
              >
                <div className="flex items-center gap-2">
                  {getCategoryIcon(item.name)}
                  <span className="text-xs font-medium text-slate-300">{item.name}</span>
                </div>
                <div className="text-right">
                  <span className="text-xs font-bold text-white font-mono">{item.count}</span>
                  <span className="block text-[10px] text-slate-400 font-mono">{item.percentage}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
