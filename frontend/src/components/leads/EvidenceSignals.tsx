"use client";

import React from "react";
import { SignalItem } from "@/lib/api";

interface EvidenceSignalsProps {
  signals: SignalItem[];
  reasoning?: string;
}

export function EvidenceSignals({ signals, reasoning }: EvidenceSignalsProps) {
  const positiveSignals = signals.filter((s) => s.sentiment.toLowerCase() === "positive");
  const negativeSignals = signals.filter((s) => s.sentiment.toLowerCase() === "negative");
  const neutralSignals = signals.filter(
    (s) => s.sentiment.toLowerCase() !== "positive" && s.sentiment.toLowerCase() !== "negative"
  );

  return (
    <div className="space-y-6">
      {/* Qualification Reasoning Card */}
      {reasoning && (
        <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 shadow-md space-y-2">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-400">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            AI Qualification Reasoning
          </div>
          <p className="text-sm text-slate-300 leading-relaxed font-normal">{reasoning}</p>
        </div>
      )}

      {/* Signals Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Positive Signals */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-400">
            <span className="flex items-center justify-center w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-400 text-xs">
              ✓
            </span>
            Positive Evidence Signals ({positiveSignals.length})
          </div>

          {positiveSignals.length === 0 ? (
            <div className="p-4 rounded-lg bg-slate-900/40 border border-slate-800/80 text-xs text-slate-500 italic">
              No positive signals recorded for this evaluation.
            </div>
          ) : (
            positiveSignals.map((item) => (
              <div
                key={item.id}
                className="p-4 rounded-xl bg-slate-900/60 border border-emerald-500/20 shadow-sm space-y-2.5 transition-colors hover:border-emerald-500/40"
              >
                <div className="flex items-start gap-2">
                  <span className="text-emerald-400 font-bold text-sm">✓</span>
                  <span className="text-sm font-semibold text-slate-100">{item.signal}</span>
                </div>
                <blockquote className="border-l-2 border-emerald-500/40 pl-3 text-xs text-slate-300 italic leading-relaxed">
                  &ldquo;{item.evidence}&rdquo;
                </blockquote>
                {item.source_url && (
                  <div className="pt-1 text-[11px] text-slate-400 flex items-center gap-1.5">
                    <span className="text-slate-500">Source:</span>
                    <a
                      href={item.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-400 hover:text-emerald-300 underline underline-offset-2 truncate max-w-xs transition-colors"
                      title={item.source_url}
                    >
                      {item.source_url.replace(/^https?:\/\//, "")} ↗
                    </a>
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Negative Signals */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-rose-400">
            <span className="flex items-center justify-center w-4 h-4 rounded-full bg-rose-500/20 text-rose-400 text-xs">
              ⚠
            </span>
            Negative / Disqualifying Signals ({negativeSignals.length})
          </div>

          {negativeSignals.length === 0 ? (
            <div className="p-4 rounded-lg bg-slate-900/40 border border-slate-800/80 text-xs text-slate-500 italic">
              No disqualifying signals found. Full alignment with positive ICP criteria.
            </div>
          ) : (
            negativeSignals.map((item) => (
              <div
                key={item.id}
                className="p-4 rounded-xl bg-slate-900/60 border border-rose-500/20 shadow-sm space-y-2.5 transition-colors hover:border-rose-500/40"
              >
                <div className="flex items-start gap-2">
                  <span className="text-rose-400 font-bold text-sm">⚠</span>
                  <span className="text-sm font-semibold text-slate-100">{item.signal}</span>
                </div>
                <blockquote className="border-l-2 border-rose-500/40 pl-3 text-xs text-slate-300 italic leading-relaxed">
                  &ldquo;{item.evidence}&rdquo;
                </blockquote>
                {item.source_url && (
                  <div className="pt-1 text-[11px] text-slate-400 flex items-center gap-1.5">
                    <span className="text-slate-500">Source:</span>
                    <a
                      href={item.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-rose-400 hover:text-rose-300 underline underline-offset-2 truncate max-w-xs transition-colors"
                      title={item.source_url}
                    >
                      {item.source_url.replace(/^https?:\/\//, "")} ↗
                    </a>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
