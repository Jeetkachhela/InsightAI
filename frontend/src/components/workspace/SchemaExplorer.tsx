import React from "react";
import { Table, Loader2, Database } from "lucide-react";

interface SchemaField {
  table_name: string;
  column_name: string;
  data_type: string;
  is_nullable: boolean;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  description?: string;
}

interface SchemaExplorerProps {
  metadata: SchemaField[];
  loading: boolean;
  expandedTables: Record<string, boolean>;
  onToggleTable: (tableName: string) => void;
}

export default function SchemaExplorer({
  metadata,
  loading,
  expandedTables,
  onToggleTable,
}: SchemaExplorerProps) {
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-48 gap-2 text-zinc-500">
        <Loader2 size={24} className="animate-spin text-violet-400" />
        <span className="text-xs">Loading schema metadata...</span>
      </div>
    );
  }

  if (metadata.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-zinc-500 text-center px-4">
        <Database size={24} className="mb-2 text-zinc-600" />
        <p className="text-xs">No tables discovered yet.</p>
      </div>
    );
  }

  // Group columns by table
  const tablesMap: Record<string, SchemaField[]> = {};
  metadata.forEach((item) => {
    tablesMap[item.table_name] = tablesMap[item.table_name] || [];
    tablesMap[item.table_name].push(item);
  });

  return (
    <div className="space-y-3">
      {Object.entries(tablesMap).map(([tableName, columns]) => {
        const isExpanded = expandedTables[tableName];
        return (
          <div key={tableName} className="border border-zinc-900 rounded bg-zinc-950/40 overflow-hidden">
            <button
              onClick={() => onToggleTable(tableName)}
              className="w-full flex items-center justify-between px-3 py-2.5 bg-zinc-950/80 hover:bg-zinc-900/60 text-left text-xs font-semibold text-zinc-300 transition-colors cursor-pointer"
            >
              <span className="flex items-center gap-2">
                <Table size={12} className="text-violet-400" />
                {tableName}
              </span>
              <span className="text-[10px] text-zinc-500 bg-zinc-900 px-1.5 py-0.5 rounded">
                {columns.length} cols
              </span>
            </button>

            {isExpanded && (
              <div className="border-t border-zinc-900 p-2 space-y-1.5 bg-zinc-950/20">
                {columns.map((col) => (
                  <div
                    key={col.column_name}
                    className="flex flex-col p-1.5 rounded hover:bg-zinc-900/40 text-[11px] transition-colors"
                  >
                    <div className="flex items-center justify-between text-zinc-300">
                      <span className="font-mono font-medium">
                        {col.column_name}
                        {col.is_primary_key && <span className="text-[9px] text-emerald-400 ml-1">PK</span>}
                        {col.is_foreign_key && <span className="text-[9px] text-indigo-400 ml-1">FK</span>}
                      </span>
                      <span className="text-zinc-500 font-mono font-light text-[10px]">{col.data_type}</span>
                    </div>
                    {col.description && (
                      <p className="text-[10px] text-zinc-500 mt-0.5 italic">{col.description}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
