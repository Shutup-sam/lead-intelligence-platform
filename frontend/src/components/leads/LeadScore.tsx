"use client";

import React from "react";

interface LeadScoreProps {
  score: number;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
}

export function LeadScore({ score, size = "md", showLabel = false }: LeadScoreProps) {
  let colorClasses = "bg-rose-500/10 text-rose-400 border-rose-500/20";
  let dotColor = "bg-rose-400";
  let label = "Low Fit";

  if (score >= 80) {
    colorClasses = "bg-emerald-500/10 text-emerald-400 border-emerald-500/25";
    dotColor = "bg-emerald-400";
    label = "Strong Fit";
  } else if (score >= 60) {
    colorClasses = "bg-amber-500/10 text-amber-400 border-amber-500/25";
    dotColor = "bg-amber-400";
    label = "Moderate";
  }

  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs font-semibold",
    md: "px-2.5 py-1 text-xs font-semibold",
    lg: "px-3.5 py-1.5 text-sm font-bold",
  }[size];

  return (
    <div className="inline-flex items-center gap-1.5">
      <span
        className={`inline-flex items-center gap-1.5 rounded-full border font-mono tracking-tight ${colorClasses} ${sizeClasses}`}
      >
        <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
        <span>{score}</span>
        {showLabel && <span className="font-sans font-normal text-slate-400">/100 · {label}</span>}
      </span>
    </div>
  );
}
