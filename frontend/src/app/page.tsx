"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Lock, Mail, Server, ArrowRight, ShieldCheck } from "lucide-react";

export default function AuthPage() {
  const router = useRouter();
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [apiHost, setApiHost] = useState("");

  useEffect(() => {
    // FE-001: Load API URL from environment config or fallback
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    setApiHost(backendUrl);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const endpoint = isLogin ? "/api/v1/auth/login" : "/api/v1/auth/register";

    try {
      const response = await fetch(`${apiHost}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include", // Ensure cookies are received/stored (SEC-005)
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Authentication failed. Check your credentials.");
      }

      localStorage.removeItem("token");
      localStorage.setItem("user_email", email);
      router.push("/workspace");
    } catch (err: any) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };


  return (
    <main className="relative flex min-h-screen items-center justify-center bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-950/20 via-zinc-950 to-zinc-950 px-4">
      {/* Background ambient light */}
      <div className="absolute top-1/4 left-1/4 h-72 w-72 rounded-full bg-violet-600/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 h-96 w-96 rounded-full bg-indigo-600/10 blur-[150px] pointer-events-none" />

      <div className="w-full max-w-md z-10">
        {/* Header */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-violet-500/20 bg-violet-500/5 mb-3 text-sm text-violet-400">
            <ShieldCheck size={14} /> Zero Trust Database Intelligence
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-white via-zinc-300 to-zinc-500 bg-clip-text text-transparent">
            InsightForge AI
          </h1>
          <p className="mt-2 text-zinc-400 text-sm">
            Schema-Aware SQL Generation & Visual Explorer
          </p>
        </div>

        {/* Card */}
        <div className="glass-card rounded-xl p-8 shadow-2xl">
          <form onSubmit={handleSubmit} className="space-y-6" suppressHydrationWarning={true}>
            <h2 className="text-xl font-semibold text-white">
              {isLogin ? "Welcome back" : "Create your account"}
            </h2>

            {error && (
              <div className={`p-3 rounded text-xs border ${error.includes("registered") ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400" : "bg-red-500/10 border-red-500/20 text-red-400"}`}>
                {error}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">Email address</label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-zinc-500">
                    <Mail size={16} />
                  </span>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    suppressHydrationWarning={true}
                    className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 py-2.5 pl-10 pr-4 text-sm text-white placeholder-zinc-500 outline-none transition-all focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
                    placeholder="name@example.com"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-medium text-zinc-400">Password</label>
                </div>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-zinc-500">
                    <Lock size={16} />
                  </span>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    suppressHydrationWarning={true}
                    className="w-full rounded-md border border-zinc-800 bg-zinc-950/80 py-2.5 pl-10 pr-4 text-sm text-white placeholder-zinc-500 outline-none transition-all focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
                    placeholder="••••••••"
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-gradient-to-r from-violet-600 to-indigo-600 py-2.5 text-sm font-semibold text-white hover:from-violet-500 hover:to-indigo-500 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:ring-offset-2 focus:ring-offset-zinc-950 disabled:opacity-50 transition-all cursor-pointer shadow-lg shadow-violet-500/10"
            >
              {loading ? "Please wait..." : isLogin ? "Access Workspace" : "Register"}
              {!loading && <ArrowRight size={16} />}
            </button>
          </form>


          {/* Toggle login/register */}
          <div className="mt-6 text-center text-xs">
            <button
              onClick={() => setIsLogin(!isLogin)}
              className="text-zinc-400 hover:text-violet-400 transition-colors"
            >
              {isLogin ? "Don't have an account? Sign up" : "Already have an account? Log in"}
            </button>
          </div>
        </div>

        {/* Footer info */}
        <div className="mt-8 text-center text-xs text-zinc-600 flex items-center justify-center gap-3">
          <span className="flex items-center gap-1"><Server size={12} /> Neon Postgres</span>
          <span>•</span>
          <span className="flex items-center gap-1"><Lock size={12} /> AES-256</span>
          <span>•</span>
          <span className="flex items-center gap-1"><ArrowRight size={12} /> SELECT-Only</span>
        </div>
      </div>
    </main>
  );
}
