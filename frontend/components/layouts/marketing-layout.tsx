import Link from "next/link";
import { SignedIn, SignedOut, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import { buttonVariants } from "@/components/ui/button";

export function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <Link href="/" className="flex items-baseline gap-2">
            <span className="text-xl font-bold tracking-tight">Sente</span>
            <span className="hidden text-xs text-muted-foreground sm:inline">
              mobile money insights
            </span>
          </Link>
          <nav className="flex items-center gap-2">
            <SignedOut>
              <SignInButton mode="modal">
                <button className={buttonVariants({ variant: "ghost", size: "sm" })}>
                  Sign in
                </button>
              </SignInButton>
              <SignUpButton mode="modal">
                <button className={buttonVariants({ size: "sm" })}>Sign up</button>
              </SignUpButton>
            </SignedOut>
            <SignedIn>
              <Link href="/dashboard" className={buttonVariants({ size: "sm" })}>
                Go to app
              </Link>
              <UserButton />
            </SignedIn>
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <div className="mx-auto max-w-6xl px-6 py-12">{children}</div>
      </main>
    </div>
  );
}
