import { Dashboard } from "@/components/dashboard";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-2 text-muted-foreground">
          Overview of your mobile money activity.
        </p>
      </div>
      <Dashboard />
    </div>
  );
}
