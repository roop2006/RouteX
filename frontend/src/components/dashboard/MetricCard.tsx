import React from "react";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
  trend?: {
    value: string;
    isPositive?: boolean;
    label?: string;
  };
  accentColor?: "blue" | "emerald" | "amber" | "rose" | "purple" | "cyan";
  className?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  icon,
  badge,
  trend,
  accentColor = "blue",
  className = "",
}) => {
  const accentClasses = {
    blue: "from-blue-600/10 to-transparent border-blue-500/20 text-blue-400",
    emerald: "from-emerald-600/10 to-transparent border-emerald-500/20 text-emerald-400",
    amber: "from-amber-600/10 to-transparent border-amber-500/20 text-amber-400",
    rose: "from-rose-600/10 to-transparent border-rose-500/20 text-rose-400",
    purple: "from-purple-600/10 to-transparent border-purple-500/20 text-purple-400",
    cyan: "from-cyan-600/10 to-transparent border-cyan-500/20 text-cyan-400",
  }[accentColor];

  return (
    <div
      className={`relative overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg backdrop-blur-sm transition-all hover:border-slate-700/80 ${className}`}
    >
      <div className={`absolute top-0 right-0 left-0 h-1 bg-gradient-to-r ${accentClasses}`} />

      <div className="flex items-start justify-between">
        <div>
          <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
            {title}
          </span>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-bold tracking-tight text-white font-mono">
              {value}
            </span>
            {badge}
          </div>
        </div>

        {icon && (
          <div className="rounded-lg bg-slate-800/80 p-2.5 text-slate-300 ring-1 ring-slate-700/50">
            {icon}
          </div>
        )}
      </div>

      {(subtitle || trend) && (
        <div className="mt-3 flex items-center justify-between text-xs text-slate-400 border-t border-slate-800/60 pt-2.5">
          {subtitle && <span>{subtitle}</span>}
          {trend && (
            <span
              className={`font-medium ${
                trend.isPositive ? "text-emerald-400" : "text-rose-400"
              }`}
            >
              {trend.value} {trend.label}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
