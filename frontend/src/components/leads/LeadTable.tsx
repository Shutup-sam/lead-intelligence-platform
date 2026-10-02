"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LeadListItem } from "@/lib/api";
import { LeadScore } from "./LeadScore";
import { LeadStatusBadge } from "./LeadStatusBadge";

interface LeadTableProps {
  leads: LeadListItem[];
  total: number;
  page: number;
  pageSize: number;
  pages: number;
  isLoading: boolean;
  error?: string | null;
  sortBy: string;
  sortOrder: string;
  onSortChange: (column: string) => void;
  onPageChange: (newPage: number) => void;
  onStatusUpdated?: (leadId: string, newStatus: string) => void;
  onRetry?: () => void;
  hasSemanticQuery?: boolean;
}

export function LeadTable({
  leads,
  total,
  page,
  pageSize,
  pages,
  isLoading,
  error,
  sortBy,
  sortOrder,
  onSortChange,
  onPageChange,
  onStatusUpdated,
  onRetry,
  hasSemanticQuery = false,
}: LeadTableProps) {
  const router = useRouter();

  // Skeleton Loader
  if (isLoading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-xl p-6 space-y-4">
        <div className="h-6 bg-slate-800/60 rounded w-1/4 animate-pulse" />
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-14 bg-slate-800/40 rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  // Error State
  if (error) {
    return (
      <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-8 text-center space-y-3 shadow-lg">
        <div className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-rose-500/20 text-rose-400">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h3 className="text-sm font-semibold text-rose-300">Failed to load lead intelligence</h3>
        <p className="text-xs text-rose-400/80 max-w-md mx-auto">{error}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold transition-colors"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  // Empty State
  if (leads.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-12 text-center space-y-3 shadow-lg">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-slate-800 text-slate-400">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
        </div>
        <h3 className="text-base font-semibold text-slate-200">No leads match your criteria</h3>
        <p className="text-xs text-slate-400 max-w-sm mx-auto">
          Try lowering the minimum ICP score threshold, clearing industry filters, or adjusting your search keywords.
        </p>
      </div>
    );
  }

  const renderSortIcon = (col: string) => {
    if (sortBy !== col) {
      return (
        <span className="opacity-0 group-hover:opacity-40 ml-1 transition-opacity">↕</span>
      );
    }
    return <span className="ml-1 text-indigo-400">{sortOrder === "asc" ? "↑" : "↓"}</span>;
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/80 overflow-hidden shadow-xl">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-wider text-[11px] border-b border-slate-800 select-none">
            <tr>
              <th
                onClick={() => onSortChange("company_name")}
                className="px-5 py-3.5 font-medium cursor-pointer group hover:text-slate-200 transition-colors"
              >
                <div className="flex items-center">
                  Company {renderSortIcon("company_name")}
                </div>
              </th>
              <th className="px-4 py-3.5 font-medium">Industry</th>
              <th
                onClick={() => onSortChange("icp_score")}
                className="px-4 py-3.5 font-medium cursor-pointer group hover:text-slate-200 transition-colors text-center"
              >
                <div className="flex items-center justify-center">
                  ICP Score {renderSortIcon("icp_score")}
                </div>
              </th>
              <th className="px-4 py-3.5 font-medium text-center">Confidence</th>
              {hasSemanticQuery && (
                <th className="px-4 py-3.5 font-medium text-center text-cyan-400">
                  Semantic Relevance
                </th>
              )}
              <th className="px-4 py-3.5 font-medium">Geography &amp; Size</th>
              <th className="px-4 py-3.5 font-medium">Status</th>
              <th
                onClick={() => onSortChange("created_at")}
                className="px-5 py-3.5 font-medium text-right cursor-pointer group hover:text-slate-200 transition-colors"
              >
                <div className="flex items-center justify-end">
                  Qualified {renderSortIcon("created_at")}
                </div>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {leads.map((lead) => {
              const isDemo = lead.company_name.startsWith("[Demo]");
              const displayName = lead.company_name.replace(/^\[Demo\]\s*/, "");

              return (
                <tr
                  key={lead.lead_id}
                  onClick={() => router.push(`/leads/${lead.lead_id}`)}
                  className="hover:bg-slate-800/50 cursor-pointer transition-colors group"
                >
                  {/* Company & Domain */}
                  <td className="px-5 py-4 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-100 group-hover:text-indigo-300 transition-colors text-sm">
                        {displayName}
                      </span>
                      {isDemo && (
                        <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/40">
                          Demo
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono flex items-center gap-1.5">
                      <span>{lead.domain}</span>
                    </div>
                    <div className="text-xs text-slate-400 line-clamp-1 max-w-sm">
                      {lead.value_proposition || lead.company_summary}
                    </div>
                  </td>

                  {/* Industry */}
                  <td className="px-4 py-4">
                    <span className="px-2.5 py-1 rounded-md bg-slate-800/80 text-slate-200 font-medium text-xs border border-slate-700/60">
                      {lead.industry}
                    </span>
                  </td>

                  {/* ICP Score */}
                  <td className="px-4 py-4 text-center">
                    <LeadScore score={lead.icp_score} />
                  </td>

                  {/* Confidence */}
                  <td className="px-4 py-4 text-center font-mono text-slate-300">
                    {Math.round(lead.confidence_score * 100)}%
                  </td>

                  {/* Semantic Relevance if query active */}
                  {hasSemanticQuery && (
                    <td className="px-4 py-4 text-center">
                      {lead.similarity !== null && lead.similarity !== undefined ? (
                        <span className="px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/25 font-mono text-[11px]">
                          {Math.round(lead.similarity * 100)}% match
                        </span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                  )}

                  {/* Geography & Company Size */}
                  <td className="px-4 py-4 text-slate-300 space-y-0.5">
                    <div>{lead.geography}</div>
                    <div className="text-[11px] text-slate-500">{lead.estimated_company_size} employees</div>
                  </td>

                  {/* Status Badge (interactive dropdown) */}
                  <td className="px-4 py-4">
                    <LeadStatusBadge
                      leadId={lead.lead_id}
                      initialStatus={lead.status}
                      editable={true}
                      onStatusUpdated={(newStatus) => {
                        if (onStatusUpdated) onStatusUpdated(lead.lead_id, newStatus);
                      }}
                    />
                  </td>

                  {/* Created At / Dossier Action */}
                  <td className="px-5 py-4 text-right space-y-1">
                    <div className="text-[11px] text-slate-400">
                      {new Date(lead.created_at).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                      })}
                    </div>
                    <span className="text-[11px] text-indigo-400 group-hover:text-indigo-300 font-medium inline-flex items-center gap-0.5">
                      Dossier →
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      <div className="px-5 py-3.5 bg-slate-950/70 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
        <div>
          Showing <span className="font-semibold text-slate-200">{leads.length}</span> of{" "}
          <span className="font-semibold text-slate-200">{total}</span> qualified leads
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-40 disabled:hover:bg-slate-800 transition-colors"
          >
            ← Previous
          </button>
          <span>
            Page <span className="text-slate-200 font-semibold">{page}</span> of{" "}
            <span className="text-slate-200 font-semibold">{Math.max(1, pages)}</span>
          </span>
          <button
            type="button"
            disabled={page >= pages}
            onClick={() => onPageChange(page + 1)}
            className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-40 disabled:hover:bg-slate-800 transition-colors"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}
