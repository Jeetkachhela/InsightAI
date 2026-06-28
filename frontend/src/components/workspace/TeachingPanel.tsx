import React from "react";
import { Sparkles, CheckCircle2, AlertTriangle, Lightbulb, GitFork } from "lucide-react";

interface TeachingPanelProps {
  confidence: number | null;
  validation: any;
  impact: any;
  explanation: string;
}

export default function TeachingPanel({
  confidence,
  validation,
  impact,
  explanation,
}: TeachingPanelProps) {
  return (
    <div className="space-y-6">
      {/* 1. Confidence & Validation Metrics */}
      <div className="grid grid-cols-2 gap-4">
        {/* Confidence Card */}
        <div className="p-4 rounded-lg border border-zinc-900 bg-zinc-950/40">
          <div className="flex items-center gap-1.5 text-xs text-zinc-400 mb-1">
            <Sparkles size={13} className="text-violet-400" />
            <span>AI Confidence</span>
          </div>
          <p className="text-2xl font-bold text-white">
            {confidence !== null ? `${Math.round(confidence * 100)}%` : "N/A"}
          </p>
        </div>

        {/* Validation Card */}
        <div className="p-4 rounded-lg border border-zinc-900 bg-zinc-950/40">
          <div className="flex items-center gap-1.5 text-xs text-zinc-400 mb-1">
            <CheckCircle2 size={13} className="text-emerald-400" />
            <span>Security Status</span>
          </div>
          <p className="text-sm font-semibold text-emerald-400 flex items-center gap-1">
            {validation && validation.is_safe ? "Verified Safe" : "Pending Check"}
          </p>
        </div>
      </div>

      {/* 2. Validation Suggestions */}
      {validation && (
        <div className={`p-4 rounded-lg border text-xs ${
          validation.is_safe 
            ? "bg-emerald-950/10 border-emerald-900/30 text-emerald-300"
            : "bg-red-950/10 border-red-900/30 text-red-300"
        }`}>
          <h4 className="font-semibold flex items-center gap-1.5 mb-1.5">
            {validation.is_safe ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />}
            SQL Firewall Evaluation
          </h4>
          <p>{validation.details || validation.message || "Query structure conforms to SELECT-only policies."}</p>
        </div>
      )}

      {/* 3. Query Impact Analysis */}
      {impact && (
        <div className="p-4 rounded-lg border border-zinc-900 bg-zinc-950/40 space-y-3">
          <h4 className="text-xs font-semibold text-white flex items-center gap-1.5">
            <GitFork size={13} className="text-indigo-400" />
            Performance & Load Projection
          </h4>
          <div className="grid grid-cols-2 gap-3 text-[11px]">
            <div className="bg-zinc-950 p-2 rounded">
              <span className="text-zinc-500 block">Estimated Rows Scan</span>
              <span className="font-semibold text-zinc-300">{impact.estimated_rows || "Low (Indexed)"}</span>
            </div>
            <div className="bg-zinc-950 p-2 rounded">
              <span className="text-zinc-500 block">Query Complexity</span>
              <span className="font-semibold text-zinc-300">{impact.complexity || "Simple SELECT"}</span>
            </div>
          </div>
        </div>
      )}

      {/* 4. Natural Language Explanation */}
      {explanation && (
        <div className="p-4 rounded-lg border border-zinc-900 bg-zinc-950/40 space-y-2">
          <h4 className="text-xs font-semibold text-white flex items-center gap-1.5">
            <Lightbulb size={13} className="text-yellow-400" />
            Agent Schema Explanation
          </h4>
          <div className="text-xs text-zinc-400 leading-relaxed whitespace-pre-wrap">
            {explanation}
          </div>
        </div>
      )}
    </div>
  );
}
