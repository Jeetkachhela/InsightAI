import React from "react";
import { GitFork, Loader2 } from "lucide-react";

interface Relationship {
  source_table: string;
  source_column: string;
  target_table: string;
  target_column: string;
}

interface RelationshipExplorerProps {
  relationships: Relationship[];
  loading: boolean;
}

export default function RelationshipExplorer({
  relationships,
  loading,
}: RelationshipExplorerProps) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-48 gap-2 text-zinc-500">
        <Loader2 size={24} className="animate-spin text-violet-400" />
        <span className="text-xs">Loading relationships...</span>
      </div>
    );
  }

  if (relationships.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-zinc-500 text-center px-4">
        <GitFork size={24} className="mb-2 text-zinc-600" />
        <p className="text-xs">No foreign key relationships detected.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {relationships.map((rel, idx) => (
        <div
          key={idx}
          className="p-3 border border-zinc-900 rounded bg-zinc-950/40 text-xs hover:border-zinc-800 transition-all"
        >
          <div className="flex items-center justify-between text-zinc-400 font-medium mb-1">
            <span>Foreign Key Link</span>
            <span className="text-[10px] text-violet-400 bg-violet-950/30 px-1.5 py-0.5 rounded font-mono">
              FK
            </span>
          </div>
          <div className="flex items-center gap-2 text-zinc-200">
            <div className="flex-1 min-w-0">
              <p className="font-semibold truncate">{rel.source_table}</p>
              <p className="font-mono text-[10px] text-zinc-500 truncate">.{rel.source_column}</p>
            </div>
            <div className="text-zinc-500 font-bold">➔</div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold truncate">{rel.target_table}</p>
              <p className="font-mono text-[10px] text-zinc-500 truncate">.{rel.target_column}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
