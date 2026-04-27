"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton, useUser } from "@clerk/clerk-react";
import { Activity, BarChart3, MessageSquare, Receipt, Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import { Kingfisher } from "@/components/kingfisher";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: BarChart3, n: "01" },
  { href: "/upload", label: "Upload", icon: Upload, n: "02" },
  { href: "/transactions", label: "Transactions", icon: Receipt, n: "03" },
  { href: "/chat", label: "Chat", icon: MessageSquare, n: "04" },
  { href: "/metrics", label: "Metrics", icon: Activity, n: "05" },
];

export function AppNav() {
  const pathname = usePathname();
  const { isLoaded, isSignedIn, user } = useUser();
  if (
    pathname === "/" ||
    pathname.startsWith("/sign-in") ||
    pathname.startsWith("/sign-up")
  ) {
    return null;
  }
  return (
    <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col bg-leaf text-paper">
      {/* Wordmark */}
      <div className="flex items-center gap-3 px-6 py-7">
        <Kingfisher size={30} />
        <div className="flex flex-col leading-none">
          <span className="font-display text-2xl font-medium tracking-tight">
            Sente
          </span>
          <span className="mt-1 text-[10px] uppercase tracking-[0.25em] text-paper/60">
            mobile money
          </span>
        </div>
      </div>

      <div className="mx-6 border-t border-paper/15" />

      {/* Section heading */}
      <p className="mt-6 px-6 text-[10px] uppercase tracking-[0.25em] text-paper/50">
        §1 — Workspace
      </p>

      {/* Nav */}
      <nav className="mt-3 flex flex-1 flex-col gap-0.5 px-3">
        {NAV.map(({ href, label, icon: Icon, n }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "group relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors",
                active
                  ? "bg-paper/[0.08] text-paper"
                  : "text-paper/70 hover:bg-paper/[0.04] hover:text-paper"
              )}
            >
              {/* lime accent on active */}
              <span
                aria-hidden
                className={cn(
                  "absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r bg-lime transition-opacity",
                  active ? "opacity-100" : "opacity-0"
                )}
              />
              <span className="font-mono-num w-6 text-[10px] text-paper/40">
                {n}
              </span>
              <Icon className="h-4 w-4" />
              <span className="font-medium">{label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Account footer */}
      <div className="mx-6 border-t border-paper/15" />
      {isLoaded && isSignedIn && (
        <div className="flex items-center gap-3 px-6 py-5">
          <UserButton
            appearance={{
              elements: {
                avatarBox: "h-9 w-9 ring-1 ring-paper/20",
              },
            }}
          />
          <div className="min-w-0 flex-1 leading-tight">
            <p className="truncate text-sm font-medium text-paper">
              {user?.firstName ?? user?.username ?? "Signed in"}
            </p>
            <p className="truncate text-[11px] text-paper/55">
              {user?.primaryEmailAddress?.emailAddress}
            </p>
          </div>
        </div>
      )}
    </aside>
  );
}
