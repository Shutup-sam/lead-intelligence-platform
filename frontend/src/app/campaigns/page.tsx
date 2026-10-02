"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/AuthContext";
import {
  CampaignResponse,
  fetchCampaigns,
  deleteCampaign,
} from "@/lib/api";
import { CreateCampaignModal } from "@/components/campaigns/CreateCampaignModal";
import { CrawlModal } from "@/components/leads/CrawlModal";

export default function CampaignsPage() {
  const { user, organization } = useAuth();
  const [campaigns, setCampaigns] = useState<CampaignResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedCrawlCampaignId, setSelectedCrawlCampaignId] = useState<string | null>(null);
  const [isCrawlModalOpen, setIsCrawlModalOpen] = useState(false);

  const loadCampaigns = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchCampaigns();
      setCampaigns(data.items);
    } catch (err: any) {
      setError(err.message || "Failed to load campaigns.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCampaigns();
  }, [loadCampaigns]);

  const handleDelete = async (campaignId: string) => {
    if (!window.confirm("Are you sure you want to delete this campaign? Existing leads will be preserved.")) {
      return;
    }
    try {
      await deleteCampaign(campaignId);
      setCampaigns((prev) => prev.filter((c) => c.id !== campaignId));
    } catch (err: any) {
      alert(err.message || "Failed to delete campaign");
    }
  };

  const handleLaunchCrawl = (campaignId: string) => {
    setSelectedCrawlCampaignId(campaignId);
    setIsCrawlModalOpen(true);
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-zinc-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-white">Lead Campaigns</h1>
            <span className="rounded-full bg-indigo-950/80 px-2.5 py-0.5 text-xs font-semibold text-indigo-400 border border-indigo-800/40">
              {organization?.name || "Workspace"}
            </span>
          </div>
          <p className="mt-1 text-sm text-zinc-400">
            Define target Ideal Customer Profiles (ICP) and segment autonomous crawls by campaign buckets.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setIsCreateModalOpen(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 transition-colors"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
          </svg>
          New Campaign
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-xl border border-rose-800/50 bg-rose-950/40 p-4 text-sm text-rose-300">
          {error}
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-20 text-zinc-500 gap-2">
          <svg className="h-5 w-5 animate-spin text-indigo-400" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          Loading workspace campaigns...
        </div>
      )}

      {/* Empty State */}
      {!isLoading && campaigns.length === 0 && (
        <div className="rounded-2xl border border-dashed border-zinc-800 bg-zinc-900/30 p-12 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-800 text-zinc-400">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <h3 className="mt-4 text-base font-semibold text-white">No campaigns found</h3>
          <p className="mt-1 text-xs text-zinc-400 max-w-md mx-auto">
            Create your first outbound campaign to target specific verticals, company sizes, and tailored AI qualification criteria.
          </p>
          <button
            type="button"
            onClick={() => setIsCreateModalOpen(true)}
            className="mt-6 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 shadow-md shadow-indigo-600/30"
          >
            Create Campaign
          </button>
        </div>
      )}

      {/* Campaigns Grid */}
      {!isLoading && campaigns.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {campaigns.map((camp) => {
            const icp = camp.icp_config || {};
            const qualRate = camp.total_leads > 0 ? ((camp.qualified_leads / camp.total_leads) * 100).toFixed(0) : "0";

            return (
              <div
                key={camp.id}
                className="group flex flex-col justify-between rounded-xl border border-zinc-800/80 bg-zinc-900/60 p-5 shadow-lg backdrop-blur-sm hover:border-zinc-700 transition-all"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-bold text-white text-base group-hover:text-indigo-300 transition-colors">
                      {camp.name}
                    </h3>
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                        camp.status === "ACTIVE"
                          ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800/50"
                          : "bg-zinc-800 text-zinc-400"
                      }`}
                    >
                      {camp.status}
                    </span>
                  </div>

                  {camp.description && (
                    <p className="mt-1.5 text-xs text-zinc-400 line-clamp-2">
                      {camp.description}
                    </p>
                  )}

                  {/* Metrics Bar */}
                  <div className="mt-4 grid grid-cols-3 gap-2 rounded-lg border border-zinc-800/80 bg-zinc-950/50 p-2.5 text-center">
                    <div>
                      <div className="text-xs text-zinc-400">Total Leads</div>
                      <div className="text-sm font-bold text-white">{camp.total_leads}</div>
                    </div>
                    <div>
                      <div className="text-xs text-zinc-400">Qualified</div>
                      <div className="text-sm font-bold text-indigo-400">{camp.qualified_leads}</div>
                    </div>
                    <div>
                      <div className="text-xs text-zinc-400">Rate</div>
                      <div className="text-sm font-bold text-emerald-400">{qualRate}%</div>
                    </div>
                  </div>

                  {/* ICP Tags */}
                  <div className="mt-4 space-y-2">
                    <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                      ICP Specification
                    </div>
                    <div className="flex flex-wrap gap-1.5 text-[11px]">
                      {icp.industries && icp.industries.length > 0 ? (
                        icp.industries.slice(0, 3).map((ind: string, idx: number) => (
                          <span key={idx} className="rounded bg-zinc-800/80 px-2 py-0.5 text-zinc-300">
                            {ind}
                          </span>
                        ))
                      ) : (
                        <span className="text-zinc-500">All Industries</span>
                      )}
                      {icp.minimum_score && (
                        <span className="rounded bg-indigo-950/80 px-2 py-0.5 font-semibold text-indigo-300 border border-indigo-800/40">
                          ICP ≥ {icp.minimum_score}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Actions Footer */}
                <div className="mt-6 flex items-center justify-between border-t border-zinc-800/80 pt-4">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleLaunchCrawl(camp.id)}
                      className="rounded-md bg-indigo-600/90 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500 transition-colors"
                    >
                      Crawl URL
                    </button>
                    <Link
                      href={`/?campaign_id=${camp.id}`}
                      className="rounded-md border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:text-white hover:border-zinc-700 transition-colors"
                    >
                      View Leads
                    </Link>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleDelete(camp.id)}
                    title="Delete Campaign"
                    className="rounded p-1.5 text-zinc-500 hover:text-rose-400 hover:bg-zinc-800"
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Create Campaign Modal */}
      <CreateCampaignModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreated={(newCamp) => {
          setCampaigns((prev) => [newCamp, ...prev]);
        }}
      />

      {/* Crawl Modal targeted to selected campaign */}
      {selectedCrawlCampaignId && (
        <CrawlModal
          isOpen={isCrawlModalOpen}
          onClose={() => {
            setIsCrawlModalOpen(false);
            setSelectedCrawlCampaignId(null);
          }}
          onLeadCreated={() => {
            loadCampaigns();
          }}
          campaignId={selectedCrawlCampaignId}
        />
      )}
    </div>
  );
}
