"use client";

import { Pin } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ScoreRing } from "@/components/score-ring";
import { Card, ComponentBars, CopyButton, inputClass, Loading, Notice, PageHeader } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, SAMPLE, useApi, useProfileId } from "@/lib/api";
import type { LinkedIn } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function LinkedInPage() {
  const id = useProfileId();
  const { data, loading, setData } = useApi<{ result: LinkedIn | null }>(id && `/api/profiles/${id}/linkedin`);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const own = id !== null && id !== SAMPLE;
  const result = data?.result;

  async function optimize() {
    setBusy(true);
    try {
      const fresh = await api<LinkedIn>(`/api/profiles/${id}/linkedin`, {
        method: "POST",
        body: JSON.stringify({ linkedin_text: text }),
      });
      setData({ result: fresh });
      toast.success("LinkedIn suggestions ready");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="LinkedIn"
        lead="Text to paste into your profile, and every place it disagrees with your resume. The app never logs in to LinkedIn or edits it."
      />

      {own && (
        <Card className="mb-6 max-w-3xl">
          <h2 className="text-lg font-semibold">Paste your current profile</h2>
          <p className="mt-1 text-muted">
            On LinkedIn, open your profile, choose More, then Save to PDF, and paste its text here. Or copy the page
            text directly.
          </p>
          <textarea
            className={cn(inputClass, "mt-3 min-h-[150px]")}
            aria-label="Your LinkedIn profile text"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <Button className="mt-3" onClick={optimize} disabled={busy || text.trim().length < 50}>
            {busy ? "Writing suggestions" : "Write my LinkedIn text"}
          </Button>
        </Card>
      )}

      {loading ? (
        <Loading label="Loading LinkedIn suggestions" />
      ) : !result ? (
        <Notice title="No suggestions yet">
          {own ? "Paste your profile above to get headlines, an About section and a consistency check." : "Upload a resume first."}
        </Notice>
      ) : (
        <div className="grid gap-5">
          <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
            <Card>
              <div className="flex items-center gap-5">
                <ScoreRing score={result.profile_strength.score} size={96} label="LinkedIn profile strength" />
                <div>
                  <h2 className="text-lg font-semibold">Profile strength today</h2>
                  <p className="text-sm text-muted">Scored on what you pasted, before any changes.</p>
                </div>
              </div>
              <h3 className="mt-5 font-semibold">Three changes with the most effect for the least work</h3>
              <ol className="mt-2 grid list-decimal gap-2 pl-5 leading-relaxed">
                {result.profile_strength.top_changes.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ol>
              <div className="mt-6">
                <ComponentBars components={result.profile_strength.components} />
              </div>
            </Card>

            <Card>
              <h2 className="text-lg font-semibold">Where LinkedIn and your resume disagree</h2>
              <p className="mt-1 text-sm text-muted">Recruiters compare the two. Fix these first.</p>
              {result.consistency_check.length === 0 && <p className="mt-3 text-muted">No mismatches found.</p>}
              <ul className="mt-4 grid gap-4">
                {result.consistency_check.map((m, i) => (
                  <li key={i} className="border-l-2 border-[var(--competitive)] pl-4">
                    <p className="font-medium first-letter:uppercase">{m.field}</p>
                    <dl className="mt-1 grid gap-0.5 text-sm">
                      <div className="flex gap-2">
                        <dt className="w-20 shrink-0 text-muted">Resume</dt>
                        <dd>{m.resume_value ?? "not listed"}</dd>
                      </div>
                      <div className="flex gap-2">
                        <dt className="w-20 shrink-0 text-muted">LinkedIn</dt>
                        <dd>{m.linkedin_value ?? "not listed"}</dd>
                      </div>
                      <div className="flex gap-2">
                        <dt className="w-20 shrink-0 text-muted">Use</dt>
                        <dd className="font-medium">{m.correct_value}</dd>
                      </div>
                    </dl>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <Card>
            <h2 className="text-lg font-semibold">Headline</h2>
            <p className="mt-1 text-sm text-muted">Three options. Each leads with the role recruiters search for.</p>
            <ul className="mt-4 grid gap-3">
              {result.headline.map((h) => (
                <li key={h} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line p-3">
                  <span className="min-w-0 flex-1 leading-relaxed">{h}</span>
                  <span className="num text-sm text-muted">{h.length} / 220</span>
                  <CopyButton text={h} />
                </li>
              ))}
            </ul>
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">About</h2>
                <CopyButton text={result.about.join("\n\n")} label="Copy all" />
              </div>
              <div className="mt-3 grid gap-3 leading-relaxed">
                {result.about.map((p) => (
                  <p key={p}>{p}</p>
                ))}
              </div>
            </Card>

            <Card>
              <h2 className="text-lg font-semibold">Experience</h2>
              {result.experience_rewrites.map((r) => {
                const body = [r.scope, ...r.bullets.map((b) => `- ${b}`)].join("\n");
                return (
                  <div key={r.exp_id} className="mt-3">
                    <p className="leading-relaxed">{r.scope}</p>
                    <ul className="mt-2 grid list-disc gap-1.5 pl-5 leading-relaxed">
                      {r.bullets.map((b) => (
                        <li key={b}>{b}</li>
                      ))}
                    </ul>
                    <div className="mt-3">
                      <CopyButton text={body} />
                    </div>
                  </div>
                );
              })}
            </Card>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <h2 className="text-lg font-semibold">Skills, in this order</h2>
              <p className="mt-1 text-sm text-muted">Pin the first three. Pinned skills carry the most search weight.</p>
              <ol className="mt-3 flex flex-wrap gap-2">
                {result.skills_order.map((s) => (
                  <li
                    key={s.name}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm",
                      s.pinned ? "border-line-strong bg-surface-2 font-medium" : "border-line",
                    )}
                  >
                    {s.pinned && <Pin size={13} className="text-accent" aria-label="Pin this skill" />}
                    {s.name}
                  </li>
                ))}
              </ol>
            </Card>

            <Card>
              <h2 className="text-lg font-semibold">Search terms you are missing</h2>
              <ul className="mt-3 grid gap-3">
                {result.keyword_gaps.map((k) => (
                  <li key={k.term}>
                    <span className="font-medium">{k.term}</span>
                    <span className={cn("text-sm", k.status === "addable-now" ? "text-strong" : "text-muted")}>
                      {k.status === "addable-now" ? " you can add this now" : " needs new work first"}
                    </span>
                    <p className="text-sm leading-relaxed text-muted">{k.note}</p>
                  </li>
                ))}
              </ul>
              <h3 className="mt-5 font-semibold">Worth featuring</h3>
              <ul className="mt-2 grid gap-2">
                {result.featured_suggestions.map((f) => (
                  <li key={f.item}>
                    <span className="font-medium">{f.item}</span>
                    <p className="text-sm leading-relaxed text-muted">{f.why}</p>
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
