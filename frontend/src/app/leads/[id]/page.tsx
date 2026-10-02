"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { fetchLeadDetail, updateLeadStatus, LeadDetail } from "@/lib/api";
import { LeadScore } from "@/components/leads/LeadScore";
import { LeadStatusBadge } from "@/components/leads/LeadStatusBadge";
import { EvidenceSignals } from "@/components/leads/EvidenceSignals";
import { SourcePages } from "@/components/leads/SourcePages";
import { AuditDetails } from "@/components/leads/AuditDetails";

export default function LeadDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();

  const [lead, setLead] = useState<LeadDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDetail = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchLeadDetail(resolvedParams.id);
      setLead(data);
    } catch (err: any) {
      setError(err.message || "Failed to load lead dossier");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDetail();
  }, [resolvedParams.id]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 p-8 flex items-center justify-center">
        <div className="space-y-4 text-center">
          <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-xs text-slate-400 font-medium">Loading sales intelligence dossier...</p>
        </div>
      </div>
    );
  }

  if (error || !lead) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 p-8">
        <div className="max-w-4xl mx-auto space-y-6">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            ← Back to Leads Dashboard
          </Link>
          <div className="p-8 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-center space-y-3 shadow-lg">
            <h2 className="text-base font-bold text-rose-300">Lead Intelligence Record Not Found</h2>
            <p className="text-xs text-rose-400/80">{error || "Could not retrieve dossier."}</p>
            <button
              onClick={() => router.push("/")}
              className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white"
            >
              Return to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  const isDemo = lead.company_name.startsWith("[Demo]");
  const displayName = lead.company_name.replace(/^\[Demo\]\s*/, "");
  const products = lead.qualification_json?.products_or_services || [];
  const observedFacts = lead.qualification_json?.observed_facts || [];
  const unknownAttrs = lead.qualification_json?.unknown_attributes || [];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500 selection:text-white pb-16">
      {/* Top Breadcrumb Header */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors"
            >
              ← Back to Leads
            </Link>
            <span className="text-slate-600">/</span>
            <span className="text-xs font-semibold text-slate-300 truncate max-w-xs">{displayName}</span>
          </div>

          <div className="flex items-center gap-3">
            <LeadStatusBadge
              leadId={lead.id}
              initialStatus={lead.status}
              editable={true}
              onStatusUpdated={(newStatus) => {
                setLead({ ...lead, status: newStatus });
              }}
            />
            <a
              href={`https://${lead.domain}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 transition-colors"
            >
              Visit Website ↗
            </a>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        {/* Company Header Card */}
        <section className="p-6 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div className="space-y-1.5">
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                  {displayName}
                </h1>
                {isDemo && (
                  <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/40">
                    Synthetic Demo Lead
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 font-mono flex items-center gap-2">
                <span>{lead.domain}</span>
                <span>·</span>
                <span>Crawl Target: {lead.crawl_target_id.slice(0, 8)}...</span>
              </p>
            </div>

            <div className="flex items-center gap-3 self-start">
              <div className="text-right">
                <span className="text-[11px] text-slate-400 block font-medium">ICP Match Score</span>
                <LeadScore score={lead.icp_score} size="lg" showLabel={true} />
              </div>
              <div className="text-right pl-3 border-l border-slate-800">
                <span className="text-[11px] text-slate-400 block font-medium">Confidence</span>
                <span className="text-lg font-bold font-mono text-cyan-400">
                  {Math.round(lead.confidence_score * 100)}%
                </span>
              </div>
            </div>
          </div>

          {/* Firmographics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-4 border-t border-slate-800/80 text-xs">
            <div>
              <span className="text-slate-500 block">Industry</span>
              <span className="font-semibold text-slate-200">{lead.industry}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Geography</span>
              <span className="font-semibold text-slate-200">{lead.geography}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Company Size</span>
              <span className="font-semibold text-slate-200">
                {lead.estimated_company_size === "Unknown" ? "Unknown" : `${lead.estimated_company_size} employees`}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">Business Model</span>
              <span className="font-semibold text-slate-200">{lead.business_model}</span>
            </div>
          </div>
        </section>

        {/* Evidence Grounding Breakdown: Facts, Inferences, Unknowns */}
        {(observedFacts.length > 0 || unknownAttrs.length > 0) && (
          <section className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-md space-y-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-amber-400 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-amber-400" />
              Evidence Grounding &amp; Fact Separation (Anti-Hallucination)
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              {observedFacts.length > 0 && (
                <div className="space-y-2">
                  <span className="text-emerald-400 font-semibold flex items-center gap-1.5">
                    <span>✓</span> Directly Observed Facts ({observedFacts.length})
                  </span>
                  <ul className="space-y-1.5 text-slate-300">
                    {observedFacts.map((fact: string, idx: number) => (
                      <li key={idx} className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
                        {fact}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {unknownAttrs.length > 0 && (
                <div className="space-y-2">
                  <span className="text-slate-400 font-semibold flex items-center gap-1.5">
                    <span>?</span> Unevidenced Attributes Marked Unknown ({unknownAttrs.length})
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {unknownAttrs.map((attr: string, idx: number) => (
                      <span key={idx} className="px-2.5 py-1 rounded-md bg-slate-950 text-slate-400 border border-slate-800 font-mono text-[11px]">
                        {attr}: Unknown
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {/* AI Business Intelligence Overview */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Company Summary & Value Prop */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-md space-y-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-indigo-400 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-indigo-400" />
              Company Intelligence &amp; Value Proposition
            </h2>
            <div className="space-y-3 text-xs leading-relaxed text-slate-300">
              <div>
                <span className="text-slate-500 font-semibold block mb-1">Company Summary:</span>
                <p className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/60">{lead.company_summary}</p>
              </div>
              <div>
                <span className="text-slate-500 font-semibold block mb-1">Core Value Proposition:</span>
                <p className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/60 text-indigo-200">
                  {lead.value_proposition}
                </p>
              </div>
              <div>
                <span className="text-slate-500 font-semibold block mb-1">Target Audience:</span>
                <p className="text-slate-300">{lead.target_audience}</p>
              </div>
            </div>
          </div>

          {/* Products & Tech Signals */}
          <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-md space-y-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-cyan-400 flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-cyan-400" />
              Offerings &amp; Technology Stack
            </h2>

            <div className="space-y-4 text-xs">
              <div>
                <span className="text-slate-500 font-semibold block mb-1.5">Identified Products &amp; Services:</span>
                {products && products.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {products.map((p: string, i: number) => (
                      <span key={i} className="px-2.5 py-1 rounded-md bg-slate-800 text-slate-200 border border-slate-700">
                        {p}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-500 italic">None specifically parsed.</p>
                )}
              </div>

              <div>
                <span className="text-slate-500 font-semibold block mb-1.5">Technology &amp; Platform Signals:</span>
                {lead.technology_signals && lead.technology_signals.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {lead.technology_signals.map((tech: string, i: number) => (
                      <span
                        key={i}
                        className="px-2.5 py-1 rounded-md bg-indigo-950/40 text-indigo-300 border border-indigo-800/40 font-mono text-[11px]"
                      >
                        {tech}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-500 italic">No specific technology signals detected.</p>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* Why This Lead? Traceable Qualification Evidence */}
        <section className="space-y-3">
          <div className="border-b border-slate-800 pb-2">
            <h2 className="text-base font-bold text-white tracking-tight">Why This Lead? Traceable Evidence</h2>
            <p className="text-xs text-slate-400">
              Direct verbatim quotes and website citations supporting ICP fit decisions.
            </p>
          </div>
          <EvidenceSignals signals={lead.signals} reasoning={lead.qualification_reasoning} />
        </section>

        {/* Contributing Source Pages */}
        <section className="space-y-3">
          <div className="border-b border-slate-800 pb-2">
            <h2 className="text-base font-bold text-white tracking-tight">Contributing Source Pages</h2>
            <p className="text-xs text-slate-400">
              Web pages fetched by the crawler that supplied factual text to the intelligence pipeline.
            </p>
          </div>
          <SourcePages pages={lead.source_pages} />
        </section>

        {/* Collapsible AI Engineering Telemetry & Vector Audit */}
        <section className="space-y-3">
          <div className="border-b border-slate-800 pb-2">
            <h2 className="text-base font-bold text-white tracking-tight">System Telemetry &amp; Vector Embeddings</h2>
            <p className="text-xs text-slate-400">
              Audit log records, token consumption metrics, latency, and pgvector cosine indexing.
            </p>
          </div>
          <AuditDetails auditLogs={lead.audit_logs} embedding={lead.embedding} />
        </section>
      </main>
    </div>
  );
}
