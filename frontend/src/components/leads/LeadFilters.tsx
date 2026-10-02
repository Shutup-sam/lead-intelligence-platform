"use client";

import React from "react";
import { FilterParams, getExportUrl } from "@/lib/api";

interface LeadFiltersProps {
  filters: FilterParams;
  onFilterChange: (newFilters: Partial<FilterParams>) => void;
  onReset: () => void;
  onOpenCrawlModal: () => void;
  onSeedDemo: () => void;
  isSeeding?: boolean;
}

export function LeadFilters({
  filters,
  onFilterChange,
  onReset,
  onOpenCrawlModal,
  onSeedDemo,
  isSeeding = false,
}: LeadFiltersProps) {
  const hasActiveFilters = Boolean(
    filters.min_icp_score !== undefined ||
      filters.industry ||
      filters.geography ||
      filters.status ||
      filters.search
  );

  return (
    <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3 shadow-md">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Dropdown Filters */}
        <div className="flex flex-wrap items-center gap-2.5 text-xs">
          {/* Minimum ICP Score */}
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 font-medium">ICP Fit:</span>
            <select
              value={filters.min_icp_score !== undefined ? filters.min_icp_score.toString() : ""}
              onChange={(e) =>
                onFilterChange({
                  min_icp_score: e.target.value ? Number(e.target.value) : undefined,
                  page: 1,
                })
              }
              className="bg-slate-950 border border-slate-800 text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
            >
              <option value="">All Scores (0–100)</option>
              <option value="80">High Fit (≥ 80)</option>
              <option value="70">Moderate+ (≥ 70)</option>
              <option value="50">Qualified (≥ 50)</option>
            </select>
          </div>

          {/* Industry */}
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 font-medium">Industry:</span>
            <select
              value={filters.industry || ""}
              onChange={(e) =>
                onFilterChange({
                  industry: e.target.value || undefined,
                  page: 1,
                })
              }
              className="bg-slate-950 border border-slate-800 text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
            >
              <option value="">All Industries</option>
              <option value="SaaS">SaaS</option>
              <option value="FinTech">FinTech</option>
              <option value="Cybersecurity">Cybersecurity</option>
              <option value="Logistics">Logistics</option>
              <option value="HR Tech">HR Tech</option>
              <option value="eCommerce">eCommerce</option>
            </select>
          </div>

          {/* Geography */}
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 font-medium">Geography:</span>
            <select
              value={filters.geography || ""}
              onChange={(e) =>
                onFilterChange({
                  geography: e.target.value || undefined,
                  page: 1,
                })
              }
              className="bg-slate-950 border border-slate-800 text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
            >
              <option value="">All Geographies</option>
              <option value="United States">United States</option>
              <option value="United Kingdom">United Kingdom</option>
              <option value="Germany">Germany</option>
              <option value="Canada">Canada</option>
            </select>
          </div>

          {/* Status */}
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 font-medium">Status:</span>
            <select
              value={filters.status || ""}
              onChange={(e) =>
                onFilterChange({
                  status: e.target.value || undefined,
                  page: 1,
                })
              }
              className="bg-slate-950 border border-slate-800 text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
            >
              <option value="">All Statuses</option>
              <option value="NEW">New</option>
              <option value="REVIEW">In Review</option>
              <option value="QUALIFIED">Qualified</option>
              <option value="CONTACTED">Contacted</option>
              <option value="REJECTED">Rejected</option>
            </select>
          </div>

          {hasActiveFilters && (
            <button
              type="button"
              onClick={onReset}
              className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition-colors"
            >
              Reset Filters
            </button>
          )}
        </div>

        {/* Action Buttons: Export & Discovery */}
        <div className="flex items-center gap-2">
          {/* Export Dropdown / Links */}
          <a
            href={getExportUrl("csv", filters)}
            download="leads_export.csv"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors"
          >
            <svg className="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Export CSV
          </a>
          <a
            href={getExportUrl("json", filters)}
            download="leads_export.json"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-colors"
          >
            Export JSON
          </a>

          {/* Seed Demo Button */}
          <button
            type="button"
            onClick={onSeedDemo}
            disabled={isSeeding}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-950/60 hover:bg-cyan-900/60 text-cyan-300 border border-cyan-800/60 text-xs font-medium transition-colors disabled:opacity-50"
            title="Seed 6 realistic synthetic B2B leads for testing"
          >
            {isSeeding ? "Seeding..." : "⚡ Seed Demo Leads"}
          </button>

          {/* Crawl New Domain Button */}
          <button
            type="button"
            onClick={onOpenCrawlModal}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-sm transition-all"
          >
            + Crawl Website
          </button>
        </div>
      </div>
    </div>
  );
}
