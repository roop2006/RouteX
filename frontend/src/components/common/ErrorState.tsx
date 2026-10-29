import React from "react";
import { AlertCircle, RotateCcw } from "lucide-react";
import { getApiErrorMessage } from "../../api/client";

interface ErrorStateProps {
  title?: string;
  error?: unknown;
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = "Failed to load data",
  error,
  message,
  onRetry,
  className = "",
}) => {
  const displayMessage = message || (error ? getApiErrorMessage(error) : "An unexpected error occurred.");

  return (
    <div
      className={`rounded-xl border border-rose-500/30 bg-rose-950/20 p-6 text-rose-200 flex flex-col items-center text-center space-y-3 ${className}`}
    >
      <div className="w-12 h-12 rounded-full bg-rose-500/10 flex items-center justify-center text-rose-400 ring-1 ring-rose-500/30">
        <AlertCircle className="w-6 h-6" />
      </div>

      <div className="space-y-1">
        <h3 className="text-base font-semibold text-rose-100">{title}</h3>
        <p className="text-sm text-rose-300/90 max-w-md">{displayMessage}</p>
      </div>

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-2 px-4 py-2 mt-2 text-sm font-medium text-white bg-rose-600/80 hover:bg-rose-600 rounded-lg transition-colors border border-rose-500/50 shadow-sm shadow-rose-900/30 cursor-pointer"
        >
          <RotateCcw className="w-4 h-4" />
          Retry Request
        </button>
      )}
    </div>
  );
};
