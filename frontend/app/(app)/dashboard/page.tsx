"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AgentStepper, lastRun } from "@/components/agent-stepper";
import { BandBadge, ScoreRing } from "@/components/score-ring";
import { Card, Loading, Notice, PageHeader, Skeleton } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { useApi, useProfileId } from "@/lib/api";
import type { JobsResponse, LinkedIn, ProfileResponse } from "@/lib/types";

export default function Dashboard() {
  const id = useProfileId();
  const profile = useApi<ProfileResponse>(id && `/api/profiles/${id}`);
  const jobs = useApi<JobsResponse>(id && `/api/profiles/${id}/jobs`);
  const linkedin = useApi<{ result: LinkedIn | null }>(id && `/api/profiles/${id}/linkedin`);
  const [runId, setRunId] = useState<string | null>(null);
  useEffect(() => setRunId(lastRun()), []);

  if (profile.error)
    return (
      <Notice title="This profile is gone" action={<Button asChild><Link href="/resume">Upload a resume</Link></Button>}>
        {profile.error.message} Uploaded profiles are deleted after 24 hours.
      </Notice>
    );

  const name = profile.data?.profile.identity.full_name;
  const scored = (jobs.data?.jobs ?? []).filter((j) => j.fit);
  const top = [...scored].sort((a, b) => b.fit!.score - a.fit!.score).slice(0, 4);

  return (
    <>
      <PageHeader
        title={name ? `${name}'s search` : "Dashboard"}
        lead={profile.data?.profile.identity.title_line ?? undefined}
      />
      <div className="grid gap-5 lg:grid-cols-[1.15fr_1fr]">
        <Card>
          <h2 className="text-lg font-semibold">Last run</h2>
          <div className="mt-4">
            {runId ? (
              <AgentStepper runId={runId} onDone={() => (profile.reload(), jobs.reload())} />
            ) : (
              <p className="leading-relaxed text-muted">
                Nothing has run in this browser yet. Upload a resume and every agent reports here as it works.
              </p>
            )}
          </div>
          <Button asChild variant="secondary" size="sm" className="mt-3">
            <Link href="/resume">{runId ? "Start another run" : "Upload a resume"}</Link>
          </Button>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold">Profile strength</h2>
          {profile.loading ? (
            <Skeleton className="mt-4 h-24 w-full" />
          ) : (
            <div className="mt-4 grid gap-5 sm:grid-cols-2">
              <Strength
                label="Resume (ATS)"
                score={profile.data?.analysis?.ats.score}
                href="/resume"
                empty="Not analysed yet"
              />
              <Strength
                label="LinkedIn"
                score={linkedin.data?.result?.profile_strength.score}
                href="/linkedin"
                empty="Paste your profile to score it"
              />
            </div>
          )}
          {profile.data?.analysis && (
            <p className="mt-5 leading-relaxed text-muted">{profile.data.analysis.overall_verdict}</p>
          )}
        </Card>
      </div>

      <h2 className="mb-3 mt-9 text-lg font-semibold">Best matches</h2>
      {jobs.loading ? (
        <Loading rows={2} label="Loading jobs" />
      ) : top.length === 0 ? (
        <Notice title="No scored jobs yet" action={<Button asChild><Link href="/jobs">Go to jobs</Link></Button>}>
          Jobs appear here once discovery and fit scoring have run.
        </Notice>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {top.map((job) => (
            <li key={job.id}>
              <Link href={`/jobs/${job.id}`} className="card card-hover flex items-center gap-4 p-4">
                <ScoreRing score={job.fit!.score} band={job.fit!.band} size={60} label="Match" />
                <span className="min-w-0">
                  <span className="block truncate font-medium">{job.title}</span>
                  <span className="block truncate text-sm text-muted">{job.company}</span>
                  <BandBadge band={job.fit!.band} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function Strength({ label, score, href, empty }: { label: string; score?: number; href: string; empty: string }) {
  return (
    <Link href={href} className="flex items-center gap-4 rounded-[10px] p-1 hover:bg-surface-2">
      {score === undefined ? (
        <span className="flex h-[72px] w-[72px] items-center justify-center rounded-full border border-dashed border-line-strong text-muted">
          <span className="num">--</span>
        </span>
      ) : (
        <ScoreRing score={score} label={label} />
      )}
      <span>
        <span className="block font-medium">{label}</span>
        <span className="block text-sm text-muted">{score === undefined ? empty : "out of 100"}</span>
      </span>
    </Link>
  );
}
