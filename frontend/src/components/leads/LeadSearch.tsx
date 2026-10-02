"use client";

import React from "react";

interface LeadSearchProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  searchMode: "keyword" | "semantic";
  onModeToggle: (mode: "keyword" | "semantic") => void;
  onSearchSubmit: (e: React.FormEvent) => void;
  isSearching?: boolean;
}

export function LeadSearch({
  searchQuery,
  onSearchChange,
  searchMode,
  onModeToggle,
  onSearchSubmit,
  isSearching = false,
}: LeadSearchProps) {
  return (
    <form onSubmit={onSearchSubmit} className="space-y-2">
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
        {/* Mode Selector */}
        <div className="flex p-1 rounded-lg bg-slate-900 border border-slate-800 text-xs font-medium self-start sm:self-auto">
          <button
            type="button"
            onClick={() => onModeToggle("keyword")}
            className={`px-3 py-1.5 rounded-md transition-all ${
              searchMode === "keyword"
                ? "bg-slate-800 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Keyword Search
          </button>
          <button
            type="button"
            onClick={() => onModeToggle("semantic")}
            className={`px-3 py-1.5 rounded-md flex items-center gap-1.5 transition-all ${
              searchMode === "semantic"
                ? "bg-indigo-600 text-white shadow-sm"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-300 animate-pulse" />
            AI Semantic Search
          </button>
        </div>

        {/* Input box */}
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={
              searchMode === "semantic"
                ? "Describe target companies... (e.g., 'B2B companies selling workflow software to enterprise teams')"
                : "Search companies, domains, industries, value propositions..."
            }
            className="w-full pl-10 pr-20 py-2.5 rounded-lg bg-slate-900/90 border border-slate-800 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => onSearchChange("")}
              className="absolute inset-y-0 right-14 pr-2 flex items-center text-slate-500 hover:text-slate-300 text-xs"
            >
              Clear
            </button>
          )}
          <button
            type="submit"
            disabled={isSearching}
            className="absolute inset-y-1.5 right-1.5 px-3 rounded-md bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors disabled:opacity-50"
          >
            {isSearching ? "Searching..." : "Search"}
          </button>
        </div>
      </div>

      {searchMode === "semantic" && (
        <p className="text-[11px] text-slate-400 pl-1">
          <span className="text-cyan-400 font-medium">pgvector Semantic Search:</span> Translates natural language into 1536-dimensional embeddings and ranks leads by cosine similarity against canonical company intelligence documents.
        </p>
      )}
    </form>
  );
}
