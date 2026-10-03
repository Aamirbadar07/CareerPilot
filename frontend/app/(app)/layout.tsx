"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Award, Briefcase, Compass, FileText, LayoutDashboard, Settings, UserRound } from "lucide-react";
import { ThemeToggle } from "@/components/theme";
import { SAMPLE, useProfileId } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  ["/dashboard", "Dashboard", LayoutDashboard],
  ["/resume", "Resume", FileText],
  ["/jobs", "Jobs", Briefcase],
  ["/linkedin", "LinkedIn", UserRound],
  ["/certifications", "Certifications", Award],
  ["/coach", "Coach", Compass],
  ["/settings", "Settings", Settings],
] as const;

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const profileId = useProfileId();
  return (
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col md:flex-row">
      <aside className="border-line md:sticky md:top-0 md:h-screen md:w-56 md:shrink-0 md:border-r">
        <div className="flex h-14 items-center justify-between px-5 md:h-16">
          <Link href="/" className="font-display text-lg font-semibold">
            CareerPilot
          </Link>
          <ThemeToggle />
        </div>
        {/* A horizontal strip that scrolls on phones, a column from md up. */}
        <nav aria-label="App" className="flex gap-1 overflow-x-auto border-b border-line px-3 pb-2 md:flex-col md:border-0 md:pb-0">
          {NAV.map(([href, label, Icon]) => {
            const active = path === href || path.startsWith(href + "/") || (href === "/jobs" && path.startsWith("/tailor"));
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex shrink-0 items-center gap-2.5 rounded-[10px] px-3 py-2 text-[15px] transition-colors duration-200",
                  active ? "bg-surface-2 font-medium text-fg" : "text-muted hover:bg-surface-2 hover:text-fg",
                )}
              >
                <Icon size={17} aria-hidden className={active ? "text-accent" : undefined} />
                {label}
              </Link>
            );
          })}
        </nav>
      </aside>

      <main id="main" className="min-w-0 flex-1 px-5 py-6 sm:px-8 md:py-9">
        {(profileId === null || profileId === SAMPLE) && (
          <p className="mb-6 rounded-[10px] border border-line bg-surface px-4 py-2.5 text-sm text-muted">
            You are looking at a sample profile for a fictional candidate. Its jobs are examples, not live postings.{" "}
            <Link href="/resume" className="font-medium text-accent underline underline-offset-4">
              Upload your own resume
            </Link>
          </p>
        )}
        {children}
      </main>
    </div>
  );
}
