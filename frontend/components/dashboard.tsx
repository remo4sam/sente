"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, TrendingUp, Users } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { formatUgx } from "@/lib/format";
import {
  CATEGORY_COLORS,
  CATEGORY_LABELS,
  type Category,
  type Transaction,
} from "@/lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

// Categories we exclude when computing "real spending" vs "real income".
// Self-transfers are pass-throughs between the user's own accounts and shouldn't
// inflate spending or income totals.
const EXCLUDE_FROM_TOTALS: Category[] = ["self_transfer"];

export function Dashboard() {
  const [rows, setRows] = useState<Transaction[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .transactions({ limit: 1000 })
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  const stats = useMemo(() => computeStats(rows ?? []), [rows]);

  if (error) return <p className="text-destructive">Error: {error}</p>;
  if (!rows) return <p className="text-muted-foreground">Loading…</p>;

  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-dashed p-10 text-center">
        <p className="text-muted-foreground">
          No transactions yet. Head to <span className="font-medium">Upload</span> to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total income"
          value={formatUgx(stats.totalIncome)}
          icon={<ArrowDownRight className="h-4 w-4 text-green-600" />}
          hint={`${stats.incomeCount} transactions`}
        />
        <StatCard
          label="Total spend"
          value={formatUgx(stats.totalSpend)}
          icon={<ArrowUpRight className="h-4 w-4 text-red-600" />}
          hint={`${stats.spendCount} transactions`}
        />
        <StatCard
          label="Net flow"
          value={formatUgx(stats.net)}
          icon={<TrendingUp className="h-4 w-4" />}
          hint="Income − spend (excl. self-transfers)"
        />
        <StatCard
          label="Unique counterparties"
          value={String(stats.uniqueCounterparties)}
          icon={<Users className="h-4 w-4" />}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Spending by category</CardTitle>
            <CardDescription>Debits only, excluding self-transfers.</CardDescription>
          </CardHeader>
          <CardContent>
            {stats.byCategory.length === 0 ? (
              <EmptyChart />
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={stats.byCategory}
                    dataKey="total"
                    nameKey="label"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    innerRadius={50}
                    strokeWidth={2}
                  >
                    {stats.byCategory.map((d) => (
                      <Cell key={d.category} fill={CATEGORY_COLORS[d.category]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number) => formatUgx(value)}
                    contentStyle={{ borderRadius: 8, fontSize: 12 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top recipients</CardTitle>
            <CardDescription>Where your money is going.</CardDescription>
          </CardHeader>
          <CardContent>
            {stats.topRecipients.length === 0 ? (
              <EmptyChart />
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart
                  data={stats.topRecipients}
                  layout="vertical"
                  margin={{ top: 5, right: 16, left: 80, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis type="number" tickFormatter={(v) => formatUgx(v, { compact: true })} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fontSize: 11 }}
                    width={80}
                  />
                  <Tooltip
                    formatter={(value: number) => formatUgx(value)}
                    contentStyle={{ borderRadius: 8, fontSize: 12 }}
                  />
                  <Bar dataKey="total" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Daily cash flow</CardTitle>
          <CardDescription>Net of income and spending per day.</CardDescription>
        </CardHeader>
        <CardContent>
          {stats.byDay.length === 0 ? (
            <EmptyChart />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={stats.byDay}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => formatUgx(v, { compact: true })} tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(value: number) => formatUgx(value)}
                  contentStyle={{ borderRadius: 8, fontSize: 12 }}
                />
                <Line
                  type="monotone"
                  dataKey="income"
                  stroke="#22c55e"
                  strokeWidth={2}
                  dot={false}
                  name="Income"
                />
                <Line
                  type="monotone"
                  dataKey="spend"
                  stroke="#ef4444"
                  strokeWidth={2}
                  dot={false}
                  name="Spend"
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
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
        {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      </CardContent>
    </Card>
  );
}

function EmptyChart() {
  return (
    <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">
      Not enough data yet.
    </div>
  );
}

// ---------- Aggregation ----------

function computeStats(rows: Transaction[]) {
  const spending = rows.filter(
    (r) => r.direction === "out" && !EXCLUDE_FROM_TOTALS.includes(r.category)
  );
  const income = rows.filter(
    (r) => r.direction === "in" && !EXCLUDE_FROM_TOTALS.includes(r.category)
  );

  const totalSpend = spending.reduce((s, r) => s + r.amount, 0);
  const totalIncome = income.reduce((s, r) => s + r.amount, 0);
  const net = totalIncome - totalSpend;

  const counterparties = new Set<string>();
  for (const r of rows) {
    if (r.counterparty_name) counterparties.add(r.counterparty_name);
    else if (r.counterparty_number) counterparties.add(r.counterparty_number);
  }

  // Category breakdown (spend only)
  const categoryMap = new Map<Category, number>();
  for (const r of spending) {
    categoryMap.set(r.category, (categoryMap.get(r.category) ?? 0) + r.amount);
  }
  const byCategory = Array.from(categoryMap.entries())
    .map(([category, total]) => ({ category, label: CATEGORY_LABELS[category], total }))
    .sort((a, b) => b.total - a.total);

  // Top recipients (spend only, must have a name)
  const recipientMap = new Map<string, number>();
  for (const r of spending) {
    const name = r.counterparty_name ?? r.counterparty_number;
    if (!name) continue;
    recipientMap.set(name, (recipientMap.get(name) ?? 0) + r.amount);
  }
  const topRecipients = Array.from(recipientMap.entries())
    .map(([name, total]) => ({ name: truncate(name, 18), total }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 8);

  // Daily cash flow
  const dayMap = new Map<string, { income: number; spend: number }>();
  for (const r of rows) {
    if (EXCLUDE_FROM_TOTALS.includes(r.category)) continue;
    const day = r.timestamp.slice(0, 10); // YYYY-MM-DD
    const entry = dayMap.get(day) ?? { income: 0, spend: 0 };
    if (r.direction === "in") entry.income += r.amount;
    else entry.spend += r.amount;
    dayMap.set(day, entry);
  }
  const byDay = Array.from(dayMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, v]) => ({ date: date.slice(5), ...v })); // MM-DD for axis

  return {
    totalIncome,
    totalSpend,
    net,
    incomeCount: income.length,
    spendCount: spending.length,
    uniqueCounterparties: counterparties.size,
    byCategory,
    topRecipients,
    byDay,
  };
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}
