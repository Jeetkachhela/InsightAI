"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Lock, Mail, Server, ArrowRight, ShieldCheck, Database,
  Sparkles, Zap, Cpu, Terminal, Layers, Code2, GitFork,
  CheckCircle2, Search, Eye, Play, RefreshCw, LogIn, UserPlus,
  ChevronRight, BookOpen, BarChart2
} from "lucide-react";

export default function LandingAndAuthPage() {
  const router = useRouter();
  
  // Auth state
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [apiHost, setApiHost] = useState("");

  // Navigation state
  const [activeTab, setActiveTab] = useState<"overview" | "features" | "auth">("overview");

  useEffect(() => {
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
    const backendUrl = getBackendUrl();
    setApiHost(backendUrl);

    // If user is already logged in, check token/session
    const checkSession = async () => {
      try {
        const token = localStorage.getItem("token");
        const res = await fetch(`${backendUrl}/api/v1/auth/me`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          credentials: "include"
        });
        if (res.ok) {
          // Optional: if already logged in, can show "Go to Workspace" badge
        }
      } catch (e) {
        // Ignore unauth
      }
    };
    checkSession();
  }, []);

  const scrollToAuth = (loginMode = true) => {
    setIsLogin(loginMode);
    setActiveTab("auth");
    const authSection = document.getElementById("auth-section");
    if (authSection) {
      authSection.scrollIntoView({ behavior: "smooth" });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    // Normalization & whitespace validation
    const trimmedEmail = email.trim();
    const trimmedPassword = password.trim();

    if (!trimmedEmail) {
      setError("Email address cannot be empty or whitespace only.");
      return;
    }
    if (!trimmedPassword) {
      setError("Password cannot be empty or whitespace only.");
      return;
    }

    // Email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmedEmail)) {
      setError("Please enter a valid email address.");
      return;
    }

    // Password strength check on Register (parity with backend requirements)
    if (!isLogin) {
      if (trimmedPassword.length < 8) {
        setError("Password must be at least 8 characters long.");
        return;
      }
      if (!/[A-Z]/.test(trimmedPassword)) {
        setError("Password must contain at least one uppercase letter.");
        return;
      }
      if (!/[a-z]/.test(trimmedPassword)) {
        setError("Password must contain at least one lowercase letter.");
        return;
      }
      if (!/[0-9]/.test(trimmedPassword)) {
        setError("Password must contain at least one digit.");
        return;
      }
      if (!/[!@#$%^&*(),.?":{}|<>]/.test(trimmedPassword)) {
        setError("Password must contain at least one special character.");
        return;
      }
    }

    setLoading(true);
    const endpoint = isLogin ? "/api/v1/auth/login" : "/api/v1/auth/register";

    try {
      const response = await fetch(`${apiHost}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({ email: trimmedEmail, password: trimmedPassword }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Authentication failed. Check your credentials.");
      }

      if (data.access_token) {
        localStorage.setItem("token", data.access_token);
      }
      localStorage.setItem("user_email", trimmedEmail);
      
      // Transition directly to main workspace page
      router.push("/workspace");
    } catch (err: any) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-white font-sans selection:bg-violet-600 selection:text-white">
      {/* Background ambient lighting */}
      <div className="fixed top-0 left-1/4 h-[500px] w-[500px] rounded-full bg-violet-600/10 blur-[150px] pointer-events-none z-0" />
      <div className="fixed bottom-0 right-1/4 h-[500px] w-[500px] rounded-full bg-indigo-600/10 blur-[180px] pointer-events-none z-0" />

      {/* Top Navigation Header */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-zinc-950/80 border-b border-zinc-800/80 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-purple-500 flex items-center justify-center font-bold text-white shadow-lg shadow-violet-500/25">
              IF
            </div>
            <div>
              <span className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-white via-zinc-200 to-zinc-400 bg-clip-text text-transparent">
                InsightForge AI
              </span>
              <span className="ml-2 text-[10px] font-mono uppercase tracking-widest px-2 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20">
                v2.0 Autonomous
              </span>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-zinc-400">
            <a
              href="#overview"
              onClick={(e) => { e.preventDefault(); document.getElementById("overview")?.scrollIntoView({ behavior: "smooth" }); }}
              className="hover:text-white transition-colors"
            >
              Overview
            </a>
            <a
              href="#features"
              onClick={(e) => { e.preventDefault(); document.getElementById("features")?.scrollIntoView({ behavior: "smooth" }); }}
              className="hover:text-white transition-colors"
            >
              Key Features
            </a>
            <a
              href="#architecture"
              onClick={(e) => { e.preventDefault(); document.getElementById("architecture")?.scrollIntoView({ behavior: "smooth" }); }}
              className="hover:text-white transition-colors"
            >
              Architecture
            </a>
            <a
              href="#auth-section"
              onClick={(e) => { e.preventDefault(); scrollToAuth(true); }}
              className="hover:text-white transition-colors"
            >
              Authentication
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <button suppressHydrationWarning={true}
              onClick={() => scrollToAuth(true)}
              className="px-4 py-2 rounded-lg border border-zinc-800 hover:border-zinc-700 bg-zinc-900/80 text-xs font-semibold text-zinc-300 hover:text-white transition-all cursor-pointer"
            >
              Sign In
            </button>
            <button suppressHydrationWarning={true}
              onClick={() => scrollToAuth(false)}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-xs font-semibold text-white shadow-lg shadow-violet-600/20 transition-all cursor-pointer flex items-center gap-1.5"
            >
              Get Started <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 pt-12 pb-24 space-y-28">
        
        {/* 1. HERO SECTION (Overview) */}
        <section id="overview" className="text-center space-y-8 pt-8 max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-violet-500/30 bg-violet-500/10 text-xs font-semibold text-violet-300 backdrop-blur-md animate-pulse">
            <Sparkles size={14} /> Schema-Aware Autonomous SQL Intelligence
          </div>

          <h1 className="text-5xl md:text-6xl lg:text-7xl font-black tracking-tight leading-none bg-gradient-to-b from-white via-zinc-100 to-zinc-400 bg-clip-text text-transparent">
            Transform Natural Language into Validated SQL.
          </h1>

          <p className="text-lg md:text-xl text-zinc-400 max-w-2xl mx-auto leading-relaxed font-normal">
            InsightForge AI orchestrates multi-agent LangGraph pipelines to explore database schemas, index semantic embeddings, auto-optimize query performance, and self-heal SQL bugs with zero-trust execution.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
            <button suppressHydrationWarning={true}
              onClick={() => scrollToAuth(false)}
              className="w-full sm:w-auto px-8 py-4 rounded-xl bg-gradient-to-r from-violet-600 via-indigo-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-base font-bold text-white shadow-xl shadow-violet-500/25 transition-all cursor-pointer flex items-center justify-center gap-2 transform hover:-translate-y-0.5"
            >
              Launch Workspace <ArrowRight size={18} />
            </button>
            <a
              href="#features"
              onClick={(e) => { e.preventDefault(); document.getElementById("features")?.scrollIntoView({ behavior: "smooth" }); }}
              className="w-full sm:w-auto px-8 py-4 rounded-xl bg-zinc-900 hover:bg-zinc-800/80 border border-zinc-800 text-base font-semibold text-zinc-300 hover:text-white transition-all text-center"
            >
              Explore Capabilities
            </a>
          </div>

          {/* Quick Stats / Highlights */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-12 border-t border-zinc-900">
            <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
              <div className="text-2xl font-bold text-violet-400">LangGraph</div>
              <div className="text-xs text-zinc-500 mt-1">Multi-Agent AI Pipeline</div>
            </div>
            <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
              <div className="text-2xl font-bold text-indigo-400">pgvector</div>
              <div className="text-xs text-zinc-500 mt-1">Semantic Schema Indexing</div>
            </div>
            <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
              <div className="text-2xl font-bold text-emerald-400">3+ Engines</div>
              <div className="text-xs text-zinc-500 mt-1">Postgres, MySQL, SQLite</div>
            </div>
            <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
              <div className="text-2xl font-bold text-amber-400">SELECT-Only</div>
              <div className="text-xs text-zinc-500 mt-1">Zero-Trust Security Gate</div>
            </div>
          </div>
        </section>

        {/* 2. PROJECT FEATURES SHOWCASE */}
        <section id="features" className="space-y-12">
          <div className="text-center space-y-4 max-w-3xl mx-auto">
            <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight">
              Everything Built Into InsightForge AI
            </h2>
            <p className="text-sm md:text-base text-zinc-400">
              Designed from the ground up for modern data engineers, analysts, and developers. Every feature operates smoothly across all your connected databases.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            
            {/* Feature Card 1 */}
            <div className="group p-6 rounded-2xl bg-gradient-to-b from-zinc-900/80 to-zinc-950 border border-zinc-800 hover:border-violet-500/50 transition-all hover:shadow-xl hover:shadow-violet-500/5 space-y-4">
              <div className="h-12 w-12 rounded-xl bg-violet-600/10 border border-violet-500/20 flex items-center justify-center text-violet-400 group-hover:scale-110 transition-transform">
                <Sparkles size={24} />
              </div>
              <h3 className="text-lg font-bold text-white">Schema-Aware SQL Generation</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Translates plain English queries into precise SQL by injecting exact table definitions, column types, foreign keys, and pgvector semantic matches into the AI prompt.
              </p>
              <div className="pt-2 flex items-center gap-2 text-[11px] text-violet-400 font-mono">
                <span>/api/v1/sql/generate</span> <ArrowRight size={12} />
              </div>
            </div>

            {/* Feature Card 2 */}
            <div className="group p-6 rounded-2xl bg-gradient-to-b from-zinc-900/80 to-zinc-950 border border-zinc-800 hover:border-indigo-500/50 transition-all hover:shadow-xl hover:shadow-indigo-500/5 space-y-4">
              <div className="h-12 w-12 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 group-hover:scale-110 transition-transform">
                <Zap size={24} />
              </div>
              <h3 className="text-lg font-bold text-white">AI Query Optimizer</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Click "Optimize" on any query to receive deep performance diagnostics, covering index recommendations, and rewritten SQL with WHERE/LIMIT safeguards.
              </p>
              <div className="pt-2 flex items-center gap-2 text-[11px] text-indigo-400 font-mono">
                <span>/api/v1/sql/optimize</span> <ArrowRight size={12} />
              </div>
            </div>

            {/* Feature Card 3 */}
            <div className="group p-6 rounded-2xl bg-gradient-to-b from-zinc-900/80 to-zinc-950 border border-zinc-800 hover:border-emerald-500/50 transition-all hover:shadow-xl hover:shadow-emerald-500/5 space-y-4">
              <div className="h-12 w-12 rounded-xl bg-emerald-600/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 group-hover:scale-110 transition-transform">
                <RefreshCw size={24} />
              </div>
              <h3 className="text-lg font-bold text-white">Self-Healing Auto Debug Engine</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Encountered a syntax error or typo in a column name? Click "Auto Fix" and our dedicated debug node analyzes database errors and corrects the SQL editor automatically.
              </p>
              <div className="pt-2 flex items-center gap-2 text-[11px] text-emerald-400 font-mono">
                <span>/api/v1/sql/debug</span> <ArrowRight size={12} />
              </div>
            </div>

            {/* Feature Card 4 */}
            <div className="group p-6 rounded-2xl bg-gradient-to-b from-zinc-900/80 to-zinc-950 border border-zinc-800 hover:border-purple-500/50 transition-all hover:shadow-xl hover:shadow-purple-500/5 space-y-4">
              <div className="h-12 w-12 rounded-xl bg-purple-600/10 border border-purple-500/20 flex items-center justify-center text-purple-400 group-hover:scale-110 transition-transform">
                <GitFork size={24} />
              </div>
              <h3 className="text-lg font-bold text-white">Visual Schema & Relations</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Navigate live metadata with collapsible tables, column type badges, primary key (PK) / foreign key (FK) highlights, and interactive ER relationship views.
              </p>
              <div className="pt-2 flex items-center gap-2 text-[11px] text-purple-400 font-mono">
                <span>Schema Explorer</span> <ArrowRight size={12} />
              </div>
            </div>

            {/* Feature Card 5 */}
            <div className="group p-6 rounded-2xl bg-gradient-to-b from-zinc-900/80 to-zinc-950 border border-zinc-800 hover:border-amber-500/50 transition-all hover:shadow-xl hover:shadow-amber-500/5 space-y-4">
              <div className="h-12 w-12 rounded-xl bg-amber-600/10 border border-amber-500/20 flex items-center justify-center text-amber-400 group-hover:scale-110 transition-transform">
                <Database size={24} />
              </div>
              <h3 className="text-lg font-bold text-white">Connect Custom Databases</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Connect external PostgreSQL instances, MySQL servers, or local SQLite database files (`.db`) right from the top navigation dropdown with zero hassle.
              </p>
              <div className="pt-2 flex items-center gap-2 text-[11px] text-amber-400 font-mono">
                <span>Multi-Engine Support</span> <ArrowRight size={12} />
              </div>
            </div>

            {/* Feature Card 6 */}
            <div className="group p-6 rounded-2xl bg-gradient-to-b from-zinc-900/80 to-zinc-950 border border-zinc-800 hover:border-rose-500/50 transition-all hover:shadow-xl hover:shadow-rose-500/5 space-y-4">
              <div className="h-12 w-12 rounded-xl bg-rose-600/10 border border-rose-500/20 flex items-center justify-center text-rose-400 group-hover:scale-110 transition-transform">
                <BookOpen size={24} />
              </div>
              <h3 className="text-lg font-bold text-white">Interactive Teaching Mode</h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Toggle "Teaching Mode" to get clear pedagogical explanations of SQL concepts, JOIN mechanics, subqueries, and aggregation rules alongside every result.
              </p>
              <div className="pt-2 flex items-center gap-2 text-[11px] text-rose-400 font-mono">
                <span>Pedagogical Assistant</span> <ArrowRight size={12} />
              </div>
            </div>

          </div>
        </section>

        {/* 3. ARCHITECTURE & SECURITY HIGHLIGHTS */}
        <section id="architecture" className="p-8 md:p-12 rounded-3xl bg-gradient-to-r from-zinc-900/90 via-zinc-900/60 to-zinc-950 border border-zinc-800 space-y-8">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="space-y-2 max-w-2xl">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded bg-violet-500/10 border border-violet-500/20 text-xs font-semibold text-violet-400">
                <ShieldCheck size={14} /> Architecture & Security
              </div>
              <h3 className="text-2xl md:text-3xl font-extrabold text-white">
                Enterprise-Grade Defense & Pipeline
              </h3>
              <p className="text-xs md:text-sm text-zinc-400">
                Built to protect production data while unleashing AI productivity. Every query undergoes strict pre-execution validation before touching your database.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4 border-t border-zinc-800/80">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-bold text-white">
                <CheckCircle2 size={16} className="text-emerald-400" /> SELECT-Only Security Gate
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                All AI and user-submitted SQL is parsed by `is_safe_select_query`. INSERT, UPDATE, DELETE, DROP, and multi-statement attacks are automatically rejected at the API edge.
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-bold text-white">
                <CheckCircle2 size={16} className="text-violet-400" /> LangGraph Workflow Orchestration
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Stateful graphs route queries between Generation, Optimization, and Debugging nodes, ensuring high accuracy and context preservation.
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-bold text-white">
                <CheckCircle2 size={16} className="text-indigo-400" /> Real-Time Schema Discovery
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Background worker (`discover_and_index_background`) indexes table catalogs and builds semantic vector embeddings in pgvector within milliseconds of connecting.
              </p>
            </div>
          </div>
        </section>

        {/* 4. AUTHENTICATION SECTION */}
        <section id="auth-section" className="pt-12 scroll-mt-24">
          <div className="max-w-md mx-auto relative">
            
            {/* Glow ring around auth card */}
            <div className="absolute -inset-1 rounded-2xl bg-gradient-to-r from-violet-600 to-indigo-600 opacity-30 blur-lg pointer-events-none" />

            <div className="relative rounded-2xl bg-zinc-900/90 border border-zinc-800 p-8 shadow-2xl space-y-6">
              
              <div className="text-center space-y-2">
                <div className="inline-flex items-center justify-center h-12 w-12 rounded-full bg-violet-600/20 text-violet-400 mb-2">
                  {isLogin ? <LogIn size={24} /> : <UserPlus size={24} />}
                </div>
                <h3 className="text-2xl font-bold text-white">
                  {isLogin ? "Access Workspace" : "Create Account"}
                </h3>
                <p className="text-xs text-zinc-400">
                  {isLogin
                    ? "Log in to access your registered databases & history"
                    : "Register to unlock autonomous SQL intelligence"}
                </p>
              </div>

              {/* Mode switch tabs */}
              <div className="grid grid-cols-2 p-1 rounded-lg bg-zinc-950 border border-zinc-800 text-xs font-semibold">
                <button suppressHydrationWarning={true}
                  type="button"
                  onClick={() => { setIsLogin(true); setError(""); }}
                  className={`py-2 rounded-md transition-all cursor-pointer text-center ${
                    isLogin ? "bg-violet-600 text-white shadow" : "text-zinc-400 hover:text-white"
                  }`}
                >
                  Sign In
                </button>
                <button suppressHydrationWarning={true}
                  type="button"
                  onClick={() => { setIsLogin(false); setError(""); }}
                  className={`py-2 rounded-md transition-all cursor-pointer text-center ${
                    !isLogin ? "bg-violet-600 text-white shadow" : "text-zinc-400 hover:text-white"
                  }`}
                >
                  Register
                </button>
              </div>

              {error && (
                <div className={`p-3 rounded-lg text-xs border ${
                  error.includes("registered")
                    ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                    : "bg-red-500/10 border-red-500/20 text-red-400"
                }`}>
                  {error}
                </div>
              )}

              <form suppressHydrationWarning={true} onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-zinc-300 mb-1.5">Email address</label>
                  <div className="relative">
                    <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-zinc-500">
                      <Mail size={16} />
                    </span>
                    <input suppressHydrationWarning={true}
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      className="w-full rounded-lg border border-zinc-800 bg-zinc-950/90 py-2.5 pl-10 pr-4 text-sm text-white placeholder-zinc-500 outline-none transition-all focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
                      placeholder="developer@company.com"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-medium text-zinc-300">Password</label>
                  </div>
                  <div className="relative">
                    <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-zinc-500">
                      <Lock size={16} />
                    </span>
                    <input suppressHydrationWarning={true}
                      type="password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="w-full rounded-lg border border-zinc-800 bg-zinc-950/90 py-2.5 pl-10 pr-4 text-sm text-white placeholder-zinc-500 outline-none transition-all focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
                      placeholder="••••••••"
                    />
                  </div>
                </div>

                <button suppressHydrationWarning={true}
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 rounded-lg bg-gradient-to-r from-violet-600 via-indigo-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 font-bold text-sm text-white shadow-lg shadow-violet-500/25 transition-all cursor-pointer flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {loading ? "Authenticating..." : isLogin ? "Continue to Workspace" : "Create Account & Enter Workspace"}
                  {!loading && <ArrowRight size={16} />}
                </button>
              </form>

              <div className="pt-2 border-t border-zinc-800/80 text-center">
                <span className="text-[11px] text-zinc-500">
                  After authentication, you will be directed straight to the Main Workspace.
                </span>
              </div>

            </div>
          </div>
        </section>

      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-900 bg-zinc-950/90 py-8 px-6 text-center text-xs text-zinc-500">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="h-6 w-6 rounded bg-violet-600 flex items-center justify-center font-bold text-[10px] text-white">IF</div>
            <span className="font-bold text-zinc-400">InsightForge AI</span>
          </div>
          <div className="flex items-center gap-6">
            <span className="flex items-center gap-1"><Server size={12} className="text-violet-400" /> FastAPI Backend</span>
            <span className="flex items-center gap-1"><Code2 size={12} className="text-indigo-400" /> Next.js 16</span>
            <span className="flex items-center gap-1"><Lock size={12} className="text-emerald-400" /> Zero-Trust Gate</span>
          </div>
          <div>© <span suppressHydrationWarning={true}>{new Date().getFullYear()}</span> InsightForge AI. All rights reserved.</div>
        </div>
      </footer>
    </div>
  );
}
