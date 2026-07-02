"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Editor from "@monaco-editor/react";
import {
  Play, BookOpen, Lightbulb, RefreshCw, Terminal, Eye,
  Database, GitFork, AlertTriangle, CheckCircle2,
  Table, LogOut, Loader2, Sparkles, AlertCircle, Plus,
  History, BarChart2
} from "lucide-react";

import SchemaExplorer from "@/components/workspace/SchemaExplorer";
import RelationshipExplorer from "@/components/workspace/RelationshipExplorer";
import QueryHistory from "@/components/workspace/QueryHistory";
import TeachingPanel from "@/components/workspace/TeachingPanel";
import SQLResultsViewer from "@/components/workspace/SQLResultsViewer";

// 1. Strict TypeScript Interfaces (FE-004)
interface DataSource {
  id: string;
  name: string;
  type: string;
  description?: string;
}

interface MetadataField {
  table_name: string;
  column_name: string;
  data_type: string;
  is_nullable: boolean;
  is_primary_key: boolean;
  is_foreign_key: boolean;
  description?: string;
}

interface Relationship {
  source_table: string;
  source_column: string;
  target_table: string;
  target_column: string;
}

interface QueryLog {
  id: string;
  query_text: string;
  status: string;
  execution_time_ms: number;
  created_at: string;
}

