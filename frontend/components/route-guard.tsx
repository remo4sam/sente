"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@clerk/clerk-react";
import { Kingfisher } from "@/components/kingfisher";

const PUBLIC_PATHS = ["/", "/sign-in", "/sign-up"];

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + "/"),
  );
}

export function RouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isLoaded, isSignedIn } = useAuth();
  const publicPath = isPublic(pathname);

  useEffect(() => {
    if (!isLoaded) return;
    if (!publicPath && !isSignedIn) {
      const next = encodeURIComponent(pathname);
      router.replace(`/sign-in?redirect_url=${next}`);
    }
  }, [isLoaded, isSignedIn, publicPath, pathname, router]);

  // Public routes always render. Protected routes wait for auth state, then
  // either render (signed in) or render nothing while redirecting.
  if (publicPath) return <>{children}</>;
  if (!isLoaded || !isSignedIn) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex items-center gap-3 text-stone">
          <Kingfisher size={20} />
          <span className="text-xs uppercase tracking-[0.25em]">Loading…</span>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
