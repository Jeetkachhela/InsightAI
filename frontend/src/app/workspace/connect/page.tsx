"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Database, ArrowLeft, Loader2, CheckCircle2, AlertCircle } from "lucide-react";

export default function ConnectDataSourcePage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [type, setType] = useState("postgresql");
  const [description, setDescription] = useState("");
  const [host, setHost] = useState("localhost");
  const [port, setPort] = useState("5432");
  const [username, setUsername] = useState("postgres");
  const [password, setPassword] = useState("");
  const [databaseName, setDatabaseName] = useState("");
  const [schemaName, setSchemaName] = useState("public");
  
  const [connectionUri, setConnectionUri] = useState("");
  const [inputMode, setInputMode] = useState<"fields" | "uri">("fields");

  const parseConnectionUri = (uri: string) => {
    setConnectionUri(uri);
    try {
      const trimmed = uri.trim();
      if (!trimmed) return;

      let parsedType = "postgresql";
      if (trimmed.startsWith("postgresql://") || trimmed.startsWith("postgres://")) {
        if (trimmed.includes("neon.tech")) parsedType = "neon";
        else if (trimmed.includes("supabase.co")) parsedType = "supabase";
        else parsedType = "postgresql";
      } else if (trimmed.startsWith("mongodb://") || trimmed.startsWith("mongodb+srv://")) {
        parsedType = "mongodb";
      } else if (trimmed.startsWith("mysql://")) {
        parsedType = "mysql";
      }

      setType(parsedType);

      const normalized = trimmed.replace(/^mongodb\+srv:\/\//, "http://").replace(/^(postgresql|postgres|mysql):\/\//, "http://");
      const urlObj = new URL(normalized);
      if (urlObj.hostname) setHost(urlObj.hostname);
      if (urlObj.port) setPort(urlObj.port);
      else if (parsedType === "mysql") setPort("3306");
      else setPort("5432");

      if (urlObj.username) setUsername(decodeURIComponent(urlObj.username));
      if (urlObj.password) setPassword(decodeURIComponent(urlObj.password));

      const pathDb = urlObj.pathname.replace(/^\//, "").split("?")[0];
      if (pathDb) setDatabaseName(pathDb);
    } catch (err) {
      // Passively ignore incomplete URIs while user types
    }
  };

  const handleSelectEngine = (selectedEngine: string) => {
    setType(selectedEngine);
    if (selectedEngine === "sqlite") {
      setDatabaseName("sample_ecommerce.db");
      setSchemaName("main");
    } else if (selectedEngine === "mysql") {
      setPort("3306");
    } else if (selectedEngine === "neon" || selectedEngine === "supabase" || selectedEngine === "postgresql") {
      setPort("5432");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    // Trim inputs
    const trimmedName = name.trim();
    const trimmedHost = host.trim();
    const trimmedPort = port.trim();
    const trimmedUsername = username.trim();
    const trimmedDatabaseName = databaseName.trim();
    const trimmedSchemaName = schemaName.trim();

    // 1. Validate connection name
    if (!trimmedName) {
      setError("Connection name cannot be empty or whitespace only.");
      return;
    }

    // 2. Validate engine-specific details
    if (type !== "sqlite") {
      if (!trimmedHost) {
        setError("Host cannot be empty or whitespace only.");
        return;
      }
      
      // Host format validation (SSRF metadata protection)
      const lowercaseHost = trimmedHost.toLowerCase();
      const blockedHostnames = ["metadata.google.internal", "169.254.169.254", "metadata.internal"];
      if (blockedHostnames.includes(lowercaseHost)) {
        setError("Connection to cloud metadata endpoints is not allowed.");
        return;
      }

      const parsedPort = parseInt(trimmedPort);
      if (isNaN(parsedPort) || parsedPort < 1 || parsedPort > 65535) {
        setError("Port must be a valid integer between 1 and 65535.");
        return;
      }

      if (!trimmedUsername) {
        setError("Username cannot be empty or whitespace only.");
        return;
      }
    }

    // 3. Validate database name
    if (!trimmedDatabaseName) {
      setError("Database name cannot be empty or whitespace only.");
      return;
    }

    // 4. Validate schema name
    if (!trimmedSchemaName) {
      setError("Schema name cannot be empty or whitespace only.");
      return;
    }

    setLoading(true);

    const getBackendUrl = () => {
      const envUrl = process.env.NEXT_PUBLIC_API_URL;
      if (envUrl) {
        return envUrl.replace(/\/api\/v1\/?$/, "").replace(/\/$/, "");
      }
      if (typeof window !== "undefined") {
        const hostname = window.location.hostname;
        const protocol = window.location.protocol;
        if (hostname === "127.0.0.1" || hostname === "localhost") {
          return `${protocol}//${hostname}:8000`;
        }
        return `${protocol}//${window.location.host}`;
      }
      return "http://localhost:8000";
    };
    const apiHost = getBackendUrl();

    const payload = {
      name: trimmedName,
      type,
      description: description.trim() || `Connection for ${trimmedName}`,
      connection_details: {
        host: type === "sqlite" ? null : trimmedHost,
        port: type === "sqlite" ? null : parseInt(trimmedPort),
        username: type === "sqlite" ? null : trimmedUsername,
        password: type === "sqlite" ? null : password,
        database_name: trimmedDatabaseName,
        schema_name: trimmedSchemaName
      }
    };

    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
      const res = await fetch(`${apiHost}/api/v1/data-sources/`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        credentials: "include",
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: "Failed to connect data source" }));
        throw new Error(data.detail || "Connection failed");
      }

      setSuccess(true);
      setTimeout(() => {
        router.push("/workspace");
      }, 1000);
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-white flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute -top-40 -left-40 w-96 h-96 bg-violet-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-xl z-10">
        <button
          onClick={() => router.push("/workspace")}
          className="flex items-center gap-2 text-xs font-semibold text-zinc-400 hover:text-white transition-colors mb-6 cursor-pointer"
        >
          <ArrowLeft size={16} /> Back to Workspace
        </button>

        <div className="glass-card rounded-xl p-8 shadow-2xl border border-zinc-800 bg-zinc-900/60 backdrop-blur-xl">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-3 rounded-lg bg-violet-500/10 border border-violet-500/20 text-violet-400">
              <Database size={24} />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Connect Database</h1>
              <p className="text-xs text-zinc-400">Register a new database connector for AI schema discovery</p>
            </div>
          </div>

          {error && (
            <div className="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-2">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="mb-6 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
              <CheckCircle2 size={16} />
              <span>Database connected successfully! Discovering schema... Redirecting...</span>
            </div>
          )}

          {/* Quick Engine Selector Badges */}
          <div className="mb-6">
            <label className="block text-xs font-medium text-zinc-400 mb-2">Select Database Engine / Cloud Preset</label>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
              {[
                { id: "neon", label: "Neon", icon: "⚡", desc: "Serverless Postgres" },
                { id: "supabase", label: "Supabase", icon: "⚡", desc: "Cloud Postgres" },
                { id: "postgresql", label: "PostgreSQL", icon: "🐘", desc: "Standard DB" },
                { id: "mongodb", label: "MongoDB", icon: "🍃", desc: "Document NoSQL" },
                { id: "mysql", label: "MySQL", icon: "🐬", desc: "Relational DB" },
                { id: "sqlite", label: "SQLite", icon: "📁", desc: "Local / Sample" }
              ].map((engine) => (
                <button
                  key={engine.id}
                  type="button"
                  onClick={() => handleSelectEngine(engine.id)}
                  className={`p-2.5 rounded-lg border text-left flex flex-col items-center justify-center transition-all cursor-pointer ${
                    type === engine.id
                      ? "border-violet-500 bg-violet-500/10 text-white shadow-sm shadow-violet-500/20"
                      : "border-zinc-800 bg-zinc-950/60 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                  }`}
                >
                  <span className="text-lg mb-1">{engine.icon}</span>
                  <span className="text-xs font-semibold">{engine.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Connection Mode Switcher */}
          <div className="flex items-center gap-2 mb-4 p-1 rounded-lg bg-zinc-950/80 border border-zinc-800">
            <button
              type="button"
              onClick={() => setInputMode("fields")}
              className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-all ${
                inputMode === "fields" ? "bg-zinc-800 text-white shadow" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Detailed Form Fields
            </button>
            <button
              type="button"
              onClick={() => setInputMode("uri")}
              className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-all ${
                inputMode === "uri" ? "bg-zinc-800 text-white shadow" : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              Paste Connection URI (Cloud String)
            </button>
          </div>

          {inputMode === "uri" && (
            <div className="mb-4 p-3 rounded-lg border border-violet-500/30 bg-violet-500/5">
              <label className="block text-xs font-medium text-violet-300 mb-1">
                Paste Cloud Connection URI (e.g. Neon, Supabase, MongoDB)
              </label>
              <input
                type="text"
                value={connectionUri}
                onChange={(e) => parseConnectionUri(e.target.value)}
                placeholder="postgresql://alex:password@ep-cool-db.neon.tech/neondb?sslmode=require"
                className="w-full rounded-md border border-zinc-800 bg-zinc-950/90 px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 font-mono transition-all"
              />
              <p className="text-[10px] text-zinc-400 mt-1">
                Auto-parses host, port, username, password, and database name into your connection settings below.
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" suppressHydrationWarning={true}>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Connection Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Production Cloud Analytics"
                  suppressHydrationWarning={true}
                  className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Database Engine</label>
                <select
                  value={type}
                  onChange={(e) => handleSelectEngine(e.target.value)}
                  suppressHydrationWarning={true}
                  className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 px-3 py-2 text-xs text-white outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all"
                >
                  <option value="neon">⚡ Neon PostgreSQL (Cloud Serverless)</option>
                  <option value="supabase">⚡ Supabase PostgreSQL (Cloud)</option>
                  <option value="postgresql">🐘 PostgreSQL (Standard / AWS RDS)</option>
                  <option value="mongodb">🍃 MongoDB (NoSQL Document Store)</option>
                  <option value="mysql">🐬 MySQL / MariaDB</option>
                  <option value="sqlite">📁 SQLite / Sample E-Commerce</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1">Description (Optional)</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief summary of what data resides in this database"
                suppressHydrationWarning={true}
                className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all"
              />
            </div>

            {type !== "sqlite" && (
              <>
                <div className="grid grid-cols-3 gap-4">
                  <div className="col-span-2">
                    <label className="block text-xs font-medium text-zinc-400 mb-1">Host</label>
                    <input
                      type="text"
                      required
                      value={host}
                      onChange={(e) => setHost(e.target.value)}
                      placeholder="localhost or db.example.com"
                      suppressHydrationWarning={true}
                      className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">Port</label>
                    <input
                      type="number"
                      required
                      value={port}
                      onChange={(e) => setPort(e.target.value)}
                      placeholder="5432"
                      suppressHydrationWarning={true}
                      className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">Username</label>
                    <input
                      type="text"
                      required
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="postgres"
                      suppressHydrationWarning={true}
                      className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-zinc-400 mb-1">Password</label>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      suppressHydrationWarning={true}
                      className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all"
                    />
                  </div>
                </div>
              </>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Database Name / Path</label>
                <input
                  type="text"
                  required
                  value={databaseName}
                  onChange={(e) => setDatabaseName(e.target.value)}
                  placeholder={type === "sqlite" ? "sample_ecommerce.db" : "my_database"}
                  suppressHydrationWarning={true}
                  className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Schema Name</label>
                <input
                  type="text"
                  required
                  value={schemaName}
                  onChange={(e) => setSchemaName(e.target.value)}
                  placeholder={type === "sqlite" ? "main" : "public"}
                  suppressHydrationWarning={true}
                  className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all"
                />
              </div>
            </div>

            <div className="pt-4">
              <button
                type="submit"
                disabled={loading || success}
                className="w-full py-2.5 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 rounded-md font-semibold text-xs text-white flex items-center justify-center gap-2 shadow-lg shadow-violet-500/10 cursor-pointer transition-all disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <Loader2 size={14} className="animate-spin" /> Connecting & Discovering Schema...
                  </>
                ) : (
                  "Connect & Discover Schema"
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