export default function WorkspacePage() {
  const router = useRouter();
  const [authorized, setAuthorized] = useState(false);
  const [email, setEmail] = useState("");
  const [apiHost, setApiHost] = useState("");

  // Data sources state
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [activeDs, setActiveDs] = useState<DataSource | null>(null);
  const [loadingDs, setLoadingDs] = useState(true);

  // Schema Explorer state
  const [metadata, setMetadata] = useState<MetadataField[]>([]);
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [expandedTables, setExpandedTables] = useState<Record<string, boolean>>({});
  const [loadingSchema, setLoadingSchema] = useState(false);
  const [activeTabLeft, setActiveTabLeft] = useState<"schema" | "relations" | "history">("schema");

  // Workspace query inputs/outputs
  const [nlQuery, setNlQuery] = useState("");
  const [sql, setSql] = useState("");
  const [loadingSql, setLoadingSql] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);

  // SQL Action Results (Explanation, Optimization, Debug)
  const [explanation, setExplanation] = useState("");
  const [optReport, setOptReport] = useState<any>(null);
  const [debugReport, setDebugReport] = useState<any>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [impact, setImpact] = useState<any>(null);
  const [validation, setValidation] = useState<any>(null);

  // Execution Results
  const [execResult, setExecResult] = useState<any>(null);
  const [execError, setExecError] = useState("");
  const [executing, setExecuting] = useState(false);
  const [activeTabBottom, setActiveTabBottom] = useState<"results" | "chart" | "actions">("results");

  // UI toggles
  const [teachingMode, setTeachingMode] = useState(false);
  const [queryHistory, setQueryHistory] = useState<QueryLog[]>([]);

  // Chart visualizer options
  const [chartType, setChartType] = useState<"bar" | "line" | "pie">("bar");
  const [xAxisCol, setXAxisCol] = useState("");
  const [yAxisCol, setYAxisCol] = useState("");

  // 2. Fetch Helper with Retry Strategy (FE-007)
  const fetchWithRetry = async (url: string, options: RequestInit = {}, retries = 3, backoff = 1000): Promise<Response> => {
    try {
      const res = await fetch(url, options);
      if (!res.ok && (res.status >= 500 || res.status === 429) && retries > 0) {
        logger("Transient API warning. Retrying connection...");
        await new Promise(r => setTimeout(r, backoff));
        return fetchWithRetry(url, options, retries - 1, backoff * 1.5);
      }
      return res;
    } catch (err) {
      if (retries > 0) {
        logger("Connection failed. Retrying...");
        await new Promise(r => setTimeout(r, backoff));
        return fetchWithRetry(url, options, retries - 1, backoff * 1.5);
      }
      throw err;
    }
  };

  const logger = (msg: string) => {
    console.warn(`[Workspace Client] ${msg}`);
  };

  // FE-001 & FE-010: Active session validation on mount
  useEffect(() => {
    const rawUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const backendUrl = rawUrl.replace(/\/api\/v1\/?$/, "").replace(/\/$/, "");
    setApiHost(backendUrl);
    
    const checkSession = async () => {
      try {
        const response = await fetch(`${backendUrl}/api/v1/auth/me`, {
          method: "GET",
          credentials: "include"
        });
        if (!response.ok) {
          router.push("/");
          return;
        }
        const user = await response.json();
        setEmail(user.email);
        setAuthorized(true);
        
        // Load initial data
        fetchDataSources(backendUrl);
        fetchQueryHistory(backendUrl);
      } catch (err) {
        console.warn("Session verification failed. Redirecting...", err);
        router.push("/");
      }
    };
    checkSession();
  }, [router]);

  // Fetch registered data sources
  const fetchDataSources = async (host: string) => {
    setLoadingDs(true);
    try {
      const response = await fetchWithRetry(`${host}/api/v1/data-sources/`, {
        credentials: "include"
      });
      if (response.ok) {
        const data = await response.json();
        setDataSources(data);
        if (data.length > 0) {
          setActiveDs(data[0]);
          fetchSchema(data[0].id, host);
        }
      }
    } catch (err) {
      console.error("Failed to load datasources", err);
    } finally {
      setLoadingDs(false);
    }
  };

  // Fetch metadata and relationships for active source
  const fetchSchema = async (dsId: string, host: string) => {
    setLoadingSchema(true);
    try {
      // 1. Fetch metadata columns
      const metaRes = await fetchWithRetry(`${host}/api/v1/schema/metadata/${dsId}`, {
        credentials: "include"
      });
      if (metaRes.ok) {
        const metaData = await metaRes.json();
        setMetadata(metaData);
        if (metaData.length > 0) {
          setExpandedTables({ [metaData[0].table_name]: true });
        }
      }
      
      // 2. Fetch relationships
      const relRes = await fetchWithRetry(`${host}/api/v1/schema/relationships/${dsId}`, {
        credentials: "include"
      });
      if (relRes.ok) {
        const relData = await relRes.json();
        setRelationships(relData);
      }
    } catch (err) {
      console.error("Failed to load schema details", err);
    } finally {
      setLoadingSchema(false);
    }
  };

  const handleSelectDataSource = (dsId: string) => {
    const ds = dataSources.find((item) => item.id === dsId);
    if (ds) {
      setActiveDs(ds);
      fetchSchema(ds.id, apiHost);
    }
  };

  // Fetch historical query logs
  const fetchQueryHistory = async (host: string) => {
    try {
      const response = await fetchWithRetry(`${host}/api/v1/history/query-logs`, {
        credentials: "include"
      });
      if (response.ok) {
        const data = await response.json();
        setQueryHistory(data);
      }
    } catch (err) {
      console.error("Query history retrieval failed", err);
    }
  };

  // Trigger SQL generation workflow via LangGraph multi-agent
  const handleGenerateSQL = async () => {
    if (!nlQuery.trim() || !activeDs) return;
    setLoadingSql(true);
    setExplanation("");
    setOptReport(null);
    setDebugReport(null);
    setExecError("");
    
    try {
      const response = await fetch(`${apiHost}/api/v1/sql/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          nl_query: nlQuery,
          data_source_id: activeDs.id,
          conversation_id: conversationId || undefined
        })
      });
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || "SQL Generation workflow failed.");
      }
      
      setSql(data.generated_sql);
      setConfidence(data.confidence_score);
      setImpact(data.impact);
      setValidation(data.validation);
      setExplanation(data.explanation);
      setConversationId(data.conversation_id);
      
      setActiveTabBottom("results");
    } catch (err: any) {
      setExecError(err.message || "Failed to generate SQL.");
    } finally {
      setLoadingSql(false);
    }
  };

  // Execute SELECT query securely
  const handleExecuteSQL = async () => {
    if (!sql.trim() || !activeDs) return;
    setExecuting(true);
    setExecError("");
    setExecResult(null);
    
    try {
      const response = await fetch(`${apiHost}/api/v1/sql/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          sql: sql,
          data_source_id: activeDs.id
        })
      });
      
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Query execution failed.");
      }
      
      setExecResult(data);
      
      if (data.columns.length > 0) {
        setXAxisCol(data.columns[0]);
        setYAxisCol(data.columns[1] || data.columns[0]);
      }
      
      // Refresh history locally without reloading page (FE-008)
      fetchQueryHistory(apiHost);
    } catch (err: any) {
      setExecError(err.message || "Execution blocked or failed.");
      setActiveTabBottom("results");
    } finally {
      setExecuting(false);
    }
  };

  // Optimize SQL Query
  const handleOptimizeSQL = async () => {
    if (!sql.trim() || !activeDs) return;
    setLoadingSql(true);
    setOptReport(null);
    try {
      const response = await fetch(`${apiHost}/api/v1/sql/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ sql, data_source_id: activeDs.id })
      });
      const data = await response.json();
      if (response.ok) {
        setOptReport(data);
        setActiveTabBottom("actions");
      } else {
        throw new Error(data.detail);
      }
    } catch (err: any) {
      setExecError(err.message);
    } finally {
      setLoadingSql(false);
    }
  };

  // Debug/Fix broken query
  const handleDebugSQL = async () => {
    if (!sql.trim() || !activeDs) return;
    setLoadingSql(true);
    setDebugReport(null);
    
    const debugPrompt = `SQL Query: ${sql}\nError reported: ${execError}`;
    
    try {
      const response = await fetch(`${apiHost}/api/v1/sql/debug`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ sql: debugPrompt, data_source_id: activeDs.id })
      });
      const data = await response.json();
      if (response.ok) {
        setDebugReport(data);
        setSql(data.corrected_sql);
        setExecError("");
        setActiveTabBottom("actions");
      } else {
        throw new Error(data.detail);
      }
    } catch (err: any) {
      setExecError(err.message);
    } finally {
      setLoadingSql(false);
    }
  };

  // Log out
  const handleLogout = async () => {
    try {
      await fetch(`${apiHost}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include"
      });
    } catch (err) {
      // Ignore network errors on logout
    }
    localStorage.removeItem("user_email");
    router.push("/");
  };

  const toggleTable = (tableName: string) => {
    setExpandedTables(prev => ({ ...prev, [tableName]: !prev[tableName] }));
  };

  const handleSelectQueryFromHistory = (sqlText: string) => {
    setSql(sqlText);
  };

  if (!authorized) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950 text-white gap-3">
        <Loader2 className="animate-spin text-violet-500" size={32} />
        <span className="text-sm font-medium">Validating workspace session...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-background text-foreground text-sm overflow-hidden">
      {/* Header bar */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-border glass-card">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-violet-600 to-indigo-600 flex items-center justify-center font-bold text-white shadow-md shadow-violet-500/20">
            IF
          </div>
          <div>
            <h1 className="font-bold text-base tracking-tight text-white">InsightForge AI</h1>
            <p className="text-xs text-zinc-500">Workspace Dashboard</p>
          </div>
        </div>

        {/* Middle Status Indicators */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Database size={14} className="text-violet-400" />
            <select
              value={activeDs?.id || ""}
              onChange={(e) => handleSelectDataSource(e.target.value)}
              disabled={dataSources.length === 0}
              className="bg-zinc-900 border border-zinc-800 rounded px-2.5 py-1 text-xs text-zinc-300 font-medium outline-none focus:border-violet-500 cursor-pointer"
            >
              {dataSources.map((ds) => (
                <option key={ds.id} value={ds.id}>
                  {ds.name} ({ds.type})
                </option>
              ))}
              {dataSources.length === 0 && (
                <option value="">No databases</option>
              )}
            </select>
          </div>

          <button
            onClick={() => router.push("/workspace/connect")}
            className="flex items-center gap-1.5 px-3 py-1 bg-violet-600 hover:bg-violet-500 border border-violet-500/30 rounded text-xs font-semibold text-white transition-all cursor-pointer shadow-sm"
            title="Connect a new database or dataset"
          >
            <Plus size={13} /> Connect Database
          </button>

          <div className="flex items-center gap-2 ml-2 pl-4 border-l border-zinc-800">
            <span className="text-xs text-zinc-400">Teaching Mode</span>
            <button
              onClick={() => setTeachingMode(!teachingMode)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors cursor-pointer ${
                teachingMode ? "bg-violet-600" : "bg-zinc-800"
              }`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  teachingMode ? "translate-x-4.5" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        </div>

        {/* User profile dropdown & logout */}
        <div className="flex items-center gap-4">
          <span className="text-xs text-zinc-400 font-medium">{email}</span>
          <button
            onClick={handleLogout}
            className="p-1.5 rounded hover:bg-zinc-900 border border-transparent hover:border-zinc-800 text-zinc-400 hover:text-white transition-all cursor-pointer"
            title="Log Out"
          >
            <LogOut size={16} />
          </button>
        </div>
      </header>

      {/* Main layout wrapper */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* LEFT COLUMN: Explorer panels */}
        <div className="w-80 flex flex-col border-r border-border bg-zinc-950/20">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-zinc-950/60">
            <span className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
              <Database size={13} className="text-violet-400" /> Data Sources
            </span>
            <button
              onClick={() => router.push("/workspace/connect")}
              className="flex items-center gap-1 px-2.5 py-1 bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/30 rounded text-[11px] font-semibold text-violet-300 hover:text-white transition-all cursor-pointer"
            >
              <Plus size={11} /> Connect
            </button>
          </div>
          <div className="flex border-b border-border bg-zinc-950/40">
            <button
              onClick={() => setActiveTabLeft("schema")}
              className={`flex-1 py-3 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                activeTabLeft === "schema"
                  ? "border-violet-500 text-white"
                  : "border-transparent text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Table size={13} /> Schema
            </button>
            <button
              onClick={() => setActiveTabLeft("relations")}
              className={`flex-1 py-3 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                activeTabLeft === "relations"
                  ? "border-violet-500 text-white"
                  : "border-transparent text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <GitFork size={13} /> Relations
            </button>
            <button
              onClick={() => setActiveTabLeft("history")}
              className={`flex-1 py-3 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
                activeTabLeft === "history"
                  ? "border-violet-500 text-white"
                  : "border-transparent text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <History size={13} /> History
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {activeTabLeft === "schema" && (
              <SchemaExplorer
                metadata={metadata}
                loading={loadingSchema}
                expandedTables={expandedTables}
                onToggleTable={toggleTable}
              />
            )}

            {activeTabLeft === "relations" && (
              <RelationshipExplorer
                relationships={relationships}
                loading={loadingSchema}
              />
            )}

            {activeTabLeft === "history" && (
              <QueryHistory
                queryHistory={queryHistory}
                onSelectQuery={handleSelectQueryFromHistory}
              />
            )}
          </div>
        </div>

        {/* 3. Empty State Experience (FE-009) */}
        {loadingDs ? (
          <div className="flex-1 flex flex-col items-center justify-center text-zinc-500 gap-2 bg-zinc-950/5">
            <Loader2 size={32} className="animate-spin text-violet-500" />
            <p className="text-sm">Retrieving registered data connectors...</p>
          </div>
        ) : dataSources.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-8 bg-zinc-950/5">
            <Database size={48} className="text-zinc-700 mb-4 animate-pulse" />
            <h3 className="text-lg font-bold text-white mb-2">No Databases Registered</h3>
            <p className="text-xs text-zinc-400 max-w-sm mb-6 leading-relaxed">
              Get started by establishing a secure database connector. Once created, InsightForge AI will auto-discover elements and generate embeddings.
            </p>
            <button
              onClick={() => router.push("/workspace/connect")}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 rounded text-xs font-semibold text-white hover:from-violet-500 hover:to-indigo-500 cursor-pointer shadow-lg shadow-violet-500/20"
            >
              <Plus size={14} /> Connect First Database
            </button>
          </div>
        ) : (
          /* WORKSPACE LAYOUT (Default loaded experience) */
          <div className="flex-1 flex overflow-hidden">
            
            {/* CENTER PANEL: Query formulation & results */}
            <div className="flex-1 flex flex-col min-w-0 border-r border-border">
              
              {/* Upper Section: Monaco Workspace & Prompt */}
              <div className="flex-1 flex flex-col p-6 min-h-[300px] gap-6 overflow-y-auto">
                
                {/* Prompt block */}
                <div className="space-y-2">
                  <label className="text-xs font-semibold text-zinc-400">Natural Language Request</label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={nlQuery}
                      onChange={(e) => setNlQuery(e.target.value)}
                      suppressHydrationWarning={true}
                      placeholder="e.g. Find all products purchased in the state of SP after 2018"
                      className="flex-1 rounded-md border border-zinc-900 bg-zinc-950/80 px-4 py-2.5 text-xs text-white placeholder-zinc-500 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all"
                    />
                    <button
                      onClick={handleGenerateSQL}
                      disabled={loadingSql || !nlQuery.trim()}
                      className="px-4 py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 rounded font-semibold text-white hover:from-violet-500 hover:to-indigo-500 disabled:opacity-50 flex items-center gap-1.5 cursor-pointer text-xs"
                    >
                      {loadingSql ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                      Generate SQL
                    </button>
                  </div>
                </div>

                {/* Monaco Editor Section */}
                <div className="flex-1 flex flex-col border border-zinc-900 rounded bg-zinc-950/60 overflow-hidden min-h-[200px]">
                  <div className="flex items-center justify-between px-4 py-2 bg-zinc-950 border-b border-zinc-900">
                    <span className="text-[10px] text-zinc-400 font-bold uppercase tracking-wider font-mono">Monaco SQL Editor</span>
                    
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleOptimizeSQL}
                        disabled={loadingSql || !sql.trim()}
                        className="px-2 py-1 bg-zinc-900 hover:bg-zinc-800 text-[10px] text-zinc-300 font-semibold rounded flex items-center gap-1 cursor-pointer"
                        title="Analyze and optimize database execution"
                      >
                        <Lightbulb size={10} /> Optimize
                      </button>
                      <button
                        onClick={handleDebugSQL}
                        disabled={loadingSql || !sql.trim()}
                        className="px-2 py-1 bg-zinc-900 hover:bg-zinc-800 text-[10px] text-zinc-300 font-semibold rounded flex items-center gap-1 cursor-pointer"
                        title="Fix query syntactic errors"
                      >
                        <RefreshCw size={10} /> Auto-Fix
                      </button>
                      <button
                        onClick={handleExecuteSQL}
                        disabled={executing || !sql.trim()}
                        className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-[10px] text-white font-bold rounded flex items-center gap-1 cursor-pointer"
                      >
                        {executing ? <Loader2 size={10} className="animate-spin" /> : <Play size={10} />}
                        Run SQL
                      </button>
                    </div>
                  </div>

                  <div className="flex-1 p-2">
                    <Editor
                      height="100%"
                      defaultLanguage="sql"
                      theme="vs-dark"
                      value={sql}
                      onChange={(value) => setSql(value || "")}
                      options={{
                        minimap: { enabled: false },
                        fontSize: 12,
                        wordWrap: "on",
                        scrollBeyondLastLine: false,
                        automaticLayout: true
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Lower Section: Query results viewer */}
              <div className="h-80 border-t border-border flex flex-col bg-zinc-950/20">
                <div className="flex border-b border-border bg-zinc-950/40">
                  <button
                    onClick={() => setActiveTabBottom("results")}
                    className={`px-6 py-3 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
                      activeTabBottom === "results"
                        ? "border-violet-500 text-white"
                        : "border-transparent text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <Table size={13} /> Query Results
                  </button>
                  <button
                    onClick={() => setActiveTabBottom("chart")}
                    className={`px-6 py-3 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
                      activeTabBottom === "chart"
                        ? "border-violet-500 text-white"
                        : "border-transparent text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <BarChart2 size={13} /> Chart Visualizer
                  </button>
                  {optReport && (
                    <button
                      onClick={() => setActiveTabBottom("actions")}
                      className={`px-6 py-3 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
                        activeTabBottom === "actions"
                          ? "border-violet-500 text-white"
                          : "border-transparent text-zinc-400 hover:text-zinc-200"
                      }`}
                    >
                      <Lightbulb size={13} /> Optimization Report
                    </button>
                  )}
                </div>

                <div className="flex-1 p-4 overflow-hidden">
                  {activeTabBottom === "results" || activeTabBottom === "chart" ? (
                    <SQLResultsViewer
                      execResult={execResult}
                      execError={execError}
                      activeTabBottom={activeTabBottom}
                      chartType={chartType}
                      xAxisCol={xAxisCol}
                      yAxisCol={yAxisCol}
                      onChartTypeChange={setChartType}
                      onXAxisChange={setXAxisCol}
                      onYAxisChange={setYAxisCol}
                    />
                  ) : (
                    /* Render optimization report results inline */
                    activeTabBottom === "actions" && optReport && (
                      <div className="h-full overflow-y-auto space-y-4 pr-2 text-xs">
                        <div className="p-3 border border-violet-500/20 bg-violet-500/5 rounded">
                          <h4 className="font-semibold text-white mb-1.5">SQL Performance Audit</h4>
                          <p className="text-zinc-400 leading-relaxed">{optReport.performance_analysis}</p>
                        </div>
                        {optReport.recommendations && optReport.recommendations.length > 0 && (
                          <div className="space-y-1.5">
                            <h4 className="font-semibold text-zinc-300">Action Recommendations:</h4>
                            <ul className="list-disc pl-4 space-y-1 text-zinc-400">
                              {optReport.recommendations.map((rec: string, idx: number) => (
                                <li key={idx}>{rec}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )
                  )}
                </div>
              </div>
            </div>

            {/* RIGHT COLUMN: Teaching mode panel */}
            {teachingMode && (
              <div className="w-80 border-l border-border bg-zinc-950/20 overflow-y-auto p-4">
                <h3 className="font-bold text-xs text-white uppercase tracking-wider mb-4">Teaching Assistant Mode</h3>
                
                <TeachingPanel
                  confidence={confidence}
                  validation={validation}
                  impact={impact}
                  explanation={explanation}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
