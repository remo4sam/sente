import { TransactionTable } from "@/components/transaction-table";
import { AppLayout } from "@/components/layouts/app-layout";
import type { NextPageWithLayout } from "@/lib/page-types";

const TransactionsPage: NextPageWithLayout = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Transactions</h1>
        <p className="mt-2 text-muted-foreground">
          Tap a category badge to correct it. Corrections train the classifier for future
          transactions.
        </p>
      </div>
      <TransactionTable />
    </div>
  );
};

TransactionsPage.getLayout = (page) => <AppLayout>{page}</AppLayout>;

export default TransactionsPage;
