"use client";

import React, { useEffect } from "react";
import { AlertCircle, RotateCcw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Global boundary caught runtime error:", error);
  }, [error]);

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-red-950/20 via-zinc-950 to-zinc-950 px-4">
      {/* Background ambient light */}
      <div className="absolute top-1/4 left-1/4 h-72 w-72 rounded-full bg-red-600/5 blur-[120px] pointer-events-none" />

      <div className="w-full max-w-md z-10 text-center space-y-6">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-full border border-red-500/20 bg-red-500/5 text-red-500 shadow-lg shadow-red-500/10 mb-4 animate-bounce">
          <AlertCircle size={28} />
        </div>
        
        <h1 className="text-3xl font-extrabold tracking-tight text-white">
          Workspace Error
        </h1>
        
        <p className="text-zinc-400 text-xs max-w-sm mx-auto leading-relaxed">
          Something went wrong in the workspace execution environment. The error has been captured.
        </p>

        <div className="glass-card rounded-xl p-4 shadow-2xl border border-red-500/10">
          <p className="font-mono text-[10px] text-red-400 text-left bg-zinc-950 p-3 rounded overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-32">
            {error.message || "An unhandled UI shell error has occurred."}
          </p>
        </div>

        <button
          onClick={() => reset()}
          className="inline-flex items-center justify-center gap-2 rounded-md bg-gradient-to-r from-red-600 to-amber-600 px-6 py-2.5 text-xs font-semibold text-white hover:from-red-500 hover:to-amber-500 transition-all cursor-pointer shadow-lg shadow-red-500/10"
        >
          <RotateCcw size={12} /> Reload Workspace
        </button>
      </div>
    </div>
  );
}
