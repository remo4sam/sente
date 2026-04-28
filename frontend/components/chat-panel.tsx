"use client";

import { useRef, useState } from "react";
import { Send, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import type { ChatToolTrace, ChatTurn } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Markdown } from "@/components/markdown";

interface Message extends ChatTurn {
  trace?: ChatToolTrace[];
}

const SUGGESTED = [
  "How much did I spend last month?",
  "Who did I send the most money to?",
  "What's my biggest spending category?",
  "Show me all airtime purchases this month",
];

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  async function send(text: string) {
    const userTurn: Message = { role: "user", content: text };
    const history = [...messages, userTurn];
    setMessages(history);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const res = await api.chat(history.map(({ role, content }) => ({ role, content })));
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, trace: res.trace },
      ]);
      // Scroll after paint
      setTimeout(() => scrollRef.current?.scrollTo({ top: 99999, behavior: "smooth" }), 50);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || loading) return;
    send(trimmed);
  }

  return (
    <div className="flex h-[calc(100vh-12rem)] flex-col rounded-lg border bg-card">
      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-6">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-4">
            <p className="text-muted-foreground">Ask anything about your transactions.</p>
            <div className="grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-2">
              {SUGGESTED.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="rounded-md border px-3 py-2 text-left text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="h-2 w-2 animate-pulse rounded-full bg-muted-foreground" />
            Thinking…
          </div>
        )}

        {error && <p className="text-sm text-destructive">Error: {error}</p>}
      </div>

      <form onSubmit={onSubmit} className="flex gap-2 border-t p-4">
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your transactions…"
          disabled={loading}
        />
        <Button type="submit" disabled={loading || !input.trim()}>
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[80%] space-y-2 ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`rounded-lg px-4 py-2 text-sm ${
            isUser ? "bg-primary text-primary-foreground" : "bg-muted"
          }`}
        >
          {isUser ? message.content : <Markdown>{message.content}</Markdown>}
        </div>
        {message.trace && message.trace.length > 0 && <ToolTrace trace={message.trace} />}
      </div>
    </div>
  );
}

function ToolTrace({ trace }: { trace: ChatToolTrace[] }) {
  const [open, setOpen] = useState(false);
  return (
    <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground hover:text-foreground">
        <Wrench className="h-3 w-3" />
        {trace.length} tool call{trace.length === 1 ? "" : "s"}
      </summary>
      <div className="mt-2 space-y-2">
        {trace.map((t, i) => (
          <div key={i} className="rounded-md bg-muted/50 p-2 font-mono text-xs">
            <div className="font-semibold">{t.tool}</div>
            <div className="text-muted-foreground">
              args: {JSON.stringify(t.args)}
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}
