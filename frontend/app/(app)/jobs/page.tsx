"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { AgentStepper, rememberRun } from "@/components/agent-stepper";
import { BandBadge, ScoreRing } from "@/components/score-ring";
import { Card, inputClass, Loading, Notice, PageHeader, SkillChips } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, SAMPLE, useApi, useProfileId } from "@/lib/api";
import type { Job, JobsResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const BANDS = ["All", "Strong", "Competitive", "Stretch", "Poor"];

export default function JobsPage() {
  const id = useProfileId();
  const { data, loading, error, reload } = useApi<JobsResponse>(id && `/api/profiles/${id}/jobs`);
  const [query, setQuery] = useState("");
  const [band, setBand] = useState("All");
  const [open, setOpen] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [pasted, setPasted] = useState("");
  const [busy, setBusy] = useState(false);
  const own = id !== null && id !== SAMPLE;

  const jobs = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data?.jobs ?? [])
      .filter((j) => band === "All" || j.fit?.band === band)
      .filter((j) => !q || `${j.title} ${j.company} ${j.stack.join(" ")}`.toLowerCase().includes(q))
      .sort((a, b) => (b.fit?.score ?? -1) - (a.fit?.score ?? -1));
  }, [data, query, band]);

  async function findJobs() {
    const form = new FormData();
    form.set("profile_id", id!);
    for (const agent of ["job_discovery", "fit_scorer", "career_coach"]) form.append("agents", agent);
    try {
      const { run_id } = await api<{ run_id: string }>("/api/runs", { method: "POST", body: form });
      rememberRun(run_id);
      setRunId(run_id);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  async function addPasted() {
    setBusy(true);
    try {
      const job = await api<Job>(`/api/profiles/${id}/jobs/paste`, { method: "POST", body: JSON.stringify({ text: pasted }) });
      await api(`/api/profiles/${id}/jobs/fit`, { method: "POST", body: JSON.stringify({ job_ids: [job.id] }) });
      toast.success(`Added and scored: ${job.title}`);
      setPasted("");
      reload();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Jobs" lead="Each job is scored against your profile. Open one to see why, then tailor your resume to it.">
        {own && (
          <Button onClick={findJobs} disabled={runId !== null}>
            Find and score jobs
          </Button>
        )}
      </PageHeader>

      {runId && (
        <Card className="mb-6">
          <AgentStepper runId={runId} onDone={() => (setRunId(null), reload())} />
        </Card>
      )}

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <input
          className={cn(inputClass, "max-w-xs")}
          placeholder="Search title, company or stack"
          aria-label="Search jobs"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by match band">
          {BANDS.map((b) => (
            <button
              key={b}
              onClick={() => setBand(b)}
              aria-pressed={band === b}
              className={cn(
                "rounded-full border px-3.5 py-1.5 text-sm transition-colors duration-200",
                band === b ? "border-transparent bg-accent font-medium text-on-accent" : "border-line-strong text-muted hover:text-fg",
              )}
            >
              {b}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <Loading label="Loading jobs" />
      ) : error ? (
        <Notice title="Jobs could not be loaded">{error.message}</Notice>
      ) : jobs.length === 0 ? (
        <Notice title={data?.jobs.length ? "No jobs match these filters" : "No jobs yet"}>
          {data?.jobs.length
            ? "Clear the search or pick another band."
            : own
              ? "Use Find and score jobs, or paste a job description below."
              : "Upload a resume to search for jobs that fit it."}
        </Notice>
      ) : (
        <ul className="grid gap-4">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} open={open === job.id} onToggle={() => setOpen(open === job.id ? null : job.id)} />
          ))}
        </ul>
      )}

      {own && (
        <Card className="mt-8 max-w-3xl">
          <h2 className="text-lg font-semibold">Add a job from its description</h2>
          <p className="mt-1 text-muted">
            For postings on sites this app does not read, such as LinkedIn or Naukri. Paste the full description.
          </p>
          <textarea
            className={cn(inputClass, "mt-3 min-h-[140px]")}
            aria-label="Job description"
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
          />
          <Button className="mt-3" variant="secondary" disabled={busy || pasted.trim().length < 200} onClick={addPasted}>
            {busy ? "Adding" : "Add and score this job"}
          </Button>
        </Card>
      )}

      {data?.discovery && data.discovery.dropped.length > 0 && (
        <details className="mt-8 max-w-3xl text-sm text-muted">
          <summary className="cursor-pointer font-medium text-fg">
            {data.discovery.dropped.length} postings were left out, and why
          </summary>
          <ul className="mt-3 grid gap-1.5">
            {data.discovery.dropped.map((d, i) => (
              <li key={i}>
                {d.title} {d.company && `at ${d.company}`}: {d.reason}
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

function JobCard({ job, open, onToggle }: { job: Job; open: boolean; onToggle: () => void }) {
  return (
    // `layout` makes the card and its neighbours glide to their new size when it expands.
    <motion.li layout transition={{ duration: 0.3, ease: "easeOut" }} className="card card-hover">
      <button onClick={onToggle} aria-expanded={open} className="flex w-full items-center gap-4 p-4 text-left sm:p-5">
        {job.fit ? (
          <ScoreRing score={job.fit.score} band={job.fit.band} size={64} label="Match" />
        ) : (
          <span className="num flex h-16 w-16 shrink-0 items-center justify-center rounded-full border border-dashed border-line-strong text-muted">
            --
          </span>
        )}
        <span className="min-w-0 flex-1">
          <span className="block font-display text-[17px] font-semibold">{job.title}</span>
          <span className="block text-muted">
            {job.company}
            {job.location && `, ${job.location}`}
          </span>
          <span className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
            {job.fit ? <BandBadge band={job.fit.band} /> : <span>Not scored yet</span>}
            {job.salary && <span className="num">{job.salary}</span>}
            <span>via {job.source}</span>
          </span>
        </span>
        <ChevronDown size={20} aria-hidden className={cn("shrink-0 text-muted transition-transform duration-200", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            layout
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-line p-4 sm:p-5"
          >
            {job.fit && <p className="max-w-3xl leading-relaxed">{job.fit.verdict}</p>}
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <h3 className="mb-2 text-sm font-medium text-muted">You have</h3>
                <SkillChips skills={job.fit?.matched.map((m) => m.skill) ?? []} variant="matched" />
              </div>
              <div>
                <h3 className="mb-2 text-sm font-medium text-muted">Missing</h3>
                <SkillChips skills={job.fit?.missing.map((m) => m.skill) ?? job.must_have} variant="missing" />
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-3">
              <Button asChild size="sm">
                <Link href={`/jobs/${job.id}`}>See the full breakdown</Link>
              </Button>
              <Button asChild size="sm" variant="secondary">
                <a href={job.url} target="_blank" rel="noreferrer">
                  Open the posting on {job.source}
                </a>
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.li>
  );
}
