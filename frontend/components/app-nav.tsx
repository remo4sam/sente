import Link from "next/link";
import { useRouter } from "next/router";
import { UserButton } from "@clerk/nextjs";
import { BarChart3, MessageSquare, Receipt, Upload } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/transactions", label: "Transactions", icon: Receipt },
  { href: "/chat", label: "Chat", icon: MessageSquare },
];

export function AppNav() {
  const { pathname } = useRouter();
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r bg-muted/30 px-4 py-6">
      <div className="mb-8 px-2">
        <Link href="/" className="flex items-baseline gap-2">
          <span className="text-2xl font-bold tracking-tight">Sente</span>
          <span className="text-xs text-muted-foreground">mobile money insights</span>
        </Link>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto flex items-center gap-3 border-t px-2 pt-4">
        <UserButton />
        <span className="text-xs text-muted-foreground">Account</span>
      </div>
    </aside>
  );
}
