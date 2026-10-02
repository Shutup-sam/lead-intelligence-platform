"use client";

import React, { useState } from "react";
import { CampaignCreateRequest, createCampaign, CampaignResponse } from "@/lib/api";

interface CreateCampaignModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (campaign: CampaignResponse) => void;
}

export function CreateCampaignModal({ isOpen, onClose, onCreated }: CreateCampaignModalProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [industries, setIndustries] = useState("SaaS, Artificial Intelligence, Fintech");
  const [companySizes, setCompanySizes] = useState("11-50, 51-200");
  const [geographies, setGeographies] = useState("United States, Canada, United Kingdom");
  const [technologies, setTechnologies] = useState("Next.js, Python, PostgreSQL");
  const [businessModels, setBusinessModels] = useState("B2B SaaS, Enterprise Software");
  const [minScore, setMinScore] = useState(65);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const payload: CampaignCreateRequest = {
        name: name.trim(),
        description: description.trim() || undefined,
        icp: {
          industries: industries.split(",").map((s) => s.trim()).filter(Boolean),
          company_sizes: companySizes.split(",").map((s) => s.trim()).filter(Boolean),
          geographies: geographies.split(",").map((s) => s.trim()).filter(Boolean),
          technologies: technologies.split(",").map((s) => s.trim()).filter(Boolean),
          business_models: businessModels.split(",").map((s) => s.trim()).filter(Boolean),
          minimum_score: minScore,
        },
      };

      const campaign = await createCampaign(payload);
      onCreated(campaign);
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to create campaign");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/75 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative w-full max-w-xl rounded-2xl border border-zinc-800 bg-zinc-900 p-6 shadow-2xl z-10 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
          <div>
            <h2 className="text-lg font-bold text-white">Create New Campaign</h2>
            <p className="text-xs text-zinc-400">Configure target Ideal Customer Profile (ICP) for AI qualification.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-white"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-lg border border-rose-800/50 bg-rose-950/40 p-3 text-xs text-rose-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-zinc-300">Campaign Name *</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Q4 FinTech Outbound High-Growth"
              className="mt-1 block w-full rounded-lg border border-zinc-800 bg-zinc-950/80 px-3.5 py-2 text-sm text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-zinc-300">Campaign Goal / Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Sourcing B2B fintech startups in North America"
              className="mt-1 block w-full rounded-lg border border-zinc-800 bg-zinc-950/80 px-3.5 py-2 text-sm text-white placeholder-zinc-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-4 space-y-3.5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-indigo-400">
              Ideal Customer Profile (ICP) Criteria
            </h3>

            <div>
              <label className="block text-xs font-medium text-zinc-300">Target Industries (comma-separated)</label>
              <input
                type="text"
                value={industries}
                onChange={(e) => setIndustries(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-zinc-800 bg-zinc-950/80 px-3 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-zinc-300">Company Sizes</label>
                <input
                  type="text"
                  value={companySizes}
                  onChange={(e) => setCompanySizes(e.target.value)}
                  placeholder="11-50, 51-200"
                  className="mt-1 block w-full rounded-lg border border-zinc-800 bg-zinc-950/80 px-3 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300">Target Geographies</label>
                <input
                  type="text"
                  value={geographies}
                  onChange={(e) => setGeographies(e.target.value)}
                  placeholder="United States, Canada"
                  className="mt-1 block w-full rounded-lg border border-zinc-800 bg-zinc-950/80 px-3 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-zinc-300">Business Models</label>
                <input
                  type="text"
                  value={businessModels}
                  onChange={(e) => setBusinessModels(e.target.value)}
                  placeholder="B2B SaaS, Marketplace"
                  className="mt-1 block w-full rounded-lg border border-zinc-800 bg-zinc-950/80 px-3 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-300">Required Technologies</label>
                <input
                  type="text"
                  value={technologies}
                  onChange={(e) => setTechnologies(e.target.value)}
                  placeholder="Next.js, Python, Stripe"
                  className="mt-1 block w-full rounded-lg border border-zinc-800 bg-zinc-950/80 px-3 py-1.5 text-xs text-white focus:border-indigo-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label className="block text-xs font-medium text-zinc-300">
                  Minimum Qualification ICP Threshold: <span className="font-bold text-indigo-400">{minScore}/100</span>
                </label>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
                className="mt-2 w-full accent-indigo-500"
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-800">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-xs font-semibold text-zinc-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 disabled:opacity-50"
            >
              {isSubmitting ? "Creating..." : "Save Campaign"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
