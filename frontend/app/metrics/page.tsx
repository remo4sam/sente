import { MetricsView } from "@/components/metrics-view";

export default function MetricsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Metrics</h1>
        <p className="mt-2 text-muted-foreground">
          Live LLM call metrics — models used, token consumption, and cost. Auto-refreshes every
          5 seconds.
        </p>
      </div>
      <MetricsView />
    </div>
  );
}
