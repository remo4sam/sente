import { Dashboard } from "@/components/dashboard";
import { AppLayout } from "@/components/layouts/app-layout";
import type { NextPageWithLayout } from "@/lib/page-types";

const DashboardPage: NextPageWithLayout = () => {
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
};

DashboardPage.getLayout = (page) => <AppLayout>{page}</AppLayout>;

export default DashboardPage;
