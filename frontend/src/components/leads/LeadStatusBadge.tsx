"use client";

import React, { useState } from "react";
import { updateLeadStatus } from "@/lib/api";

interface LeadStatusBadgeProps {
  leadId: string;
  initialStatus: string;
  editable?: boolean;
  onStatusUpdated?: (newStatus: string) => void;
}

const STATUS_CONFIG: Record<string, { label: string; classes: string; dot: string }> = {
  NEW: {
    label: "New",
    classes: "bg-sky-500/10 text-sky-400 border-sky-500/25",
    dot: "bg-sky-400",
  },
  REVIEW: {
    label: "In Review",
    classes: "bg-amber-500/10 text-amber-400 border-amber-500/25",
    dot: "bg-amber-400",
  },
  QUALIFIED: {
    label: "Qualified",
    classes: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25",
    dot: "bg-emerald-400",
  },
  CONTACTED: {
    label: "Contacted",
    classes: "bg-indigo-500/10 text-indigo-400 border-indigo-500/25",
    dot: "bg-indigo-400",
  },
  REJECTED: {
    label: "Rejected",
    classes: "bg-rose-500/10 text-rose-400 border-rose-500/25",
    dot: "bg-rose-400",
  },
};

export function LeadStatusBadge({
  leadId,
  initialStatus,
  editable = false,
  onStatusUpdated,
}: LeadStatusBadgeProps) {
  const [status, setStatus] = useState(initialStatus.toUpperCase());
  const [isUpdating, setIsUpdating] = useState(false);

  const config = STATUS_CONFIG[status] || {
    label: status,
    classes: "bg-slate-800 text-slate-300 border-slate-700",
    dot: "bg-slate-400",
  };

  const handleStatusChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newStatus = e.target.value;
    setIsUpdating(true);
    try {
      await updateLeadStatus(leadId, newStatus);
      setStatus(newStatus);
      if (onStatusUpdated) onStatusUpdated(newStatus);
    } catch (err) {
      console.error("Failed to update status:", err);
      // Revert if error
    } finally {
      setIsUpdating(false);
    }
  };

  if (!editable) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${config.classes}`}
      >
        <span className={`h-1.5 w-1.5 rounded-full ${config.dot}`} />
        {config.label}
      </span>
    );
  }

  return (
    <div className="relative inline-flex items-center" onClick={(e) => e.stopPropagation()}>
      <select
        value={status}
        disabled={isUpdating}
        onChange={handleStatusChange}
        className={`text-xs font-medium rounded-full px-2.5 py-1 border appearance-none cursor-pointer focus:outline-none transition-all ${
          config.classes
        } ${isUpdating ? "opacity-50 cursor-wait" : "hover:brightness-110"}`}
      >
        <option value="NEW" className="bg-slate-900 text-slate-100">
          New
        </option>
        <option value="REVIEW" className="bg-slate-900 text-slate-100">
          In Review
        </option>
        <option value="QUALIFIED" className="bg-slate-900 text-slate-100">
          Qualified
        </option>
        <option value="CONTACTED" className="bg-slate-900 text-slate-100">
          Contacted
        </option>
        <option value="REJECTED" className="bg-slate-900 text-slate-100">
          Rejected
        </option>
      </select>
    </div>
  );
}
