import { UploadForm } from "@/components/upload-form";
import { AppLayout } from "@/components/layouts/app-layout";
import type { NextPageWithLayout } from "@/lib/page-types";

const UploadPage: NextPageWithLayout = () => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Ingest transactions</h1>
        <p className="mt-2 text-muted-foreground">
          Upload an Airtel Money statement or paste SMS messages to get started.
        </p>
      </div>
      <UploadForm />
    </div>
  );
};

UploadPage.getLayout = (page) => <AppLayout>{page}</AppLayout>;

export default UploadPage;
