"use client";

import { useEffect, useState } from "react";
import { Activity, AlertCircle, Clock, Coins, Cpu } from "lucide-react";
import { api } from "@/lib/api";
import type { MetricsResponse, OpMetrics } from "@/lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const REFRESH_MS = 5000;

export function MetricsView() {
  const [data, setData] = useState<MetricsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      api
        .metrics()
        .then((d) => {
          if (!cancelled) {
            setData(d);
            setError(null);
          }
        })
        .catch((e) => {
          if (!cancelled) setError(e instanceof Error ? e.message : String(e));
        });
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (error && !data) return <p className="text-destructive">Error: {error}</p>;
  if (!data) return <p className="text-muted-foreground">Loading…</p>;

  const ops = Object.values(data.llm.ops).sort((a, b) => a.op.localeCompare(b.op));
  const totalCalls = ops.reduce((s, o) => s + o.calls, 0);
  const totalFailures = ops.reduce((s, o) => s + o.failures, 0);
  const totalInputTokens = ops.reduce((s, o) => s + o.input_tokens, 0);
  const totalOutputTokens = ops.reduce((s, o) => s + o.output_tokens, 0);
  const distinctModels = new Set<string>();
  for (const op of ops) for (const m of op.models) distinctModels.add(m.model);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total cost"
          value={formatUsd(data.llm.total_cost_usd)}
          icon={<Coins className="h-4 w-4 text-amber-600" />}
          hint={`${formatTokens(totalInputTokens + totalOutputTokens)} tokens`}
        />
        <StatCard
          label="Total calls"
          value={String(totalCalls)}
          icon={<Activity className="h-4 w-4" />}
          hint={
            totalFailures > 0
              ? `${totalFailures} failure${totalFailures === 1 ? "" : "s"}`
              : "no failures"
          }
        />
        <StatCard
          label="Models in use"
          value={String(distinctModels.size)}
          icon={<Cpu className="h-4 w-4" />}
          hint={
            distinctModels.size > 0
              ? Array.from(distinctModels).map(shortModel).join(", ")
              : undefined
          }
        />
        <StatCard
          label="In / out tokens"
          value={`${formatTokens(totalInputTokens)} / ${formatTokens(totalOutputTokens)}`}
          icon={<Clock className="h-4 w-4" />}
        />
      </div>

      {ops.length === 0 ? (
        <div className="rounded-md border border-dashed p-10 text-center">
          <p className="text-muted-foreground">
            No LLM calls recorded yet. Ingest a message or open the chat to see metrics here.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {ops.map((op) => (
            <OpCard key={op.op} op={op} />
          ))}
        </div>
      )}

      {error && (
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <AlertCircle className="h-3 w-3" />
          Last refresh failed: {error}. Showing cached data.
        </p>
      )}
    </div>
  );
}

function OpCard({ op }: { op: OpMetrics }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="capitalize">{op.op}</CardTitle>
          <span className="text-sm font-mono text-muted-foreground">
            {formatUsd(op.cost_usd)}
          </span>
        </div>
        <CardDescription>
          {op.calls} call{op.calls === 1 ? "" : "s"} ·{" "}
          {(op.success_rate * 100).toFixed(1)}% success · p50 {op.p50_latency_ms}ms · p95{" "}
          {op.p95_latency_ms}ms
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Model</TableHead>
              <TableHead className="text-right">Calls</TableHead>
              <TableHead className="text-right">Input tokens</TableHead>
              <TableHead className="text-right">Output tokens</TableHead>
              <TableHead className="text-right">Cost</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {op.models.map((m) => (
              <TableRow key={m.model}>
                <TableCell className="font-mono text-xs">{m.model}</TableCell>
                <TableCell className="text-right">{m.calls}</TableCell>
                <TableCell className="text-right">{formatTokens(m.input_tokens)}</TableCell>
                <TableCell className="text-right">{formatTokens(m.output_tokens)}</TableCell>
                <TableCell className="text-right font-mono">{formatUsd(m.cost_usd)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function StatCard({
  label,
  value,
  icon,
  hint,
}: {
  label: string;
  value: string;
  icon?: React.ReactNode;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">{label}</p>
          {icon}
        </div>
        <p className="mt-2 text-2xl font-bold">{value}</p>
        {hint && <p className="mt-1 truncate text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

function formatUsd(n: number): string {
  if (n === 0) return "$0.00";
  if (n < 0.01) return `$${n.toFixed(6)}`;
  if (n < 1) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

// Trim a dated model snapshot ("claude-haiku-4-5-20251001") down to its family
// for compact display in summary chips.
function shortModel(m: string): string {
  return m.replace(/-\d{8}$/, "");
}
