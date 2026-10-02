"use client";

import React from "react";
import { SourcePageItem } from "@/lib/api";

interface SourcePagesProps {
  pages: SourcePageItem[];
}

export function SourcePages({ pages }: SourcePagesProps) {
  if (!pages || pages.length === 0) {
    return (
      <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 text-center text-sm text-slate-400">
        No crawled source pages found for this lead.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/80 overflow-hidden shadow-lg">
      <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">Crawled Source Pages ({pages.length})</h3>
          <p className="text-xs text-slate-400">
            Original web pages fetched via Scrapling that provided factual context to the qualification pipeline.
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/70 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-800">
            <tr>
              <th className="px-5 py-3 font-medium">Page Title &amp; Target URL</th>
              <th className="px-4 py-3 font-medium text-center">Depth</th>
              <th className="px-4 py-3 font-medium text-center">Status</th>
              <th className="px-4 py-3 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {pages.map((p) => (
              <tr key={p.id} className="hover:bg-slate-800/40 transition-colors">
                <td className="px-5 py-3.5 space-y-0.5">
                  <div className="font-medium text-slate-100 truncate max-w-md">
                    {p.title || "Untitled Page"}
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono truncate max-w-md">{p.url}</div>
                </td>
                <td className="px-4 py-3.5 text-center font-mono text-slate-400">
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-[11px]">D{p.depth}</span>
                </td>
                <td className="px-4 py-3.5 text-center">
                  <span
                    className={`inline-flex px-2 py-0.5 rounded text-[11px] font-mono font-medium ${
                      p.status_code === 200
                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                        : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                    }`}
                  >
                    {p.status_code}
                  </span>
                </td>
                <td className="px-4 py-3.5 text-right">
                  <a
                    href={p.final_url || p.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs transition-colors"
                  >
                    Open Page
                    <svg className="w-3 h-3 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                      />
                    </svg>
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
