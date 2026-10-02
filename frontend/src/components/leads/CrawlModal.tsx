"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { enqueuePipelineJob, cancelJob, fetchJobStatus, getJobEventsUrl, JobStatusResponse } from "@/lib/api";

interface CrawlModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLeadCreated: () => void;
  campaignId?: string;
}

interface EventLogItem {
  type: string;
  stage: string;
  progress: number;
  message: string;
  timestamp: string;
}

export function CrawlModal({ isOpen, onClose, onLeadCreated, campaignId }: CrawlModalProps) {
  const router = useRouter();

  const [url, setUrl] = useState("https://quotes.toscrape.com");
  const [maxPages, setMaxPages] = useState(3);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Active Job State
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string>("IDLE");
  const [stage, setStage] = useState<string>("");
  const [progress, setProgress] = useState<number>(0);
  const [pagesDiscovered, setPagesDiscovered] = useState<number>(0);
  const [pagesCrawled, setPagesCrawled] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [completedLeadId, setCompletedLeadId] = useState<string | null>(null);
  const [completedIcpScore, setCompletedIcpScore] = useState<number | null>(null);
  const [eventLogs, setEventLogs] = useState<EventLogItem[]>([]);

  const eventSourceRef = useRef<EventSource | null>(null);
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const stopActiveStreams = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  };

  // Clean up EventSource and polling on unmount or modal close
  useEffect(() => {
    return () => {
      stopActiveStreams();
    };
  }, []);

  if (!isOpen) return null;

  const startJob = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    stopActiveStreams();
    setIsSubmitting(true);
    setErrorMessage(null);
    setEventLogs([]);
    setProgress(0);
    setPagesDiscovered(0);
    setPagesCrawled(0);
    setCompletedLeadId(null);
    setCompletedIcpScore(null);
    setJobStatus("QUEUED");
    setStage("Dispatching job to Redis worker queue...");

    try {
      const resp = await enqueuePipelineJob(url.trim(), maxPages, undefined, false, campaignId);
      setActiveJobId(resp.job_id);
      setJobStatus(resp.status);

      // Connect to SSE stream and start polling fallback
      connectEventSource(resp.job_id);
      startPolling(resp.job_id);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to enqueue job");
      setJobStatus("FAILED");
    } finally {
      setIsSubmitting(false);
    }
  };

  const startPolling = (jobId: string) => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
    }

    pollTimerRef.current = setInterval(async () => {
      try {
        const job = await fetchJobStatus(jobId);
        if (job.status) {
          setJobStatus(job.status);
        }

        if (job.status === "COMPLETED") {
          setProgress(100);
          setStage("Pipeline completed successfully");
          const leadId = (job.result as any)?.qualification?.lead_id;
          const score = (job.result as any)?.qualification?.icp_score;
          if (leadId) setCompletedLeadId(leadId);
          if (score !== undefined) setCompletedIcpScore(score);
          onLeadCreated();
          stopActiveStreams();
        } else if (job.status === "FAILED") {
          setJobStatus("FAILED");
          setErrorMessage(job.error_message || "Job execution failed");
          stopActiveStreams();
        } else if (job.status === "CANCELLED") {
          setJobStatus("CANCELLED");
          stopActiveStreams();
        }
      } catch (err) {
        // Non-fatal transient error
      }
    }, 1500);
  };

  const connectEventSource = (jobId: string) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const sseUrl = getJobEventsUrl(jobId);
    const es = new EventSource(sseUrl);
    eventSourceRef.current = es;

    const handleEventData = (dataStr: string) => {
      try {
        const payload = JSON.parse(dataStr);
        const resolvedStatus =
          payload.status ||
          payload.data?.status ||
          (payload.event_type === "job_completed"
            ? "COMPLETED"
            : payload.event_type === "job_failed"
            ? "FAILED"
            : payload.event_type === "job_cancelled"
            ? "CANCELLED"
            : [
                "job_started",
                "crawl_started",
                "page_crawled",
                "qualification_started",
                "embedding_completed",
              ].includes(payload.event_type)
            ? "RUNNING"
            : undefined);

        if (resolvedStatus) setJobStatus(resolvedStatus);
        if (payload.stage) setStage(payload.stage);
        if (payload.progress !== undefined) setProgress(payload.progress);
        if (payload.pages_discovered !== undefined) setPagesDiscovered(payload.pages_discovered);
        if (payload.pages_crawled !== undefined) setPagesCrawled(payload.pages_crawled);

        if (payload.message) {
          setEventLogs((prev) => [
            ...prev.slice(-9), // Keep last 10 events
            {
              type: payload.event_type || "update",
              stage: payload.stage || "",
              progress: payload.progress || 0,
              message: payload.message,
              timestamp: new Date().toLocaleTimeString(),
            },
          ]);
        }

        // Terminal states
        if (payload.event_type === "job_completed" || resolvedStatus === "COMPLETED") {
          setJobStatus("COMPLETED");
          setProgress(100);
          setStage("Pipeline completed successfully");
          const leadId = payload.data?.qualification?.lead_id || payload.result?.qualification?.lead_id;
          const score = payload.data?.qualification?.icp_score || payload.result?.qualification?.icp_score;
          if (leadId) setCompletedLeadId(leadId);
          if (score !== undefined) setCompletedIcpScore(score);
          onLeadCreated();
          stopActiveStreams();
        } else if (payload.event_type === "job_failed" || resolvedStatus === "FAILED") {
          setJobStatus("FAILED");
          setErrorMessage(payload.message || payload.error_message || "Job execution failed");
          stopActiveStreams();
        } else if (payload.event_type === "job_cancelled" || resolvedStatus === "CANCELLED") {
          setJobStatus("CANCELLED");
          stopActiveStreams();
        }
      } catch (err) {
        console.error("SSE parse error:", err);
      }
    };

    es.addEventListener("job_snapshot", (e) => handleEventData(e.data));
    es.addEventListener("job_started", (e) => handleEventData(e.data));
    es.addEventListener("crawl_started", (e) => handleEventData(e.data));
    es.addEventListener("page_crawled", (e) => handleEventData(e.data));
    es.addEventListener("qualification_started", (e) => handleEventData(e.data));
    es.addEventListener("embedding_completed", (e) => handleEventData(e.data));
    es.addEventListener("job_completed", (e) => handleEventData(e.data));
    es.addEventListener("job_failed", (e) => handleEventData(e.data));
    es.addEventListener("job_cancelled", (e) => handleEventData(e.data));
    es.onmessage = (e) => handleEventData(e.data);

    es.onerror = () => {
      // Reconnection or closed stream handled transparently
    };
  };

  const handleCancel = async () => {
    if (!activeJobId) return;
    stopActiveStreams();
    try {
      await cancelJob(activeJobId);
      setJobStatus("CANCELLED");
      setStage("Job cancelled by user");
    } catch (err) {
      console.error("Cancel failed:", err);
    }
  };

  const handleReset = () => {
    stopActiveStreams();
    setActiveJobId(null);
    setJobStatus("IDLE");
    setProgress(0);
    setEventLogs([]);
    setErrorMessage(null);
    setCompletedLeadId(null);
  };

  const isRunning = jobStatus === "QUEUED" || jobStatus === "RUNNING";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
      <div className="relative w-full max-w-xl rounded-2xl bg-slate-900 border border-slate-800 p-6 shadow-2xl space-y-5 max-h-[92vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-semibold text-white">AI Lead Intelligence Pipeline</h3>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                ARQ + Redis + SSE
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Asynchronous ethical web crawling &amp; LLM lead qualification with real-time progress streaming.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Input Form (visible when IDLE or COMPLETED/FAILED) */}
        {!isRunning && (
          <form onSubmit={startJob} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Target Public Domain / URL:
              </label>
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com"
                className="w-full px-3.5 py-2.5 rounded-lg bg-slate-950 border border-slate-800 text-white text-sm focus:outline-none focus:border-indigo-500"
                required
              />
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <label className="text-xs text-slate-400">Pages:</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={maxPages}
                  onChange={(e) => setMaxPages(Number(e.target.value))}
                  className="w-16 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-white text-xs focus:outline-none focus:border-indigo-500"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="flex-1 px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md transition-all disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Enqueueing Job...
                  </>
                ) : (
                  "⚡ Launch Asynchronous Pipeline"
                )}
              </button>
            </div>
          </form>
        )}

        {/* Live SSE Progress Panel */}
        {jobStatus !== "IDLE" && (
          <div className="p-5 rounded-xl bg-slate-950/80 border border-slate-800 space-y-4 shadow-inner">
            {/* Status & Job Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    isRunning
                      ? "bg-amber-400 animate-pulse"
                      : jobStatus === "COMPLETED"
                      ? "bg-emerald-400"
                      : "bg-rose-400"
                  }`}
                />
                <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
                  Status: {jobStatus}
                </span>
                {activeJobId && (
                  <span className="text-[11px] font-mono text-slate-500">
                    ({activeJobId.slice(0, 8)}...)
                  </span>
                )}
              </div>

              {isRunning && (
                <button
                  type="button"
                  onClick={handleCancel}
                  className="text-xs text-rose-400 hover:text-rose-300 font-medium px-2 py-0.5 rounded bg-rose-500/10 border border-rose-500/20"
                >
                  Cancel Job
                </button>
              )}
            </div>

            {/* Progress Bar */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="text-slate-300 font-medium truncate max-w-xs">
                  {stage || "Processing..."}
                </span>
                <span className="font-mono font-bold text-cyan-400">{progress}%</span>
              </div>
              <div className="w-full bg-slate-800/80 rounded-full h-2.5 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-indigo-500 via-cyan-400 to-emerald-400 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>

            {/* Counters */}
            <div className="grid grid-cols-2 gap-3 text-center pt-1">
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-[11px] text-slate-500 block">Pages Discovered</span>
                <span className="text-base font-bold text-slate-200">{pagesDiscovered}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-[11px] text-slate-500 block">Pages Crawled</span>
                <span className="text-base font-bold text-emerald-400">{pagesCrawled}</span>
              </div>
            </div>

            {/* Real-time Event Log */}
            {eventLogs.length > 0 && (
              <div className="space-y-1.5 pt-2">
                <span className="text-[11px] font-semibold text-slate-400 block uppercase tracking-wider">
                  Live Event Stream (Redis Pub/Sub):
                </span>
                <div className="bg-slate-900/90 rounded-lg p-3 border border-slate-800/80 max-h-32 overflow-y-auto font-mono text-[11px] text-slate-300 space-y-1">
                  {eventLogs.map((log, index) => (
                    <div key={index} className="flex items-start gap-2">
                      <span className="text-slate-500 shrink-0">{log.timestamp}</span>
                      <span className="text-cyan-400 shrink-0">[{log.progress}%]</span>
                      <span className="text-slate-300 truncate">{log.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Error state */}
            {errorMessage && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                <span className="font-semibold">Error:</span> {errorMessage}
              </div>
            )}

            {/* Completion state with dossier navigation */}
            {jobStatus === "COMPLETED" && (
              <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-emerald-400 font-bold text-sm">✓</span>
                    <span className="text-xs font-semibold text-emerald-300">
                      Discovery &amp; AI Qualification Complete!
                    </span>
                  </div>
                  {completedIcpScore !== null && (
                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                      ICP: {completedIcpScore}/100
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between gap-3 pt-1">
                  <button
                    type="button"
                    onClick={handleReset}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium"
                  >
                    Start Another Crawl
                  </button>

                  {completedLeadId && (
                    <button
                      type="button"
                      onClick={() => {
                        onClose();
                        router.push(`/leads/${completedLeadId}`);
                      }}
                      className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md transition-colors"
                    >
                      View Intelligence Dossier →
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
