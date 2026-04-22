"use client";

import { useState } from "react";
import { FileText, Upload as UploadIcon } from "lucide-react";
import { api } from "@/lib/api";
import type { IngestResponse } from "@/lib/types";
import { formatUgx } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

type Mode = "pdf" | "text";

export function UploadForm() {
  const [mode, setMode] = useState<Mode>("pdf");
  const [file, setFile] = useState<File | null>(null);
  const [textInput, setTextInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    setResult(null);
    setSubmitting(true);
    try {
      if (mode === "pdf") {
        if (!file) {
          setError("Pick a PDF file first.");
          return;
        }
        const r = await api.ingestPdf(file);
        setResult(r);
      } else {
        const messages = textInput
          .split("\n")
          .map((m) => m.trim())
          .filter(Boolean);
        if (messages.length === 0) {
          setError("Paste at least one SMS message.");
          return;
        }
        const r = await api.ingestText(messages);
        setResult(r);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        <Button
          variant={mode === "pdf" ? "default" : "outline"}
          onClick={() => setMode("pdf")}
          size="sm"
        >
          <FileText className="h-4 w-4" />
          PDF statement
        </Button>
        <Button
          variant={mode === "text" ? "default" : "outline"}
          onClick={() => setMode("text")}
          size="sm"
        >
          <UploadIcon className="h-4 w-4" />
          Paste SMS messages
        </Button>
      </div>

      {mode === "pdf" ? (
        <Card>
          <CardHeader>
            <CardTitle>Airtel Money statement (PDF)</CardTitle>
            <CardDescription>
              Download a statement from the Airtel Money app or USSD and upload it here.
              Transactions are matched to any existing records by transaction ID.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <input
              type="file"
              accept="application/pdf"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm file:mr-4 file:rounded-md file:border-0 file:bg-primary file:px-4 file:py-2 file:text-sm file:font-medium file:text-primary-foreground hover:file:bg-primary/90"
            />
            {file && (
              <p className="text-sm text-muted-foreground">
                Selected: {file.name} ({Math.round(file.size / 1024)} KB)
              </p>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Paste SMS messages</CardTitle>
            <CardDescription>
              One message per line. Works with Airtel Money SMS formats; MTN support is in progress.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder="CASH DEPOSIT of UGX 200,000 from SC BANK..."
              rows={8}
            />
          </CardContent>
        </Card>
      )}

      <div className="flex items-center gap-3">
        <Button onClick={submit} disabled={submitting}>
          {submitting ? "Processing…" : "Ingest"}
        </Button>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>

      {result && <IngestResult result={result} />}
    </div>
  );
}

function IngestResult({ result }: { result: IngestResponse }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Ingest complete</CardTitle>
        {result.customer_name && (
          <CardDescription>
            {result.customer_name}
            {result.period_start && result.period_end
              ? ` · ${new Date(result.period_start).toLocaleDateString()} – ${new Date(result.period_end).toLocaleDateString()}`
              : null}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <Stat label="Parsed" value={result.parsed} />
          <Stat label="Inserted" value={result.inserted} />
          <Stat label="Merged" value={result.merged} />
          <Stat label="Unchanged" value={result.skipped_no_change} />
          {result.statement_total_credit != null && (
            <Stat label="Total credit" value={formatUgx(result.statement_total_credit)} />
          )}
          {result.statement_total_debit != null && (
            <Stat label="Total debit" value={formatUgx(result.statement_total_debit)} />
          )}
        </dl>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-lg font-semibold">{value}</dd>
    </div>
  );
}
