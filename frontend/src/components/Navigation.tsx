"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/AuthContext";

export function Navigation() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, organization, organizations, switchOrganization, logout } = useAuth();
  const [isOrgDropdownOpen, setIsOrgDropdownOpen] = useState(false);
  const [isUserDropdownOpen, setIsUserDropdownOpen] = useState(false);

  const navLinks = [
    { label: "Leads", href: "/" },
    { label: "Campaigns", href: "/campaigns" },
    { label: "Analytics & Usage", href: "/analytics" },
  ];

  return (
    <header className="sticky top-0 z-40 w-full border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand & Workspace */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 p-0.5 shadow-lg shadow-indigo-500/20 group-hover:scale-105 transition-transform">
              <div className="flex h-full w-full items-center justify-center rounded-[7px] bg-zinc-950">
                <svg className="h-5 w-5 text-indigo-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
            </div>
            <div>
              <span className="text-base font-bold tracking-tight text-white group-hover:text-indigo-300 transition-colors">
                LeadIntel
              </span>
              <span className="ml-1 text-xs font-semibold uppercase tracking-wider text-indigo-400/90">
                SaaS
              </span>
            </div>
          </Link>

          {/* Organization Workspace Dropdown */}
          {user && organization && (
            <div className="relative">
              <button
                type="button"
                onClick={() => setIsOrgDropdownOpen(!isOrgDropdownOpen)}
                className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/90 px-2.5 py-1.5 text-xs font-medium text-zinc-300 hover:border-zinc-700 hover:text-white transition-colors"
              >
                <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="max-w-[120px] truncate">{organization.name}</span>
                <span className="rounded bg-indigo-950/80 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-300 border border-indigo-800/50">
                  {organization.role}
                </span>
                <svg className="h-3.5 w-3.5 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {isOrgDropdownOpen && (
                <div
                  className="absolute left-0 mt-2 w-64 rounded-lg border border-zinc-800 bg-zinc-900 p-2 shadow-2xl ring-1 ring-black/50 z-50"
                  onMouseLeave={() => setIsOrgDropdownOpen(false)}
                >
                  <div className="px-2 py-1.5 text-[11px] font-medium uppercase tracking-wider text-zinc-500">
                    Switch Workspace
                  </div>
                  <div className="space-y-1">
                    {organizations.map((org) => (
                      <button
                        key={org.id}
                        type="button"
                        onClick={() => {
                          switchOrganization(org.id);
                          setIsOrgDropdownOpen(false);
                        }}
                        className={`flex w-full items-center justify-between rounded-md px-2.5 py-2 text-xs font-medium transition-colors ${
                          org.id === organization.id
                            ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                            : "text-zinc-300 hover:bg-zinc-800/80 hover:text-white"
                        }`}
                      >
                        <span className="truncate">{org.name}</span>
                        <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
                          {org.role}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    isActive
                      ? "bg-zinc-800 text-white shadow-sm"
                      : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                  }`}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* User Status / Account Dropdown */}
        <div className="flex items-center gap-3">
          {user ? (
            <div className="relative">
              <button
                type="button"
                onClick={() => setIsUserDropdownOpen(!isUserDropdownOpen)}
                className="flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/90 pl-2 pr-3 py-1 text-xs text-zinc-300 hover:border-zinc-700 hover:text-white transition-colors"
              >
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-tr from-indigo-600 to-purple-600 text-[11px] font-bold text-white">
                  {user.full_name ? user.full_name.charAt(0).toUpperCase() : "U"}
                </div>
                <span className="max-w-[100px] truncate font-medium">{user.full_name || user.email}</span>
                <svg className="h-3 w-3 text-zinc-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {isUserDropdownOpen && (
                <div
                  className="absolute right-0 mt-2 w-56 rounded-lg border border-zinc-800 bg-zinc-900 p-2 shadow-2xl ring-1 ring-black/50 z-50"
                  onMouseLeave={() => setIsUserDropdownOpen(false)}
                >
                  <div className="border-b border-zinc-800/80 px-2.5 py-2">
                    <p className="text-xs font-semibold text-white truncate">{user.full_name}</p>
                    <p className="text-[11px] text-zinc-400 truncate">{user.email}</p>
                  </div>
                  <div className="pt-1">
                    <button
                      type="button"
                      onClick={async () => {
                        setIsUserDropdownOpen(false);
                        await logout();
                        router.push("/login");
                      }}
                      className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-xs font-medium text-rose-400 hover:bg-rose-950/30 hover:text-rose-300 transition-colors"
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                      </svg>
                      Sign Out
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link
                href="/login"
                className="rounded-md px-3 py-1.5 text-xs font-medium text-zinc-300 hover:text-white transition-colors"
              >
                Sign In
              </Link>
              <Link
                href="/register"
                className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 shadow-sm shadow-indigo-600/30 transition-colors"
              >
                Get Started
              </Link>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
