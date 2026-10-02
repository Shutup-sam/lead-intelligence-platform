"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@/lib/AuthContext";
import {
  fetchAnalyticsOverview,
  fetchAnalyticsUsage,
  fetchAnalyticsLeads,
  AnalyticsOverviewResponse,
  AnalyticsUsageResponse,
  AnalyticsLeadsResponse,
} from "@/lib/api";

export default function AnalyticsPage() {
  const { organization } = useAuth();
  const [overview, setOverview] = useState<AnalyticsOverviewResponse | null>(null);
  const [usage, setUsage] = useState<AnalyticsUsageResponse | null>(null);
  const [leadsAnalytics, setLeadsAnalytics] = useState<AnalyticsLeadsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadAllAnalytics() {
      setIsLoading(true);
      setError(null);
      try {
        const [ov, us, ld] = await Promise.all([
          fetchAnalyticsOverview(),
          fetchAnalyticsUsage(),
          fetchAnalyticsLeads(),
        ]);
        setOverview(ov);
        setUsage(us);
        setLeadsAnalytics(ld);
      } catch (err: any) {
        setError(err.message || "Failed to load organization analytics");
      } finally {
        setIsLoading(false);
      }
    }
    loadAllAnalytics();
  }, []);

  const jobSuccessRate =
    overview && overview.jobs_completed + overview.jobs_failed > 0
      ? ((overview.jobs_completed / (overview.jobs_completed + overview.jobs_failed)) * 100).toFixed(1)
      : "100";

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-zinc-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white">Analytics & Usage</h1>
            <span className="rounded-full bg-indigo-950/80 px-2.5 py-0.5 text-xs font-semibold text-indigo-400 border border-indigo-800/40">
              {organization?.name || "Workspace"}
            </span>
          </div>
          <p className="mt-1 text-sm text-zinc-400">
            Real-time pipeline telemetry, daily organization usage meters, and estimated AI compute costs.
          </p>
        </div>

        {/* Quota Limits Badge */}
        <div className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/80 px-3.5 py-2 text-xs">
          <div>
            <span className="text-zinc-500">Concurrency: </span>
            <span className="font-semibold text-zinc-200">5 Jobs Max</span>
          </div>
          <div className="h-3 w-[1px] bg-zinc-800" />
          <div>
            <span className="text-zinc-500">Monthly Quota: </span>
            <span className="font-semibold text-zinc-200">100 Crawls</span>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-800/50 bg-rose-950/40 p-4 text-sm text-rose-300">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-24 text-zinc-500 gap-2">
          <svg className="h-5 w-5 animate-spin text-indigo-400" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          Aggregating telemetry and audit logs...
        </div>
      )}

      {!isLoading && overview && (
        <>
          {/* Executive KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Total Leads */}
            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Total Leads
                </span>
                <span className="rounded bg-indigo-950/80 px-2 py-0.5 text-[11px] font-semibold text-indigo-400 border border-indigo-800/40">
                  {overview.qualification_rate}% qual.
                </span>
              </div>
              <div className="mt-2 text-3xl font-extrabold text-white">
                {overview.total_leads}
              </div>
              <div className="mt-1 text-xs text-zinc-400">
                <span className="text-emerald-400 font-medium">{overview.qualified_leads}</span> meeting ICP criteria
              </div>
            </div>

            {/* Crawling Telemetry */}
            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Crawl Targets
                </span>
                <span className="rounded bg-zinc-800 px-2 py-0.5 text-[11px] text-zinc-400">
                  Scrapling
                </span>
              </div>
              <div className="mt-2 text-3xl font-extrabold text-white">
                {overview.total_crawls}
              </div>
              <div className="mt-1 text-xs text-zinc-400">
                <span className="text-indigo-400 font-medium">{overview.pages_crawled}</span> pages extracted & cleaned
              </div>
            </div>

            {/* Background Jobs */}
            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Async Jobs
                </span>
                <span className="rounded bg-emerald-950/80 px-2 py-0.5 text-[11px] font-semibold text-emerald-400 border border-emerald-800/40">
                  {jobSuccessRate}% success
                </span>
              </div>
              <div className="mt-2 text-3xl font-extrabold text-white">
                {overview.jobs_completed}
              </div>
              <div className="mt-1 text-xs text-zinc-400">
                <span className="text-rose-400 font-medium">{overview.jobs_failed}</span> failed executions
              </div>
            </div>

            {/* Estimated AI Cost */}
            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Estimated AI Cost
                </span>
                <span className="rounded bg-purple-950/80 px-2 py-0.5 text-[11px] font-semibold text-purple-400 border border-purple-800/40">
                  Audit Logs
                </span>
              </div>
              <div className="mt-2 text-3xl font-extrabold text-white">
                ${overview.estimated_ai_cost.toFixed(4)}
              </div>
              <div className="mt-1 text-xs text-zinc-400">
                Based on $0.15/1M input & $0.60/1M output
              </div>
            </div>
          </div>

          {/* Lead Distribution Breakdown */}
          {leadsAnalytics && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Campaign Breakdown */}
              <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-5">
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300">
                  Leads by Campaign
                </h3>
                <div className="mt-4 space-y-3">
                  {leadsAnalytics.by_campaign.length === 0 ? (
                    <p className="text-xs text-zinc-500 py-4 text-center">No campaign leads recorded yet</p>
                  ) : (
                    leadsAnalytics.by_campaign.map((c, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="text-zinc-300 font-medium truncate max-w-[160px]">
                          {c.campaign_name}
                        </span>
                        <div className="flex items-center gap-3">
                          <span className="text-indigo-400 font-semibold">{c.total_leads} leads</span>
                          <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
                            Avg ICP {c.avg_icp_score.toFixed(0)}
                          </span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Industry Breakdown */}
              <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-5">
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300">
                  Leads by Industry Vertical
                </h3>
                <div className="mt-4 space-y-3">
                  {leadsAnalytics.by_industry.length === 0 ? (
                    <p className="text-xs text-zinc-500 py-4 text-center">No industry data available</p>
                  ) : (
                    leadsAnalytics.by_industry.slice(0, 5).map((ind, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="text-zinc-300 truncate">{ind.industry}</span>
                        <span className="font-semibold text-white">{ind.count}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Status Breakdown */}
              <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-5">
                <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-300">
                  Lead Status Distribution
                </h3>
                <div className="mt-4 space-y-3">
                  {Object.entries(leadsAnalytics.by_status).map(([st, count]) => (
                    <div key={st} className="flex items-center justify-between text-xs">
                      <span className="rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider bg-zinc-800 text-zinc-300">
                        {st}
                      </span>
                      <span className="font-semibold text-white">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Daily Usage Table */}
          <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-5">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
              <div>
                <h3 className="text-sm font-bold text-white">Daily Organization Usage (Last 30 Days)</h3>
                <p className="text-xs text-zinc-400">Auditable daily resource consumption and AI pipeline invocations.</p>
              </div>
            </div>

            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-zinc-800 text-zinc-400">
                  <tr>
                    <th className="pb-2.5 font-semibold">Date</th>
                    <th className="pb-2.5 font-semibold">Crawls</th>
                    <th className="pb-2.5 font-semibold">Pages Crawled</th>
                    <th className="pb-2.5 font-semibold">Leads Created</th>
                    <th className="pb-2.5 font-semibold">AI Qualifications</th>
                    <th className="pb-2.5 font-semibold">Jobs Completed</th>
                    <th className="pb-2.5 font-semibold text-right">Est. AI Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50 text-zinc-300">
                  {usage && usage.items.length > 0 ? (
                    usage.items.map((row) => (
                      <tr key={row.date} className="hover:bg-zinc-800/30">
                        <td className="py-2.5 font-medium text-white">{row.date}</td>
                        <td className="py-2.5">{row.crawls}</td>
                        <td className="py-2.5">{row.pages_crawled}</td>
                        <td className="py-2.5 text-indigo-400 font-semibold">{row.leads_created}</td>
                        <td className="py-2.5">{row.ai_qualifications}</td>
                        <td className="py-2.5 text-emerald-400">{row.jobs_completed}</td>
                        <td className="py-2.5 text-right font-mono text-zinc-200">
                          ${row.estimated_ai_cost.toFixed(4)}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-6 text-center text-zinc-500">
                        No usage recorded for this workspace yet. Run a crawl to generate metrics!
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
