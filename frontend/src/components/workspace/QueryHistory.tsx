import React from "react";
import { History, Play, AlertCircle } from "lucide-react";

interface QueryLog {
  id: string;
  query_text: string;
  status: string;
  execution_time_ms: number;
  created_at: string;
}

interface QueryHistoryProps {
  queryHistory: QueryLog[];
  onSelectQuery: (sqlText: string) => void;
}

export default function QueryHistory({
  queryHistory,
  onSelectQuery,
}: QueryHistoryProps) {
  if (queryHistory.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-zinc-500 text-center px-4">
        <History size={24} className="mb-2 text-zinc-600" />
        <p className="text-xs">No query history logs found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {queryHistory.map((log) => (
        <div
          key={log.id}
          className="p-3 border border-zinc-900 rounded bg-zinc-950/40 text-xs hover:border-zinc-800 transition-all flex flex-col gap-2"
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-zinc-500 font-mono">
              {new Date(log.created_at).toLocaleTimeString()}
            </span>
            <span
              className={`flex items-center gap-1 text-[9px] px-1.5 py-0.5 rounded font-medium ${
                log.status === "success"
                  ? "bg-emerald-950/30 text-emerald-400 border border-emerald-900/30"
                  : "bg-red-950/30 text-red-400 border border-red-900/30"
              }`}
            >
              {log.status === "success" ? "Success" : "Error"}
            </span>
          </div>

          <pre className="font-mono text-[10px] bg-zinc-950 p-2 rounded text-zinc-300 overflow-x-auto whitespace-pre-wrap max-h-24">
            {log.query_text}
          </pre>

          <div className="flex items-center justify-between">
            <span className="text-[10px] text-zinc-500">
              {log.execution_time_ms} ms latency
            </span>
            <button
              onClick={() => onSelectQuery(log.query_text)}
              className="text-[10px] text-violet-400 hover:text-violet-300 font-semibold flex items-center gap-1 cursor-pointer"
            >
              <Play size={10} /> Load Query
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
