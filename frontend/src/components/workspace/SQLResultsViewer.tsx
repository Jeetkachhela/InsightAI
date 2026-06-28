import React from "react";
import { Table, BarChart2, AlertTriangle, AlertCircle } from "lucide-react";

interface SQLResultsViewerProps {
  execResult: {
    columns: string[];
    rows: any[][];
    execution_time_ms: number;
    row_count: number;
    truncated?: boolean;
  } | null;
  execError: string;
  activeTabBottom: "results" | "chart" | "actions";
  chartType: "bar" | "line" | "pie";
  xAxisCol: string;
  yAxisCol: string;
  onChartTypeChange: (type: "bar" | "line" | "pie") => void;
  onXAxisChange: (col: string) => void;
  onYAxisChange: (col: string) => void;
}

export default function SQLResultsViewer({
  execResult,
  execError,
  activeTabBottom,
  chartType,
  xAxisCol,
  yAxisCol,
  onChartTypeChange,
  onXAxisChange,
  onYAxisChange,
}: SQLResultsViewerProps) {
  if (execError) {
    return (
      <div className="flex flex-col items-center justify-center p-8 border border-red-500/20 bg-red-500/5 rounded-lg text-red-400 gap-2">
        <AlertCircle size={28} />
        <h4 className="font-semibold text-sm">Execution Error</h4>
        <p className="text-xs text-center max-w-md font-mono bg-zinc-950 p-3 rounded border border-red-950/30">
          {execError}
        </p>
      </div>
    );
  }

  if (!execResult) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-zinc-500 text-center">
        <Table size={24} className="mb-2 text-zinc-600" />
        <p className="text-xs">Run a SELECT query to view results here.</p>
      </div>
    );
  }

  const { columns, rows, execution_time_ms, row_count, truncated } = execResult;

  if (activeTabBottom === "results") {
    return (
      <div className="flex flex-col h-full gap-3">
        {/* Truncation warning indicator (SEC-013) */}
        {truncated && (
          <div className="flex items-center gap-2 p-2.5 rounded bg-amber-500/10 border border-amber-500/20 text-xs text-amber-400">
            <AlertTriangle size={14} className="flex-shrink-0" />
            <span>
              <strong>Performance Protection Rule Active:</strong> Query outputs exceeded the limit and have been truncated to the first 1,000 records.
            </span>
          </div>
        )}

        <div className="flex items-center justify-between text-xs text-zinc-500 bg-zinc-950 p-2 rounded">
          <span>Row count: <strong>{row_count}</strong></span>
          <span>Latency: <strong>{execution_time_ms} ms</strong></span>
        </div>

        <div className="flex-1 overflow-auto border border-zinc-900 rounded bg-zinc-950/20">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-zinc-950 border-b border-zinc-900 sticky top-0">
                {columns.map((col) => (
                  <th key={col} className="px-4 py-3 font-semibold text-zinc-300 font-mono">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rIdx) => (
                <tr key={rIdx} className="border-b border-zinc-900/60 hover:bg-zinc-900/25 transition-colors">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="px-4 py-2.5 text-zinc-400 font-light truncate max-w-[200px]" title={String(cell)}>
                      {cell === null ? <span className="text-zinc-600 italic">null</span> : String(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (activeTabBottom === "chart") {
    // Dynamic SVG charting implementation
    const xIdx = columns.indexOf(xAxisCol);
    const yIdx = columns.indexOf(yAxisCol);

    const hasValidChartData = xIdx !== -1 && yIdx !== -1 && rows.length > 0;

    if (!hasValidChartData) {
      return (
        <div className="flex flex-col items-center justify-center h-48 text-zinc-500 text-center">
          <BarChart2 size={24} className="mb-2 text-zinc-600" />
          <p className="text-xs">Configure X and Y axis columns to render visualization.</p>
        </div>
      );
    }

    // Limit charts to 25 items for visual sanity
    const chartRows = rows.slice(0, 25);
    const yValues = chartRows.map(r => {
      const val = parseFloat(r[yIdx]);
      return isNaN(val) ? 0 : val;
    });

    const maxVal = Math.max(...yValues, 1);

    return (
      <div className="flex flex-col h-full gap-4">
        {/* Controls */}
        <div className="flex flex-wrap gap-4 items-center bg-zinc-950/60 p-3 rounded-lg border border-zinc-900 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-zinc-500">Chart:</span>
            <select
              value={chartType}
              onChange={(e) => onChartTypeChange(e.target.value as any)}
              className="bg-zinc-900 border border-zinc-800 rounded px-2.5 py-1 text-white outline-none cursor-pointer"
            >
              <option value="bar">Bar Chart</option>
              <option value="line">Line Chart</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-zinc-500">X-Axis (Label):</span>
            <select
              value={xAxisCol}
              onChange={(e) => onXAxisChange(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded px-2.5 py-1 text-white outline-none cursor-pointer"
            >
              {columns.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-zinc-500">Y-Axis (Value):</span>
            <select
              value={yAxisCol}
              onChange={(e) => onYAxisChange(e.target.value)}
              className="bg-zinc-900 border border-zinc-800 rounded px-2.5 py-1 text-white outline-none cursor-pointer"
            >
              {columns.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        {/* SVG Drawing Canvas */}
        <div className="flex-1 min-h-[250px] bg-zinc-950/20 border border-zinc-900 rounded p-6 flex items-center justify-center">
          <svg className="w-full h-full max-h-[300px]" viewBox="0 0 500 200" preserveAspectRatio="none">
            {chartType === "bar" ? (
              // Bar chart renderer
              chartRows.map((row, idx) => {
                const width = 350 / chartRows.length;
                const gap = 100 / chartRows.length;
                const x = 50 + idx * (width + gap);
                const val = parseFloat(row[yIdx]);
                const numericVal = isNaN(val) ? 0 : val;
                const height = (numericVal / maxVal) * 150;
                const y = 170 - height;
                
                return (
                  <g key={idx} className="group">
                    <rect
                      x={x}
                      y={y}
                      width={width}
                      height={height}
                      className="fill-violet-600/70 stroke-violet-500 hover:fill-violet-500 transition-colors"
                      rx="2"
                    />
                    <text
                      x={x + width / 2}
                      y={185}
                      textAnchor="middle"
                      className="fill-zinc-500 font-mono text-[6px] pointer-events-none"
                    >
                      {String(row[xIdx]).substring(0, 8)}
                    </text>
                    <title>{`${row[xIdx]}: ${numericVal}`}</title>
                  </g>
                );
              })
            ) : (
              // Line chart renderer
              <g>
                {/* Draw line path */}
                <path
                  d={chartRows.reduce((acc, row, idx) => {
                    const step = 400 / (chartRows.length - 1 || 1);
                    const x = 50 + idx * step;
                    const val = parseFloat(row[yIdx]);
                    const numericVal = isNaN(val) ? 0 : val;
                    const height = (numericVal / maxVal) * 150;
                    const y = 170 - height;
                    return acc + `${idx === 0 ? "M" : "L"} ${x} ${y} `;
                  }, "")}
                  fill="none"
                  stroke="#8b5cf6"
                  strokeWidth="2"
                />
                {/* Draw dots */}
                {chartRows.map((row, idx) => {
                  const step = 400 / (chartRows.length - 1 || 1);
                  const x = 50 + idx * step;
                  const val = parseFloat(row[yIdx]);
                  const numericVal = isNaN(val) ? 0 : val;
                  const height = (numericVal / maxVal) * 150;
                  const y = 170 - height;
                  
                  return (
                    <g key={idx} className="group">
                      <circle
                        cx={x}
                        cy={y}
                        r="3.5"
                        className="fill-zinc-950 stroke-violet-400 stroke-2 hover:fill-violet-400 transition-all cursor-pointer"
                      />
                      <text
                        x={x}
                        y={185}
                        textAnchor="middle"
                        className="fill-zinc-500 font-mono text-[6px] pointer-events-none"
                      >
                        {String(row[xIdx]).substring(0, 8)}
                      </text>
                      <title>{`${row[xIdx]}: ${numericVal}`}</title>
                    </g>
                  );
                })}
              </g>
            )}
            
            {/* Base axis */}
            <line x1="30" y1="170" x2="470" y2="170" className="stroke-zinc-800" strokeWidth="1" />
          </svg>
        </div>
      </div>
    );
  }

  return null;
}
