"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, inputClass, Loading, PageHeader } from "@/components/ui/bits";
import { Button } from "@/components/ui/button";
import { api, SAMPLE, setProfileId, useApi, useProfileId } from "@/lib/api";
import type { Preferences, ProfileResponse } from "@/lib/types";

const TYPES = ["full-time", "internship", "contract", "part-time"];
const list = (text: string) => text.split(",").map((s) => s.trim()).filter(Boolean);

export default function SettingsPage() {
  const id = useProfileId();
  const router = useRouter();
  const { data, loading } = useApi<ProfileResponse>(id && `/api/profiles/${id}`);
  const [prefs, setPrefs] = useState<Preferences | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const own = id !== null && id !== SAMPLE;
  useEffect(() => setPrefs(data?.profile.preferences ?? null), [data]);

  async function save() {
    setSaving(true);
    try {
      await api(`/api/profiles/${id}/preferences`, { method: "PUT", body: JSON.stringify(prefs) });
      toast.success("Preferences saved. Job scores will be recalculated against them.");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function deleteData() {
    try {
      await api(`/api/profiles/${id}`, { method: "DELETE" });
      localStorage.removeItem("careerpilot.run");
      setProfileId(SAMPLE);
      toast.success("Your data is deleted");
      router.push("/");
    } catch (e) {
      toast.error((e as Error).message);
    }
  }

  const set = (patch: Partial<Preferences>) => setPrefs((p) => (p ? { ...p, ...patch } : p));

  return (
    <>
      <PageHeader title="Settings" lead="What kind of jobs to look for, and what happens to your data." />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <h2 className="text-lg font-semibold">Job preferences</h2>
          {loading || !prefs ? (
            <div className="mt-4">
              <Loading rows={1} label="Loading preferences" />
            </div>
          ) : (
            <fieldset disabled={!own} className="mt-4 grid gap-4 disabled:opacity-70">
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-[var(--accent-from)]"
                  checked={prefs.remote_only}
                  onChange={(e) => set({ remote_only: e.target.checked })}
                />
                Remote jobs only
              </label>
              <label className="grid gap-1.5">
                <span className="font-medium">Locations</span>
                <input
                  className={inputClass}
                  defaultValue={prefs.locations.join(", ")}
                  onBlur={(e) => set({ locations: list(e.target.value) })}
                  placeholder="Pune, Bengaluru"
                />
                <span className="text-sm text-muted">Separate with commas.</span>
              </label>
              <div className="grid grid-cols-[1fr_7rem] gap-3">
                <label className="grid gap-1.5">
                  <span className="font-medium">Minimum salary</span>
                  <input
                    type="number"
                    min={0}
                    className={`${inputClass} num`}
                    value={prefs.min_salary ?? ""}
                    onChange={(e) => set({ min_salary: e.target.value ? Number(e.target.value) : null })}
                  />
                </label>
                <label className="grid gap-1.5">
                  <span className="font-medium">Currency</span>
                  <input
                    className={`${inputClass} num`}
                    maxLength={3}
                    value={prefs.currency}
                    onChange={(e) => set({ currency: e.target.value.toUpperCase() })}
                  />
                </label>
              </div>
              <div>
                <span className="font-medium">Employment types</span>
                <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2">
                  {TYPES.map((t) => (
                    <label key={t} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        className="h-4 w-4 accent-[var(--accent-from)]"
                        checked={prefs.employment_types.includes(t)}
                        onChange={(e) =>
                          set({
                            employment_types: e.target.checked
                              ? [...prefs.employment_types, t]
                              : prefs.employment_types.filter((x) => x !== t),
                          })
                        }
                      />
                      {t}
                    </label>
                  ))}
                </div>
              </div>
              <label className="grid gap-1.5">
                <span className="font-medium">Companies to leave out</span>
                <input
                  className={inputClass}
                  defaultValue={prefs.exclude_companies.join(", ")}
                  onBlur={(e) => set({ exclude_companies: list(e.target.value) })}
                />
              </label>
              {own ? (
                <Button onClick={save} disabled={saving} className="justify-self-start">
                  {saving ? "Saving" : "Save preferences"}
                </Button>
              ) : (
                <p className="text-sm text-muted">The sample profile cannot be edited. Upload a resume to set your own.</p>
              )}
            </fieldset>
          )}
        </Card>

        <div className="grid content-start gap-5">
          <Card>
            <h2 className="text-lg font-semibold">Privacy</h2>
            <ul className="mt-3 grid list-disc gap-2 pl-5 leading-relaxed text-muted">
              <li>Your resume file is read in memory and is never written to disk or kept.</li>
              <li>
                The profile built from it, and everything derived from it, is deleted automatically
                {data?.expires_at ? ` on ${new Date(data.expires_at).toLocaleString()}` : " 24 hours after upload"}.
              </li>
              <li>Your email and phone number are not sent to the AI model after the first read of your resume.</li>
              <li>There are no accounts. This browser remembers one profile id; anyone with that id can read the profile until it expires.</li>
              <li>The app never applies to a job, posts to LinkedIn or contacts anyone for you.</li>
            </ul>
          </Card>

          <Card>
            <h2 className="text-lg font-semibold">Delete my data</h2>
            <p className="mt-2 leading-relaxed text-muted">
              Removes your profile, every job score, tailored resume, plan and cached AI result now. This cannot be undone.
            </p>
            {!own ? (
              <p className="mt-3 text-sm text-muted">You have not uploaded anything, so there is nothing to delete.</p>
            ) : confirming ? (
              <div className="mt-4 flex flex-wrap gap-3">
                <Button variant="danger" onClick={deleteData}>
                  Yes, delete everything
                </Button>
                <Button variant="secondary" onClick={() => setConfirming(false)}>
                  Keep my data
                </Button>
              </div>
            ) : (
              <Button variant="danger" className="mt-4" onClick={() => setConfirming(true)}>
                Delete my data
              </Button>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
