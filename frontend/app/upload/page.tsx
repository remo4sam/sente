import { UploadForm } from "@/components/upload-form";

export default function UploadPage() {
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
}
