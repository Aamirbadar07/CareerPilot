"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { BandBadge, ScoreRing } from "@/components/score-ring";
import { Card, ComponentBars, Loading, Notice, PageHeader, SkillChips } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, useApi, useProfileId } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function JobPage({ params }: { params: { id: string } }) {
  const id = useProfileId();
  const router = useRouter();
  const { data: job, loading, error, reload } = useApi<Job>(id && `/api/profiles/${id}/jobs/${params.id}`);
  const [busy, setBusy] = useState<"tailor" | "score" | null>(null);

  async function tailor() {
    setBusy("tailor");
    toast.info("Tailoring and fact-checking. This takes up to a minute.");
    try {
      await api(`/api/profiles/${id}/jobs/${params.id}/tailor`, { method: "POST" });
      toast.success("Tailored resume ready");
      router.push(`/tailor/${params.id}`);
    } catch (e) {
      toast.error((e as Error).message);
      setBusy(null);
    }
  }

  async function score() {
    setBusy("score");
    try {
      await api(`/api/profiles/${id}/jobs/fit`, { method: "POST", body: JSON.stringify({ job_ids: [params.id] }) });
      toast.success("Scored");
      reload();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <Loading label="Loading job" />;
  if (error || !job)
    return (
      <Notice title="Job not found" action={<Button asChild><Link href="/jobs">Back to jobs</Link></Button>}>
        {error?.message}
      </Notice>
    );
  const fit = job.fit;

  return (
    <>
      <PageHeader title={job.title} lead={[job.company, job.location, job.employment_type].filter(Boolean).join(", ")}>
        <div className="flex flex-wrap gap-3">
          <Button onClick={tailor} disabled={busy !== null}>
            {busy === "tailor" ? "Tailoring" : "Tailor my resume to this job"}
          </Button>
          <Button asChild variant="secondary">
            <a href={job.url} target="_blank" rel="noreferrer">
              Open the posting on {job.source}
            </a>
          </Button>
        </div>
      </PageHeader>

      {!fit ? (
        <Notice
          title="Not scored against your current profile"
          action={
            <Button onClick={score} disabled={busy !== null}>
              {busy === "score" ? "Scoring" : "Score this job"}
            </Button>
          }
        >
          Your profile changed, or this job was never scored.
        </Notice>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[1fr_1.15fr]">
          <Card>
            <div className="flex items-center gap-5">
              <ScoreRing score={fit.score} band={fit.band} size={104} label="Match" />
              <div>
                <BandBadge band={fit.band} />
                <p className="mt-1 text-sm text-muted">A match score, not a chance of being hired.</p>
              </div>
            </div>
            <p className="mt-5 leading-relaxed">{fit.verdict}</p>
            {fit.capped && (
              <p className="mt-3 rounded-lg border border-line-strong px-3 py-2 text-sm leading-relaxed text-competitive">
                The score is held at 60 because a must-have is missing. Close it and the cap goes away.
              </p>
            )}
            <div className="mt-6">
              <ComponentBars components={fit.dimensions} />
            </div>
          </Card>

          <div className="grid content-start gap-5">
            <Card>
              <h2 className="text-lg font-semibold">What you have that the job asks for</h2>
              <div className="mt-3">
                <SkillChips skills={fit.matched.map((m) => m.skill)} variant="matched" />
              </div>
              <h2 className="mt-6 text-lg font-semibold">What is missing</h2>
              {fit.missing.length === 0 && <p className="mt-2 text-muted">Nothing the posting demands is missing.</p>}
              <ul className="mt-3 grid gap-3">
                {fit.missing.map((m) => (
                  <li key={m.skill}>
                    <span className="font-medium">{m.skill}</span>
                    <span className={m.type === "blocker" ? "text-sm text-stretch" : "text-sm text-muted"}>
                      {m.type === "blocker" ? " blocks this application" : " can be learned"}
                    </span>
                    <p className="text-sm leading-relaxed text-muted">{m.how_to_close}</p>
                  </li>
                ))}
              </ul>
            </Card>

            <Card>
              <h2 className="text-lg font-semibold">What a tailored resume can fix today</h2>
              {fit.closable_now.length === 0 ? (
                <p className="mt-2 text-muted">Nothing. The gaps here need new work, not new wording.</p>
              ) : (
                <ul className="mt-3 grid list-disc gap-2 pl-5 leading-relaxed">
                  {fit.closable_now.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              )}
              <h3 className="mt-5 text-sm font-medium text-muted">The line your resume should lead with</h3>
              <p className="mt-1 leading-relaxed">{fit.resume_angle}</p>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
