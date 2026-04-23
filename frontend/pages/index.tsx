import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  MessageSquare,
  Sparkles,
  Upload,
} from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { MarketingLayout } from "@/components/layouts/marketing-layout";
import type { NextPageWithLayout } from "@/lib/page-types";

const HomePage: NextPageWithLayout = () => {
  return (
    <div className="space-y-12">
      <section className="space-y-5 pt-4">
        <div className="inline-flex items-center gap-2 rounded-full border bg-muted/50 px-3 py-1 text-xs text-muted-foreground">
          <Sparkles className="h-3 w-3" />
          AI-powered mobile money insights
        </div>
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          Make sense of your mobile money.
        </h1>
        <p className="max-w-2xl text-lg text-muted-foreground">
          Sente parses your Airtel and MTN transactions from SMS and PDF statements,
          categorizes them automatically, and lets you explore the results in charts
          or by chatting with an agent that reads your ledger.
        </p>
        <div className="flex flex-wrap gap-3 pt-2">
          <Link href="/upload" className={buttonVariants({ size: "lg" })}>
            Upload transactions
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
          <Link
            href="/dashboard"
            className={buttonVariants({ size: "lg", variant: "outline" })}
          >
            View dashboard
          </Link>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <FeatureCard
          icon={<Upload className="h-5 w-5" />}
          title="Ingest SMS and PDFs"
          description="Paste transaction SMS or upload Airtel statements. A regex-first parser handles known templates; anything new falls through to Claude Haiku."
          href="/upload"
          cta="Start ingesting"
        />
        <FeatureCard
          icon={<BarChart3 className="h-5 w-5" />}
          title="Dashboards that respect reality"
          description="Spending by category, top recipients, and daily cash flow — with self-transfers correctly excluded so your totals match the statement."
          href="/dashboard"
          cta="Open dashboard"
        />
        <FeatureCard
          icon={<MessageSquare className="h-5 w-5" />}
          title="Chat with your ledger"
          description="Ask natural-language questions. The agent queries your transactions through typed tools and only sees the rows it explicitly asks for."
          href="/chat"
          cta="Open chat"
        />
      </section>

      <section className="rounded-lg border bg-muted/30 p-6 sm:p-8">
        <h2 className="text-xl font-semibold tracking-tight">How it works</h2>
        <ol className="mt-4 space-y-3 text-sm text-muted-foreground">
          <Step n={1}>
            <span className="font-medium text-foreground">Ingest.</span>{" "}
            Drop in SMS text or an Airtel PDF statement. Records are deduped by transaction ID
            across sources.
          </Step>
          <Step n={2}>
            <span className="font-medium text-foreground">Categorize.</span>{" "}
            Zero-shot classification seeds the system; your corrections are embedded and
            retrieved as few-shot examples next time.
          </Step>
          <Step n={3}>
            <span className="font-medium text-foreground">Explore.</span>{" "}
            Use the dashboard for a visual overview, or ask the chat agent for anything
            else — trends, top counterparties, category breakdowns.
          </Step>
        </ol>
      </section>
    </div>
  );
};

HomePage.getLayout = (page) => <MarketingLayout>{page}</MarketingLayout>;

export default HomePage;

function FeatureCard({
  icon,
  title,
  description,
  href,
  cta,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  href: string;
  cta: string;
}) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-md bg-primary/10 text-primary">
          {icon}
        </div>
        <CardTitle className="text-lg">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="mt-auto">
        <Link
          href={href}
          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          {cta}
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </CardContent>
    </Card>
  );
}

function Step({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
        {n}
      </span>
      <span>{children}</span>
    </li>
  );
}
