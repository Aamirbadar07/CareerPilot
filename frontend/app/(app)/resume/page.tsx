"use client";

import { FileUp } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { AgentStepper, rememberRun } from "@/components/agent-stepper";
import { ScoreRing } from "@/components/score-ring";
import { Card, ComponentBars, CopyButton, Loading, Notice, PageHeader } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, useApi, useProfileId } from "@/lib/api";
import type { ProfileResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

const MAX_BYTES = 5 * 1024 * 1024;

export default function ResumePage() {
  const id = useProfileId();
  const { data, loading, reload } = useApi<ProfileResponse>(id && `/api/profiles/${id}`);
  const [runId, setRunId] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  async function upload(chosen: File | undefined) {
    if (!chosen) return;
    if (chosen.size > MAX_BYTES) return toast.error("That file is larger than 5 MB.");
    setFile(chosen);
    const form = new FormData();
    form.set("file", chosen);
    try {
      const { run_id } = await api<{ run_id: string }>("/api/runs", { method: "POST", body: form });
      rememberRun(run_id);
      setRunId(run_id);
      toast.success("Upload received. The agents are starting.");
    } catch (e) {
      setFile(null);
      toast.error((e as Error).message);
    }
  }

  const parsing = runId !== null && file !== null;
  const bullets = new Map(
    [...(data?.profile.experience ?? []), ...(data?.profile.projects ?? [])].flatMap((e) =>
      e.bullets.map((b) => [b.id, b.text] as const),
    ),
  );
  const analysis = data?.analysis;

  return (
    <>
      <PageHeader title="Resume" lead="Upload a resume to build your profile, see how it scores and fix its weakest lines." />

      <div className="grid gap-5 lg:grid-cols-2">
        <Card
          onDragOver={(e) => (e.preventDefault(), setDragging(true))}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => (e.preventDefault(), setDragging(false), upload(e.dataTransfer.files[0]))}
          className={cn("relative overflow-hidden border-dashed transition-colors duration-200", dragging && "border-line-strong bg-surface-2")}
        >
          {/* The scanning line: one bar sweeping down the card while the file is parsed. */}
          {parsing && (
            <span
              className="pointer-events-none absolute inset-x-0 top-0 h-1/4 bg-accent opacity-20"
              style={{ animation: "scan 1.6s ease-in-out infinite" }}
              aria-hidden
            />
          )}
          <div className="flex flex-col items-start gap-3">
            <FileUp size={26} className="text-accent" aria-hidden />
            <h2 className="text-lg font-semibold">{file ? file.name : "Drop your resume here"}</h2>
            <p className="leading-relaxed text-muted">
              PDF, DOCX or TXT, up to 5 MB. The file is read in memory and never stored. The profile built from it is
              deleted after 24 hours, or at once from Settings.
            </p>
            <input
              ref={input}
              type="file"
              accept=".pdf,.docx,.txt"
              className="sr-only"
              onChange={(e) => upload(e.target.files?.[0])}
              aria-label="Resume file"
            />
            <Button onClick={() => input.current?.click()} disabled={parsing}>
              {parsing ? "Reading your resume" : "Choose a file"}
            </Button>
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold">Progress</h2>
          <div className="mt-4 min-h-[380px]">
            {runId ? (
              <AgentStepper runId={runId} onDone={() => (setFile(null), reload())} />
            ) : (
              <p className="leading-relaxed text-muted">
                After you upload, each agent appears here as it starts, finishes or fails. A failed step can be retried
                on its own.
              </p>
            )}
          </div>
        </Card>
      </div>

      <h2 className="mb-3 mt-9 text-xl font-semibold">Analysis</h2>
      {loading ? (
        <Loading label="Loading analysis" />
      ) : !analysis ? (
        <Notice title="No analysis yet">Upload a resume above and the analysis appears here.</Notice>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
          <Card>
            <div className="flex items-center gap-5">
              <ScoreRing score={analysis.ats.score} size={96} label="ATS score" />
              <div>
                <h3 className="text-lg font-semibold">ATS score</h3>
                <p className="text-sm text-muted">How cleanly an applicant tracking system reads this resume.</p>
              </div>
            </div>
            <p className="mt-5 leading-relaxed">{analysis.overall_verdict}</p>
            <div className="mt-6">
              <ComponentBars components={analysis.ats.components} />
            </div>
          </Card>

          <div className="grid content-start gap-5">
            <Card>
              <h3 className="text-lg font-semibold">Weak bullets and how to fix them</h3>
              {analysis.weak_bullets.length === 0 && <p className="mt-2 text-muted">No weak bullets found.</p>}
              <ul className="mt-4 grid gap-6">
                {analysis.weak_bullets.map((w) => (
                  <li key={w.bullet_id}>
                    <p className="rounded-lg bg-[var(--remove-bg)] px-3 py-2 leading-relaxed">{bullets.get(w.bullet_id)}</p>
                    <p className="mt-2 text-sm leading-relaxed text-muted">{w.problem}</p>
                    <p className="mt-2 rounded-lg bg-[var(--add-bg)] px-3 py-2 leading-relaxed">{w.rewrite}</p>
                    {w.needs_from_user && (
                      <p className="mt-2 text-sm leading-relaxed">
                        <span className="font-medium">To make it stronger: </span>
                        <span className="text-muted">{w.needs_from_user}</span>
                      </p>
                    )}
                    <div className="mt-2">
                      <CopyButton text={w.rewrite} label="Copy rewrite" />
                    </div>
                  </li>
                ))}
              </ul>
            </Card>

            <Card>
              <h3 className="text-lg font-semibold">Highest-leverage gaps</h3>
              <ol className="mt-4 grid gap-4">
                {analysis.top_gaps.map((g, i) => (
                  <li key={g.gap} className="flex gap-3">
                    <span className="num mt-0.5 text-sm text-muted">{i + 1}</span>
                    <div>
                      <p className="font-medium">{g.gap}</p>
                      <p className="mt-0.5 text-sm leading-relaxed text-muted">{g.blocks}</p>
                      <p className="mt-1 text-sm leading-relaxed">
                        <span className="font-medium">Smallest fix: </span>
                        {g.smallest_action}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </Card>

            <Card>
              <h3 className="text-lg font-semibold">Keywords your target roles expect</h3>
              <ul className="mt-3 grid gap-2">
                {analysis.missing_keywords.map((k) => (
                  <li key={k.keyword + k.for_role} className="flex flex-wrap items-baseline justify-between gap-2">
                    <span>
                      <span className="font-medium">{k.keyword}</span>
                      <span className="text-sm text-muted"> for {k.for_role}</span>
                    </span>
                    <span className={cn("text-sm", k.severity === "high" ? "text-stretch" : "text-muted")}>
                      {k.severity} priority
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
