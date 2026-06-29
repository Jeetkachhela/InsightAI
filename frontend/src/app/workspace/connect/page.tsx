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
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const apiHost = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const payload = {
      name,
      type,
      description: description || f"Connection for {name}",
      connection_details: {
        host: type === "sqlite" ? null : host,
        port: type === "sqlite" ? null : (port ? parseInt(port) : null),
        username: type === "sqlite" ? null : username,
        password: type === "sqlite" ? null : password,
        database_name: databaseName,
        schema_name: schemaName || "public"
      }
    };

    try {
      const res = await fetch(`${apiHost}/api/v1/data-sources/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
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

          <form onSubmit={handleSubmit} className="space-y-4" suppressHydrationWarning={true}>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Connection Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Production Analytics"
                  suppressHydrationWarning={true}
                  className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 px-3 py-2 text-xs text-white placeholder-zinc-500 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Database Engine</label>
                <select
                  value={type}
                  onChange={(e) => {
                    setType(e.target.value);
                    if (e.target.value === "sqlite") {
                      setDatabaseName("sample_ecommerce.db");
                    } else if (e.target.value === "postgresql") {
                      setPort("5432");
                    } else if (e.target.value === "mysql") {
                      setPort("3306");
                    }
                  }}
                  suppressHydrationWarning={true}
                  className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 px-3 py-2 text-xs text-white outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-all"
                >
                  <option value="postgresql">PostgreSQL</option>
                  <option value="mysql">MySQL</option>
                  <option value="sqlite">SQLite</option>
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
