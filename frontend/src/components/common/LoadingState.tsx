import React from "react";
import { Loader2 } from "lucide-react";

interface LoadingStateProps {
  message?: string;
  className?: string;
  skeletonLines?: number;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = "Loading data...",
  className = "",
  skeletonLines = 0,
}) => {
  if (skeletonLines > 0) {
    return (
      <div className={`space-y-3 p-4 animate-pulse ${className}`}>
        {Array.from({ length: skeletonLines }).map((_, idx) => (
          <div
            key={idx}
            className="h-6 bg-slate-800/80 rounded border border-slate-700/30"
            style={{ width: `${Math.max(40, 100 - idx * 15)}%` }}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className={`flex flex-col items-center justify-center p-8 text-slate-400 space-y-3 ${className}`}
    >
      <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      <p className="text-sm font-medium">{message}</p>
    </div>
  );
};
