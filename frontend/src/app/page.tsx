"use client";

import React, { useEffect, useState, useCallback, useTransition } from "react";
import {
  fetchLeads,
  semanticSearch,
  hybridSearch,
  seedDemoData,
  LeadListItem,
  FilterParams,
} from "@/lib/api";
import { LeadTable } from "@/components/leads/LeadTable";
import { LeadFilters } from "@/components/leads/LeadFilters";
import { LeadSearch } from "@/components/leads/LeadSearch";
import { CrawlModal } from "@/components/leads/CrawlModal";

export default function LeadsDashboard() {
  const [leads, setLeads] = useState<LeadListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter & Search State
  const [filters, setFilters] = useState<FilterParams>({
    page: 1,
    page_size: 25,
    sort_by: "created_at",
    sort_order: "desc",
  });

  const [searchQuery, setSearchQuery] = useState("");
  const [searchMode, setSearchMode] = useState<"keyword" | "semantic">("keyword");
  const [activeSemanticQuery, setActiveSemanticQuery] = useState<string | null>(null);

  // Seed & Crawl Modal State
  const [isSeeding, setIsSeeding] = useState(false);
  const [isCrawlModalOpen, setIsCrawlModalOpen] = useState(false);
  const [bannerMessage, setBannerMessage] = useState<string | null>(null);

  // Sync state to URL params
  const updateUrlParams = (currentFilters: FilterParams, query: string, mode: string) => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    url.searchParams.delete("search");
    url.searchParams.delete("min_icp_score");
    url.searchParams.delete("industry");
    url.searchParams.delete("geography");
    url.searchParams.delete("status");
    url.searchParams.delete("page");
    url.searchParams.delete("mode");
    url.searchParams.delete("campaign_id");

    if (query) url.searchParams.set("search", query);
    if (mode === "semantic") url.searchParams.set("mode", "semantic");
    if (currentFilters.campaign_id)
      url.searchParams.set("campaign_id", currentFilters.campaign_id);
    if (currentFilters.min_icp_score !== undefined)
      url.searchParams.set("min_icp_score", currentFilters.min_icp_score.toString());
    if (currentFilters.industry) url.searchParams.set("industry", currentFilters.industry);
    if (currentFilters.geography) url.searchParams.set("geography", currentFilters.geography);
    if (currentFilters.status) url.searchParams.set("status", currentFilters.status);
    if (currentFilters.page && currentFilters.page > 1)
      url.searchParams.set("page", currentFilters.page.toString());

    window.history.replaceState({}, "", url.toString());
  };

  const loadLeads = useCallback(async (currentFilters: FilterParams, query: string, mode: "keyword" | "semantic") => {
    setIsLoading(true);
    setError(null);

    try {
      if (mode === "semantic" && query.trim()) {
        // Execute Semantic AI Search via pgvector
        const semRes = await semanticSearch(query.trim(), currentFilters.page_size || 25);
        setActiveSemanticQuery(query.trim());
        setLeads(
          semRes.results.map((r) => ({
            lead_id: r.lead_id,
            crawl_target_id: "",
            company_name: r.company_name,
            domain: r.domain,
            industry: r.industry,
            company_summary: r.company_summary,
            value_proposition: r.company_summary,
            icp_score: r.icp_score,
            confidence_score: r.confidence_score,
            geography: r.geography,
            estimated_company_size: "N/A",
            status: r.status,
            created_at: new Date().toISOString(),
            similarity: r.similarity,
          }))
        );
        setTotal(semRes.count);
        setPages(1);
      } else {
        // Standard Relational / Keyword Filter Query
        setActiveSemanticQuery(null);
        const data = await fetchLeads({
          ...currentFilters,
          search: query.trim() || undefined,
        });
        setLeads(data.items);
        setTotal(data.total);
        setPages(data.pages);
      }
      updateUrlParams(currentFilters, query, mode);
    } catch (err: any) {
      setError(err.message || "Failed to load lead intelligence");
      setLeads([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const q = params.get("search") || "";
      const mode = (params.get("mode") as "keyword" | "semantic") || "keyword";
      const minIcp = params.get("min_icp_score") ? Number(params.get("min_icp_score")) : undefined;
      const ind = params.get("industry") || undefined;
      const geo = params.get("geography") || undefined;
      const stat = params.get("status") || undefined;
      const campId = params.get("campaign_id") || undefined;
      const pg = params.get("page") ? Number(params.get("page")) : 1;

      setSearchQuery(q);
      setSearchMode(mode);

      const initialFilters: FilterParams = {
        page: pg,
        page_size: 25,
        campaign_id: campId,
        min_icp_score: minIcp,
        industry: ind,
        geography: geo,
        status: stat,
        sort_by: "created_at",
        sort_order: "desc",
      };
      setFilters(initialFilters);
      loadLeads(initialFilters, q, mode);
    }
  }, [loadLeads]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const updated = { ...filters, page: 1 };
    setFilters(updated);
    loadLeads(updated, searchQuery, searchMode);
  };

  const handleModeToggle = (mode: "keyword" | "semantic") => {
    setSearchMode(mode);
    const updated = { ...filters, page: 1 };
    setFilters(updated);
    loadLeads(updated, searchQuery, mode);
  };

  const handleFilterChange = (newFilters: Partial<FilterParams>) => {
    const updated = { ...filters, ...newFilters };
    setFilters(updated);
    loadLeads(updated, searchQuery, searchMode);
  };

  const handleResetFilters = () => {
    const reset: FilterParams = {
      page: 1,
      page_size: 25,
      sort_by: "created_at",
      sort_order: "desc",
    };
    setSearchQuery("");
    setSearchMode("keyword");
    setFilters(reset);
    loadLeads(reset, "", "keyword");
  };

  const handleSortChange = (column: string) => {
    let order: "asc" | "desc" = "desc";
    if (filters.sort_by === column && filters.sort_order === "desc") {
      order = "asc";
    }
    const updated: FilterParams = { ...filters, sort_by: column, sort_order: order };
    setFilters(updated);
    loadLeads(updated, searchQuery, searchMode);
  };

  const handlePageChange = (newPage: number) => {
    const updated = { ...filters, page: newPage };
    setFilters(updated);
    loadLeads(updated, searchQuery, searchMode);
  };

  const handleSeedDemo = async () => {
    setIsSeeding(true);
    try {
      const res = await seedDemoData();
      setBannerMessage(`✓ ${res.message} Generated synthetic B2B company intelligence.`);
      setTimeout(() => setBannerMessage(null), 6000);
      loadLeads(filters, searchQuery, searchMode);
    } catch (err: any) {
      setError(err.message || "Failed to seed demo data");
    } finally {
      setIsSeeding(false);
    }
  };

  // KPI Calculations
  const highFitCount = leads.filter((l) => l.icp_score >= 80).length;
  const inReviewCount = leads.filter((l) => l.status === "REVIEW" || l.status === "NEW").length;
  const avgFit =
    leads.length > 0 ? Math.round(leads.reduce((acc, curr) => acc + curr.icp_score, 0) / leads.length) : 0;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans selection:bg-indigo-500 selection:text-white">
      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Title & Action Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-zinc-800/80 pb-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Lead Intelligence Engine</h1>
            <p className="text-xs text-zinc-400">
              Autonomous Scrapling crawls · LLM ICP qualification · pgvector hybrid search
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleSeedDemo}
              disabled={isSeeding}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900 text-xs font-semibold text-zinc-300 hover:text-white hover:border-zinc-700 transition-colors shadow-sm disabled:opacity-50"
            >
              {isSeeding ? "Seeding..." : "⚡ Seed Demo Leads"}
            </button>
            <button
              type="button"
              onClick={() => setIsCrawlModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 text-xs font-semibold text-white hover:bg-indigo-500 shadow-md shadow-indigo-600/30 transition-colors"
            >
              + Crawl &amp; Qualify Domain
            </button>
          </div>
        </div>

        {/* Campaign Filter Pill if active */}
        {filters.campaign_id && (
          <div className="flex items-center justify-between rounded-lg border border-indigo-500/30 bg-indigo-950/40 px-3.5 py-2 text-xs text-indigo-300">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-white">Filtering by Campaign:</span>
              <span className="font-mono text-[11px] bg-indigo-900/60 px-2 py-0.5 rounded text-indigo-200">
                {filters.campaign_id}
              </span>
            </div>
            <button
              type="button"
              onClick={() => handleFilterChange({ campaign_id: undefined })}
              className="rounded bg-indigo-900/80 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-indigo-800 transition-colors"
            >
              Clear Campaign Filter ✕
            </button>
          </div>
        )}
        {/* Banner notification */}
        {bannerMessage && (
          <div className="p-3.5 rounded-xl bg-cyan-950/60 border border-cyan-800/60 text-cyan-200 text-xs flex items-center justify-between shadow-lg animate-in fade-in">
            <span>{bannerMessage}</span>
            <button
              onClick={() => setBannerMessage(null)}
              className="text-cyan-400 hover:text-cyan-200 text-xs font-semibold ml-4"
            >
              ✕
            </button>
          </div>
        )}

        {/* Dashboard Title & Quick KPIs */}
        <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/90 shadow-sm space-y-1">
            <span className="text-xs text-slate-400 font-medium">Total Qualified Leads</span>
            <div className="text-2xl font-extrabold text-white tracking-tight">{total}</div>
            <span className="text-[11px] text-slate-500">Crawled &amp; Verified</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-emerald-500/20 shadow-sm space-y-1">
            <span className="text-xs text-emerald-400/90 font-medium">Strong ICP Match (≥ 80)</span>
            <div className="text-2xl font-extrabold text-emerald-400 tracking-tight">{highFitCount}</div>
            <span className="text-[11px] text-slate-500">Highest sales priority</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-amber-500/20 shadow-sm space-y-1">
            <span className="text-xs text-amber-400/90 font-medium">In Pipeline / Review</span>
            <div className="text-2xl font-extrabold text-amber-400 tracking-tight">{inReviewCount}</div>
            <span className="text-[11px] text-slate-500">Requires SDR evaluation</span>
          </div>

          <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/90 shadow-sm space-y-1">
            <span className="text-xs text-slate-400 font-medium">Average ICP Score</span>
            <div className="text-2xl font-extrabold text-indigo-400 tracking-tight">{avgFit} / 100</div>
            <span className="text-[11px] text-slate-500">Across current results</span>
          </div>
        </section>

        {/* Search Bar (Keyword vs Semantic) */}
        <section>
          <LeadSearch
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            searchMode={searchMode}
            onModeToggle={handleModeToggle}
            onSearchSubmit={handleSearchSubmit}
            isSearching={isLoading}
          />
        </section>

        {/* Filters Toolbar */}
        <section>
          <LeadFilters
            filters={filters}
            onFilterChange={handleFilterChange}
            onReset={handleResetFilters}
            onOpenCrawlModal={() => setIsCrawlModalOpen(true)}
            onSeedDemo={handleSeedDemo}
            isSeeding={isSeeding}
          />
        </section>

        {/* Main Leads Table */}
        <section>
          <LeadTable
            leads={leads}
            total={total}
            page={filters.page || 1}
            pageSize={filters.page_size || 25}
            pages={pages}
            isLoading={isLoading}
            error={error}
            sortBy={filters.sort_by || "created_at"}
            sortOrder={filters.sort_order || "desc"}
            onSortChange={handleSortChange}
            onPageChange={handlePageChange}
            onRetry={() => loadLeads(filters, searchQuery, searchMode)}
            onStatusUpdated={() => loadLeads(filters, searchQuery, searchMode)}
            hasSemanticQuery={Boolean(activeSemanticQuery)}
          />
        </section>
      </main>

      {/* Crawl New Domain Modal */}
      <CrawlModal
        isOpen={isCrawlModalOpen}
        onClose={() => setIsCrawlModalOpen(false)}
        onLeadCreated={() => {
          loadLeads(filters, searchQuery, searchMode);
        }}
      />
    </div>
  );
}
