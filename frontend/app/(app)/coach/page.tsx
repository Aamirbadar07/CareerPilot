"use client";

import { useState } from "react";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { Card, Loading, Notice, PageHeader } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, SAMPLE, useApi, useProfileId } from "@/lib/api";
import type { Plan } from "@/lib/types";

export default function CoachPage() {
  const id = useProfileId();
  const { data, loading, setData } = useApi<{ plan: Plan | null }>(id && `/api/profiles/${id}/coach`);
  const [busy, setBusy] = useState(false);
  const own = id !== null && id !== SAMPLE;
  const plan = data?.plan;

  async function refresh() {
    setBusy(true);
    try {
      setData({ plan: await api<Plan>(`/api/profiles/${id}/coach`, { method: "POST" }) });
      toast.success("Coaching plan ready");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Coach" lead="One plan from all your fit reports together: what blocks the most jobs, and the five actions worth doing.">
        {own && (
          <Button onClick={refresh} disabled={busy}>
            {busy ? "Reading your fit reports" : plan ? "Rebuild the plan" : "Build my plan"}
          </Button>
        )}
      </PageHeader>

      {loading ? (
        <Loading label="Loading coaching plan" />
      ) : !plan ? (
        <Notice title="No plan yet">
          {own
            ? "A plan needs scored jobs. Score some on the Jobs page, then build it here. It is rebuilt after your profile changes."
            : "Upload a resume first."}
        </Notice>
      ) : (
        <div className="grid gap-5">
          <Card>
            <p className="font-display text-xl font-semibold leading-snug sm:text-2xl">{plan.one_line_verdict}</p>
          </Card>

          <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
            <Card>
              <h2 className="text-lg font-semibold">Five actions, in order</h2>
              <ol className="mt-4 grid gap-6">
                {plan.plan.map((a) => (
                  <li key={a.rank} className="flex gap-4">
                    <span className="num flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-sm font-semibold text-on-accent">
                      {a.rank}
                    </span>
                    <div className="min-w-0">
                      <p className="font-medium leading-relaxed">{a.action}</p>
                      <p className="mt-1 text-sm leading-relaxed text-muted">{a.why_this_one}</p>
                      <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
                        <Fact term="Effort" value={`${a.effort_hours} hours`} mono />
                        <Fact term="Cost" value={a.cost} />
                        <Fact term="When" value={a.timeline} />
                      </dl>
                      <p className="mt-1 text-sm leading-relaxed">
                        <span className="text-muted">What a recruiter will see: </span>
                        {a.proof_artifact}
                      </p>
                      {a.jobs_unlocked.length > 0 && (
                        <p className="mt-2 text-sm leading-relaxed">
                          <span className="text-muted">Helps with: </span>
                          {a.jobs_unlocked.join("; ")}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            </Card>

            <div className="grid content-start gap-5">
              <Card>
                <h2 className="text-lg font-semibold">Gaps that repeat across jobs</h2>
                <p className="mt-1 text-sm text-muted">Share of your scored jobs that list each skill as missing.</p>
                {plan.pattern_gaps.length === 0 ? (
                  <p className="mt-3 text-muted">No skill is missing in more than one job.</p>
                ) : (
                  <GapChart gaps={plan.pattern_gaps} />
                )}
              </Card>

              <Card>
                <h2 className="text-lg font-semibold">The one change that moves the most jobs</h2>
                <p className="mt-2 leading-relaxed">{plan.score_ceiling.change}</p>
                <p className="mt-2 text-sm leading-relaxed text-muted">{plan.score_ceiling.expected_band_shift}</p>
              </Card>

              <Card>
                <h2 className="text-lg font-semibold">Positioning</h2>
                <p className="mt-2 leading-relaxed">{plan.positioning.verdict}</p>
                <dl className="mt-3 grid gap-1 text-sm">
                  <Fact term="Commit to" value={plan.positioning.commit_to.join(", ")} />
                  {plan.positioning.drop.length > 0 && <Fact term="Drop" value={plan.positioning.drop.join(", ")} />}
                </dl>
              </Card>

              <Card>
                <h2 className="text-lg font-semibold">Claims an interviewer will test</h2>
                <ul className="mt-3 grid gap-3">
                  {plan.evidence_debt.map((e) => (
                    <li key={e.skill}>
                      <span className="font-medium">{e.skill}</span>
                      <p className="text-sm leading-relaxed text-muted">{e.risk}</p>
                    </li>
                  ))}
                </ul>
              </Card>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Fact({ term, value, mono }: { term: string; value: string; mono?: boolean }) {
  return (
    <div className="flex gap-2">
      <dt className="shrink-0 text-muted">{term}</dt>
      <dd className={mono ? "num" : undefined}>{value}</dd>
    </div>
  );
}

const DIFFICULTY: Record<string, string> = { low: "var(--strong)", medium: "var(--competitive)", high: "var(--stretch)" };

function GapChart({ gaps }: { gaps: Plan["pattern_gaps"] }) {
  const height = gaps.length * 44 + 8;
  return (
    <>
      {/* Height is fixed from the row count, so the chart reserves its space before it draws. */}
      <div style={{ height }} className="mt-4" role="img" aria-label={gaps.map((g) => `${g.skill}: ${g.pct_of_targets} percent of jobs`).join("; ")}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={gaps} layout="vertical" margin={{ left: 0, right: 44, top: 0, bottom: 0 }}>
            <XAxis type="number" domain={[0, 100]} hide />
            <YAxis
              type="category"
              dataKey="skill"
              width={128}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--fg)", fontSize: 13 }}
            />
            <Bar dataKey="pct_of_targets" radius={6} barSize={18} background={{ fill: "var(--surface-2)", radius: 6 }} isAnimationActive={false}>
              {gaps.map((g) => (
                <Cell key={g.skill} fill={DIFFICULTY[g.acquisition_difficulty]} />
              ))}
              <LabelList
                dataKey="pct_of_targets"
                position="right"
                formatter={(v) => `${v}%`}
                style={{ fill: "var(--muted)", fontSize: 13, fontFamily: "var(--font-mono)" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-sm text-muted">
        Colour shows how hard the skill is to pick up:{" "}
        <span className="text-strong">low</span>, <span className="text-competitive">medium</span>,{" "}
        <span className="text-stretch">high</span>.
      </p>
    </>
  );
}
