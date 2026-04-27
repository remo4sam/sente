"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ClerkProvider as BaseClerkProvider } from "@clerk/clerk-react";
import { Kingfisher } from "@/components/kingfisher";

const PUBLISHABLE_KEY = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ?? "";

function PaperLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-paper">
      <div className="flex items-center gap-3 text-stone">
        <Kingfisher size={22} />
        <span className="text-xs uppercase tracking-[0.25em]">Loading…</span>
      </div>
    </div>
  );
}

export function ClerkProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Static export prerenders this tree at build time, where the publishable
  // key isn't validated and Clerk hooks would throw without a provider. We
  // defer the entire interactive tree to client mount.
  if (!mounted) return <PaperLoader />;

  if (!PUBLISHABLE_KEY) {
    console.error(
      "Missing NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY — set it in .env.local",
    );
    return <PaperLoader />;
  }

  return (
    <BaseClerkProvider
      publishableKey={PUBLISHABLE_KEY}
      routerPush={(to) => router.push(to)}
      routerReplace={(to) => router.replace(to)}
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
      signInFallbackRedirectUrl="/dashboard"
      signUpFallbackRedirectUrl="/dashboard"
      afterSignOutUrl="/"
    >
      {children}
    </BaseClerkProvider>
  );
}
