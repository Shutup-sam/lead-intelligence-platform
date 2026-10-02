"use client";

import React, { useState } from "react";
import { AuditLogItem, EmbeddingMetadata } from "@/lib/api";

interface AuditDetailsProps {
  auditLogs: AuditLogItem[];
  embedding?: EmbeddingMetadata | null;
}

export function AuditDetails({ auditLogs, embedding }: AuditDetailsProps) {
  const [isOpen, setIsOpen] = useState(false);

  const latestAudit = auditLogs && auditLogs.length > 0 ? auditLogs[0] : null;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-md">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-5 py-3.5 flex items-center justify-between text-left hover:bg-slate-800/40 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-cyan-400" />
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            AI Engineering Telemetry &amp; Vector Metadata
          </span>
          {latestAudit && (
            <span className="text-xs text-slate-500 font-mono">
              ({latestAudit.provider} · {latestAudit.model})
            </span>
          )}
        </div>
        <span className="text-xs text-slate-400 font-medium">
          {isOpen ? "Hide Telemetry ↑" : "View Telemetry & Audit Logs ↓"}
        </span>
      </button>

      {isOpen && (
        <div className="p-5 border-t border-slate-800/80 space-y-5 bg-slate-950/60 text-xs">
          {/* Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
              <span className="text-slate-500 block">LLM Provider</span>
              <span className="font-semibold text-slate-200 uppercase">{latestAudit?.provider || "N/A"}</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
              <span className="text-slate-500 block">LLM Model</span>
              <span className="font-mono text-slate-200">{latestAudit?.model || "N/A"}</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
              <span className="text-slate-500 block">Total Tokens</span>
              <span className="font-mono font-bold text-cyan-400">
                {latestAudit ? `${latestAudit.total_tokens.toLocaleString()} (${latestAudit.input_tokens} in / ${latestAudit.output_tokens} out)` : "N/A"}
              </span>
            </div>
            <div className="p-3 rounded-lg bg-slate-900/80 border border-slate-800">
              <span className="text-slate-500 block">Inference Latency</span>
              <span className="font-mono font-bold text-emerald-400">
                {latestAudit ? `${latestAudit.latency_ms.toFixed(1)} ms` : "N/A"}
              </span>
            </div>
          </div>

          {/* pgvector Embeddings Metadata */}
          {embedding && (
            <div className="p-4 rounded-lg bg-slate-900/70 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-300">pgvector Embedding Representation</span>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                  {embedding.dimension} dimensions · HNSW Indexed
                </span>
              </div>
              <div className="text-[11px] text-slate-400 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">SHA-256 Idempotency Hash:</span>
                  <span className="font-mono text-slate-300">{embedding.content_hash}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">Vector Storage:</span>
                  <span className="text-slate-300">PostgreSQL pgvector (raw vector hidden for performance)</span>
                </div>
              </div>
            </div>
          )}

          {/* Historical Logs if multiple */}
          {auditLogs && auditLogs.length > 1 && (
            <div className="space-y-2">
              <span className="text-slate-400 font-semibold block">Execution History:</span>
              <div className="space-y-1">
                {auditLogs.map((log, idx) => (
                  <div key={idx} className="flex items-center justify-between py-1 text-[11px] text-slate-400 border-b border-slate-800/40">
                    <span>{log.created_at}</span>
                    <span className="font-mono">{log.model}</span>
                    <span>{log.total_tokens} tokens</span>
                    <span>{log.latency_ms} ms</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
