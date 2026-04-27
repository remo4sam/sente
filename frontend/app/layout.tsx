import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Fraunces, Geist, JetBrains_Mono } from "next/font/google";
import { AppNav } from "@/components/app-nav";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-fraunces",
  style: ["normal", "italic"],
  axes: ["SOFT", "WONK", "opsz"],
});

const geist = Geist({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-geist",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Sente — Mobile Money Insights",
  description: "AI-powered analyzer for Ugandan mobile money transactions.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider dynamic>
      <html
        lang="en"
        className={`${fraunces.variable} ${geist.variable} ${jetbrains.variable}`}
      >
        <body className="min-h-screen bg-background font-sans text-foreground antialiased">
          <div className="flex min-h-screen">
            <AppNav />
            <main className="flex-1 overflow-x-hidden">
              <div className="mx-auto max-w-6xl px-8 py-10">{children}</div>
            </main>
          </div>
        </body>
      </html>
    </ClerkProvider>
  );
}
