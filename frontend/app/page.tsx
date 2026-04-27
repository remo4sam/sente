"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/clerk-react";
import { Kingfisher } from "@/components/kingfisher";

const FEATURES = [
  {
    n: "01",
    title: "SMS, parsed",
    body: "Templates handle every common Airtel and MTN message. Anything unusual quietly falls through to Claude Haiku, so nothing is ever dropped.",
    tag: "Hybrid parser",
  },
  {
    n: "02",
    title: "Categories that learn",
    body: "Every correction you make becomes a few-shot example for the next classification. The model starts to sound like you in a week or two.",
    tag: "Embedded retrieval",
  },
  {
    n: "03",
    title: "Ask in plain English",
    body: "“How much did I send to mum last quarter?” The agent owns the loop server-side and only sees rows it explicitly asks for.",
    tag: "Tool-use loop",
  },
  {
    n: "04",
    title: "SMS and PDF, reconciled",
    body: "Upload a statement and import the receipts. Sente merges them by transaction ID and keeps the best fields from each side.",
    tag: "Multi-source ingestion",
  },
];

export default function LandingPage() {
  const router = useRouter();
  const { isLoaded, isSignedIn } = useAuth();
  useEffect(() => {
    if (isLoaded && isSignedIn) router.replace("/dashboard");
  }, [isLoaded, isSignedIn, router]);

  return (
    <div className="-mx-8 -my-10 min-h-screen bg-paper text-ink">
      {/* Top banner — date stamp + nav, like a masthead */}
      <header className="border-b border-ink/15">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-8 py-5">
          <Link href="/" className="flex items-center gap-3">
            <Kingfisher size={32} />
            <span className="font-display text-2xl font-medium tracking-tight">
              Sente
            </span>
          </Link>
          <span className="hidden text-xs uppercase tracking-[0.2em] text-stone md:inline">
            Vol. I &nbsp;·&nbsp; Kampala &nbsp;·&nbsp; 2026
          </span>
          <div className="flex items-center gap-2">
            <Link
              href="/sign-in"
              className="rounded-full px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-ink/5"
            >
              Sign in
            </Link>
            <Link
              href="/sign-up"
              className="group inline-flex items-center gap-2 rounded-full bg-leaf px-4 py-2 text-sm font-medium text-paper transition-colors hover:bg-ink"
            >
              Get started
              <span aria-hidden className="transition-transform group-hover:translate-x-0.5">
                →
              </span>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative">
        <div className="mx-auto grid max-w-6xl gap-10 px-8 pt-24 pb-20 md:grid-cols-12">
          <div className="md:col-span-8">
            <p className="mb-8 text-xs uppercase tracking-[0.3em] text-kingfisher animate-fade-up">
              An almanac for mobile money
            </p>
            <h1 className="font-display text-[clamp(3rem,8vw,7.5rem)] font-light leading-[0.95] animate-fade-up [animation-delay:80ms]">
              Make{" "}
              <span className="font-display-italic font-medium text-leaf">
                sense
              </span>{" "}
              of your <br className="hidden md:block" />
              mobile money.
            </h1>
            <p className="mt-8 max-w-xl text-lg leading-relaxed text-ink/75 animate-fade-up [animation-delay:160ms]">
              Sente turns the daily torrent of Airtel and MTN messages and
              statements into a clear picture of where your money goes — with
              categorization that learns from your corrections and a chat
              agent that answers in plain English.
            </p>
            <div className="mt-10 flex flex-wrap items-center gap-4 animate-fade-up [animation-delay:240ms]">
              <Link
                href="/sign-up"
                className="group inline-flex items-center gap-3 rounded-full bg-ink px-6 py-3 text-sm font-medium text-paper transition-colors hover:bg-leaf"
              >
                Create an account
                <span aria-hidden className="transition-transform group-hover:translate-x-1">
                  →
                </span>
              </Link>
              <Link
                href="/sign-in"
                className="text-sm font-medium underline decoration-ink/30 underline-offset-[6px] transition-colors hover:decoration-ink"
              >
                I already have one
              </Link>
            </div>
          </div>

          {/* Right column — index card with running ledger */}
          <aside className="md:col-span-4 animate-fade-up [animation-delay:320ms]">
            <div className="ink-shadow rounded-md border border-ink/15 bg-card/60 p-6">
              <div className="flex items-baseline justify-between border-b border-ink/15 pb-3">
                <span className="text-xs uppercase tracking-[0.2em] text-stone">
                  Specimen ledger
                </span>
                <span className="font-mono-num text-xs text-stone">UGX</span>
              </div>
              <ul className="mt-3 space-y-3 text-sm">
                {[
                  { label: "Boda · Kololo → Bugolobi", amt: "−6,000", cat: "Transport" },
                  { label: "Café Javas", amt: "−42,500", cat: "Food" },
                  { label: "Salary · Apr", amt: "+2,800,000", cat: "Income", pos: true },
                  { label: "Mum", amt: "−150,000", cat: "Family" },
                  { label: "Yaka top-up", amt: "−80,000", cat: "Utilities" },
                ].map((row) => (
                  <li key={row.label} className="flex items-baseline justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate">{row.label}</p>
                      <p className="text-xs text-stone">{row.cat}</p>
                    </div>
                    <span
                      className={`font-mono-num text-sm ${row.pos ? "text-leaf" : "text-ink"}`}
                    >
                      {row.amt}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-5 border-t border-ink/15 pt-3 text-xs italic text-stone">
                Real categories, real shapes. No data leaves your account.
              </p>
            </div>
          </aside>
        </div>
      </section>

      {/* Features as numbered index */}
      <section className="border-t-2 border-ink">
        <div className="mx-auto max-w-6xl px-8 py-20">
          <div className="mb-12 flex items-baseline justify-between border-b border-ink/15 pb-3">
            <h2 className="font-display text-3xl font-light">
              What's <span className="font-display-italic text-leaf">inside</span>
            </h2>
            <span className="text-xs uppercase tracking-[0.2em] text-stone">
              §1 — Capabilities
            </span>
          </div>
          <ol className="grid gap-x-12">
            {FEATURES.map((f) => (
              <li
                key={f.n}
                className="grid grid-cols-12 items-baseline gap-6 border-b border-ink/15 py-8 transition-colors last:border-b-0 hover:bg-ink/[0.025]"
              >
                <span className="col-span-2 font-mono-num text-sm text-stone md:col-span-1">
                  {f.n}
                </span>
                <h3 className="col-span-10 font-display text-2xl font-medium md:col-span-3">
                  {f.title}
                </h3>
                <p className="col-span-12 text-base leading-relaxed text-ink/80 md:col-span-6">
                  {f.body}
                </p>
                <span className="col-span-12 inline-flex items-center justify-self-start rounded-full bg-lime/40 px-3 py-1 text-xs font-medium text-ink md:col-span-2 md:justify-self-end">
                  {f.tag}
                </span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Closing strip — kingfisher motif */}
      <section className="bg-leaf text-paper">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-8 px-8 py-20 md:flex-row md:items-end md:justify-between">
          <div className="max-w-xl">
            <p className="text-xs uppercase tracking-[0.3em] text-peach">
              The name
            </p>
            <p className="mt-4 font-display text-4xl font-light leading-tight">
              <span className="font-display-italic font-medium">Sente</span> is
              Luganda for money — small change, the kind that disappears
              between messages.
            </p>
          </div>
          <Link
            href="/sign-up"
            className="group inline-flex items-center gap-3 rounded-full bg-paper px-6 py-3 text-sm font-medium text-ink transition-transform hover:-translate-y-0.5"
          >
            Open the ledger
            <span aria-hidden className="transition-transform group-hover:translate-x-1">
              →
            </span>
          </Link>
        </div>
      </section>

      <footer className="border-t border-ink/15">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-2 px-8 py-6 text-xs text-stone md:flex-row md:items-center">
          <span className="flex items-center gap-2">
            <Kingfisher size={18} />
            Sente · Built in Kampala
          </span>
          <span className="uppercase tracking-[0.2em]">
            Airtel today &nbsp;·&nbsp; MTN soon
          </span>
        </div>
      </footer>
    </div>
  );
}
