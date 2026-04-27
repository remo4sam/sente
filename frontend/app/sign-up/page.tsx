"use client";

import Link from "next/link";
import { SignUp } from "@clerk/clerk-react";
import { ClientOnly } from "@/components/client-only";
import { Kingfisher } from "@/components/kingfisher";

export default function Page() {
  return (
    <div className="-mx-8 -my-10 flex min-h-screen flex-col bg-paper">
      <header className="border-b border-ink/15">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-8 py-5">
          <Link href="/" className="flex items-center gap-3">
            <Kingfisher size={28} />
            <span className="font-display text-xl font-medium tracking-tight">
              Sente
            </span>
          </Link>
          <Link
            href="/sign-in"
            className="text-sm font-medium underline decoration-ink/30 underline-offset-[6px] hover:decoration-ink"
          >
            I already have an account
          </Link>
        </div>
      </header>
      <div className="flex flex-1 items-center justify-center px-8 py-16">
        <div className="w-full max-w-md">
          <p className="mb-3 text-xs uppercase tracking-[0.3em] text-kingfisher">
            New here
          </p>
          <h1 className="mb-8 font-display text-4xl font-light leading-tight">
            Start your <span className="font-display-italic font-medium text-leaf">almanac</span>.
          </h1>
          <ClientOnly>
            <SignUp routing="hash" />
          </ClientOnly>
        </div>
      </div>
    </div>
  );
}
