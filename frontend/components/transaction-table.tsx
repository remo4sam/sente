"use client";

import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { api } from "@/lib/api";
import { formatDateTime, formatSignedUgx } from "@/lib/format";
import { CATEGORY_LABELS, type Category, type Transaction } from "@/lib/types";
import { CategoryBadge } from "@/components/category-badge";
import { Select } from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const ALL_CATEGORIES = Object.keys(CATEGORY_LABELS) as Category[];

export function TransactionTable() {
  const [rows, setRows] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .transactions({ limit: 200 })
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function correct(row: Transaction, category: Category) {
    const previous = row.category;
    // Optimistic update
    setRows((prev) =>
      prev.map((r) =>
        r.id === row.id
          ? { ...r, category, category_confidence: 1.0, user_corrected: true }
          : r
      )
    );
    try {
      await api.correctCategory(row.id, category);
    } catch (e) {
      // Roll back on failure
      setRows((prev) =>
        prev.map((r) => (r.id === row.id ? { ...r, category: previous } : r))
      );
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setEditingId(null);
    }
  }

  if (loading) return <p className="text-muted-foreground">Loading transactions…</p>;
  if (error) return <p className="text-destructive">Error: {error}</p>;
  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-dashed p-8 text-center">
        <p className="text-muted-foreground">
          No transactions yet. Upload a statement or paste SMS messages to get started.
        </p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Date</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Counterparty</TableHead>
          <TableHead className="text-right">Amount</TableHead>
          <TableHead>Category</TableHead>
          <TableHead>Network</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.id}>
            <TableCell className="whitespace-nowrap text-muted-foreground">
              {formatDateTime(row.timestamp)}
            </TableCell>
            <TableCell className="font-medium capitalize">{row.type.replaceAll("_", " ")}</TableCell>
            <TableCell>
              {row.counterparty_name ?? (
                <span className="text-muted-foreground">
                  {row.counterparty_number ?? "—"}
                </span>
              )}
            </TableCell>
            <TableCell
              className={`text-right font-mono ${
                row.direction === "in" ? "text-green-600" : "text-foreground"
              }`}
            >
              {formatSignedUgx(row.amount, row.direction)}
            </TableCell>
            <TableCell>
              {editingId === row.id ? (
                <div className="flex items-center gap-2">
                  <Select
                    value={row.category}
                    onChange={(e) => correct(row, e.target.value as Category)}
                    autoFocus
                    onBlur={() => setEditingId(null)}
                  >
                    {ALL_CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {CATEGORY_LABELS[c]}
                      </option>
                    ))}
                  </Select>
                </div>
              ) : (
                <button
                  onClick={() => setEditingId(row.id)}
                  className="inline-flex items-center gap-2 rounded-md px-1 hover:bg-accent"
                  title={
                    row.user_corrected
                      ? "Corrected by you"
                      : `Auto-classified (confidence ${(row.category_confidence * 100).toFixed(0)}%)`
                  }
                >
                  <CategoryBadge category={row.category} />
                  {row.user_corrected && <Check className="h-3 w-3 text-green-600" />}
                </button>
              )}
            </TableCell>
            <TableCell className="text-muted-foreground">{row.network}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
