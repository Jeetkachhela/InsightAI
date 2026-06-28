"use client";

import React from "react";
import { Loader2 } from "lucide-react";

export default function Loading() {
  return (
    <main className="relative flex min-h-screen items-center justify-center bg-zinc-950 px-4">
      {/* Background ambient light */}
      <div className="absolute top-1/3 left-1/3 h-96 w-96 rounded-full bg-violet-600/5 blur-[150px] pointer-events-none" />

      <div className="flex flex-col items-center justify-center gap-4 text-center z-10">
        <Loader2 size={36} className="animate-spin text-violet-500" />
        <h2 className="text-sm font-semibold text-zinc-300 tracking-wide">
          InsightForge AI
        </h2>
        <p className="text-zinc-500 text-[11px] max-w-[200px] leading-relaxed">
          Retrieving workspace models...
        </p>
      </div>
    </main>
  );
}
