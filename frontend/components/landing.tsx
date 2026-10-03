"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { useEffect } from "react";
import { AgentGraph } from "@/components/agent-graph";
import { ThemeToggle } from "@/components/theme";
import { Button } from "@/components/ui/button";
import { prefersReducedMotion } from "@/lib/utils";

const HEADLINE = ["Your resume, matched", "to real jobs.", "Nothing invented."];

const STEPS = [
  ["Resume analyzer", "Reads your resume into one structured profile and scores it the way an applicant tracking system would. A skill with no evidence behind it is left out."],
  ["Job discovery", "Searches licensed job feeds for roles you can win at your level, then removes duplicates, stale postings and recruiter spam."],
  ["Fit scorer", "Scores you against each job on six weighted dimensions and places it in a band. A missing must-have holds the score at 60."],
  ["Resume tailor", "Rewrites your own bullets for the job you pick. A second model then tries to catch it inventing something; if it does twice, you get your original back."],
  ["LinkedIn optimizer", "Writes headlines and an About section to paste in, and lists every mismatch between your resume and your LinkedIn."],
  ["Credentials", "Turns a new certificate into a profile update that you approve. Every later resume and plan then uses it."],
  ["Career coach", "Reads all the fit reports together and names the five actions that would move the most jobs up a band."],
];

const LIMITS = [
  ["It will not invent a claim.", "Every line in a tailored resume traces to a fact in your profile. Code rejects any number, tool or employer that is not already there, before a fact-checking model reads the rest."],
  ["It will not guess your odds.", "You get a match band and the reasons for it, never a percentage chance of being hired. Hiring depends on who else applied, and that is not in the data."],
  ["It will not send anything for you.", "No scraping, no auto-applying, no posting to LinkedIn. The app prepares the text and the PDF. You decide what to submit."],
];

export function Landing() {
  // Smooth scrolling on the landing page only, and only for people who have not asked for
  // reduced motion. Loaded lazily so it stays out of the first paint.
  useEffect(() => {
    if (prefersReducedMotion()) return;
    let stop = () => {};
    import("lenis").then(({ default: Lenis }) => {
      const lenis = new Lenis({ duration: 0.9 });
      let frame = requestAnimationFrame(function raf(time) {
        lenis.raf(time);
        frame = requestAnimationFrame(raf);
      });
      stop = () => {
        cancelAnimationFrame(frame);
        lenis.destroy();
      };
    });
    return () => stop();
  }, []);

  return (
    <div className="mx-auto max-w-6xl px-5 sm:px-8">
      <header className="flex h-16 items-center justify-between">
        <Link href="/" className="font-display text-lg font-semibold">
          CareerPilot
        </Link>
        <nav className="flex items-center gap-1" aria-label="Site">
          <Button asChild variant="ghost" size="sm">
            <Link href="/dashboard">Open the app</Link>
          </Button>
          <ThemeToggle />
        </nav>
      </header>

      <main id="main">
        <section className="grid items-center gap-10 py-10 lg:grid-cols-[1.05fr_1fr] lg:py-20">
          <div>
            <h1 className="text-[2.35rem] font-semibold leading-[1.08] sm:text-5xl xl:text-6xl">
              {HEADLINE.map((line, i) => (
                <span key={line} className="block overflow-hidden pb-1">
                  <motion.span
                    className="block"
                    initial={{ y: "105%", opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    transition={{ duration: 0.6, delay: 0.08 + i * 0.12, ease: [0.2, 0.7, 0.2, 1] }}
                  >
                    {line}
                  </motion.span>
                </span>
              ))}
            </h1>
            <motion.p
              className="mt-6 max-w-[34rem] text-lg leading-relaxed text-muted"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.55 }}
            >
              Seven agents read your resume, find jobs through licensed feeds, score each fit honestly and tailor a
              one-page resume to the job you choose. A fact-checker rejects any claim your resume cannot back.
            </motion.p>
            <motion.div
              className="mt-8 flex flex-wrap gap-3"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.7 }}
            >
              <Button asChild>
                <Link href="/resume">Upload your resume</Link>
              </Button>
              <Button asChild variant="secondary">
                <Link href="/dashboard">Explore the sample profile</Link>
              </Button>
            </motion.div>
            <p className="mt-4 text-sm text-muted">
              Your file is read in memory and never stored. The profile built from it is deleted after 24 hours.
            </p>
          </div>

          <motion.div
            className="card mx-auto w-full max-w-xl p-4 sm:p-6"
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6, delay: 0.35, ease: "easeOut" }}
          >
            <AgentGraph />
          </motion.div>
        </section>

        <section className="border-t border-line py-14" aria-labelledby="steps">
          <h2 id="steps" className="text-2xl font-semibold sm:text-3xl">
            What happens after you upload
          </h2>
          <ol className="mt-8 grid gap-x-10 gap-y-7 md:grid-cols-2">
            {STEPS.map(([name, text], i) => (
              <li key={name} className="flex gap-4">
                <span className="num mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-line-strong text-sm text-muted">
                  {i + 1}
                </span>
                <div>
                  <h3 className="font-semibold">{name}</h3>
                  <p className="mt-1 max-w-[30rem] leading-relaxed text-muted">{text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section className="border-t border-line py-14" aria-labelledby="limits">
          <h2 id="limits" className="text-2xl font-semibold sm:text-3xl">
            Three things it will not do
          </h2>
          <div className="mt-8 grid gap-5 md:grid-cols-3">
            {LIMITS.map(([title, text]) => (
              <div key={title} className="card p-6">
                <h3 className="text-lg font-semibold">{title}</h3>
                <p className="mt-2 leading-relaxed text-muted">{text}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line py-8 text-sm text-muted">
        <span>CareerPilot. Job data from Remotive, Greenhouse boards and JSearch.</span>
        <Link href="/settings" className="underline underline-offset-4 hover:text-fg">
          Privacy and your data
        </Link>
      </footer>
    </div>
  );
}
