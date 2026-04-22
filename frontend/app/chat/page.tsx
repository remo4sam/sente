import { ChatPanel } from "@/components/chat-panel";

export default function ChatPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Chat</h1>
        <p className="mt-2 text-muted-foreground">
          Ask questions about your transactions in natural language.
        </p>
      </div>
      <ChatPanel />
    </div>
  );
}
