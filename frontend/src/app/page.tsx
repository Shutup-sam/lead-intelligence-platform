"use client";

import { useEffect, useState } from "react";

interface ServiceHealth {
  status: string;
  latency_ms?: number;
  pgvector_ready?: boolean;
  ping?: boolean;
  error?: string;
}

interface HealthData {
  status: string;
  environment: string;
  timestamp: string;
  services: {
    database: ServiceHealth;
    redis: ServiceHealth;
  };
}

export default function Home() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/health`, { cache: "no-store" });
      if (!res.ok && res.status !== 503) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data: HealthData = await res.json();
      setHealth(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to connect to backend";
      setError(msg);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500 selection:text-white">
      {/* Top Navigation */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-indigo-500 to-cyan-400 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/20">
              AI
            </div>
            <div>
              <span className="font-semibold text-white tracking-tight">AI Lead Intelligence</span>
              <span className="ml-2 text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Milestone 1: Foundation
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <a
              href={`${apiBase}/api/v1/docs`}
              target="_blank"
              rel="noreferrer"
              className="text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-md hover:bg-slate-800"
            >
              API Docs ↗
            </a>
            <a
              href={`${apiBase}/health`}
              target="_blank"
              rel="noreferrer"
              className="text-slate-400 hover:text-white transition-colors px-3 py-1.5 rounded-md hover:bg-slate-800"
            >
              Health Check ↗
            </a>
          </div>
        </div>
      </header>

      {/* Hero & Status */}
      <main className="max-w-6xl mx-auto px-6 py-12 space-y-12">
        <section className="space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            Next.js App Router Running Successfully
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white">
            Lead Intelligence Platform
          </h1>
          <p className="text-lg text-slate-400 max-w-2xl">
            Autonomous discovery, Scrapling-powered ethical web extraction, and LLM-driven ICP qualification with PostgreSQL &amp; pgvector.
          </p>
        </section>

        {/* Live System Diagnostics Card */}
        <section className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-xl space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div>
              <h2 className="text-lg font-semibold text-white">Live System Diagnostics</h2>
              <p className="text-sm text-slate-400">Real-time status of backend services and databases</p>
            </div>
            <button
              onClick={fetchHealth}
              disabled={loading}
              className="self-start sm:self-auto px-4 py-2 text-xs font-medium rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-all disabled:opacity-50"
            >
              {loading ? "Checking..." : "Refresh Status"}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* FastAPI Service */}
            <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800 space-y-2">
              <div className="text-xs uppercase tracking-wider text-slate-500 font-semibold">FastAPI Gateway</div>
              <div className="flex items-center gap-2">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    health ? "bg-emerald-400" : error ? "bg-rose-500" : "bg-amber-400 animate-pulse"
                  }`}
                />
                <span className="font-semibold text-white">
                  {health ? "Online" : error ? "Offline" : "Connecting..."}
                </span>
              </div>
              <p className="text-xs text-slate-400">
                {health ? `Environment: ${health.environment}` : error || "Waiting for response..."}
              </p>
            </div>

            {/* PostgreSQL + pgvector */}
            <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800 space-y-2">
              <div className="text-xs uppercase tracking-wider text-slate-500 font-semibold">PostgreSQL 16 + pgvector</div>
              <div className="flex items-center gap-2">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    health?.services.database.status === "connected"
                      ? "bg-emerald-400"
                      : "bg-slate-600"
                  }`}
                />
                <span className="font-semibold text-white">
                  {health?.services.database.status === "connected" ? "Connected" : "Disconnected"}
                </span>
              </div>
              <p className="text-xs text-slate-400">
                {health?.services.database.latency_ms
                  ? `Latency: ${health.services.database.latency_ms}ms · pgvector: ${
                      health.services.database.pgvector_ready ? "Ready" : "Disabled"
                    }`
                  : "Awaiting backend..."}
              </p>
            </div>

            {/* Redis 7 */}
            <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800 space-y-2">
              <div className="text-xs uppercase tracking-wider text-slate-500 font-semibold">Redis 7 Broker</div>
              <div className="flex items-center gap-2">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    health?.services.redis.status === "connected"
                      ? "bg-emerald-400"
                      : "bg-slate-600"
                  }`}
                />
                <span className="font-semibold text-white">
                  {health?.services.redis.status === "connected" ? "Connected" : "Disconnected"}
                </span>
              </div>
              <p className="text-xs text-slate-400">
                {health?.services.redis.latency_ms
                  ? `Latency: ${health.services.redis.latency_ms}ms · PING: OK`
                  : "Awaiting backend..."}
              </p>
            </div>
          </div>
        </section>

        {/* Architecture Grid */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-white">Architecture Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-5 rounded-xl bg-slate-900/50 border border-slate-800 space-y-2">
              <div className="text-indigo-400 text-sm font-semibold">1. Next.js 15 App Router</div>
              <p className="text-xs text-slate-400">
                Server Components, streaming updates, and client-side data filtering with TanStack Table.
              </p>
            </div>
            <div className="p-5 rounded-xl bg-slate-900/50 border border-slate-800 space-y-2">
              <div className="text-cyan-400 text-sm font-semibold">2. FastAPI Gateway</div>
              <p className="text-xs text-slate-400">
                Async request handling, SSRF defense, JWT security, and task scheduling via Redis.
              </p>
            </div>
            <div className="p-5 rounded-xl bg-slate-900/50 border border-slate-800 space-y-2">
              <div className="text-amber-400 text-sm font-semibold">3. Scrapling Engine</div>
              <p className="text-xs text-slate-400">
                Anti-bot bypassing (Cloudflare Turnstile), robots.txt courtesy, and prompt-injection-safe Markdown extraction.
              </p>
            </div>
            <div className="p-5 rounded-xl bg-slate-900/50 border border-slate-800 space-y-2">
              <div className="text-emerald-400 text-sm font-semibold">4. PostgreSQL + pgvector</div>
              <p className="text-xs text-slate-400">
                Relational multi-tenant lead database combined with 1536-dim HNSW embeddings for lookalike search.
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
