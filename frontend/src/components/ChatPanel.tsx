"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { sendChat } from "@/lib/api";
import { quantity as formatQuantity } from "@/lib/format";
import type { ChatMessage, TradeResult, WatchlistResult } from "@/lib/types";

interface ChatPanelProps {
  /** Called after the assistant replies, since it may have traded on our behalf. */
  onActions: () => void | Promise<unknown>;
  collapsed: boolean;
  onToggle: () => void;
}

let messageId = 0;
const nextId = () => `m${++messageId}`;

function ActionChip({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <div
      className={`flex items-start gap-1.5 border-l-2 py-0.5 pl-2 font-mono text-[10px] ${
        ok ? "border-up text-up" : "border-down text-down"
      }`}
    >
      <span aria-hidden>{ok ? "▸" : "✕"}</span>
      <span className="flex-1 text-terminal-text">{children}</span>
    </div>
  );
}

function TradeChip({ result }: { result: TradeResult }) {
  const ok = result.status === "executed";
  const fill = result.trade?.price;
  return (
    <ActionChip ok={ok}>
      {result.side.toUpperCase()} {formatQuantity(result.quantity)} {result.ticker}
      {ok
        ? typeof fill === "number"
          ? ` @ ${fill.toFixed(2)}`
          : " filled"
        : ` — ${result.error ?? "rejected"}`}
    </ActionChip>
  );
}

function WatchChip({ result }: { result: WatchlistResult }) {
  const ok = result.status === "executed";
  const verb = result.action === "add" ? "Added" : "Removed";
  return (
    <ActionChip ok={ok}>
      {ok ? `${verb} ${result.ticker}` : `${result.ticker} — ${result.error ?? "rejected"}`}
    </ActionChip>
  );
}

export function ChatPanel({ onActions, collapsed, onToggle }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight;
  }, [messages, loading]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || loading) return;

    setMessages((current) => [...current, { id: nextId(), role: "user", content: text }]);
    setDraft("");
    setLoading(true);

    try {
      const response = await sendChat(text);
      setMessages((current) => [
        ...current,
        {
          id: nextId(),
          role: "assistant",
          content: response.message,
          trade_results: response.trade_results,
          watchlist_results: response.watchlist_results,
        },
      ]);
      await onActions();
    } catch (err) {
      setMessages((current) => [
        ...current,
        {
          id: nextId(),
          role: "assistant",
          content: err instanceof Error ? err.message : "The assistant is unavailable.",
          failed: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onToggle}
        aria-label="Open AI assistant"
        aria-expanded={false}
        className="flex w-9 shrink-0 flex-col items-center gap-3 border border-terminal-line bg-terminal-panel py-3 transition hover:bg-terminal-raised"
      >
        <span aria-hidden className="h-2 w-[2px] bg-accent" />
        <span className="eyebrow [writing-mode:vertical-rl]">Assistant</span>
      </button>
    );
  }

  return (
    <section
      aria-label="AI assistant"
      className="flex min-h-0 w-[340px] shrink-0 flex-col border border-terminal-line bg-terminal-panel"
    >
      <header className="flex h-7 shrink-0 items-center justify-between border-b border-terminal-line bg-terminal-raised px-2.5">
        <h2 className="eyebrow flex items-center gap-1.5">
          <span aria-hidden className="h-2 w-[2px] bg-accent" />
          Assistant
        </h2>
        <button
          type="button"
          onClick={onToggle}
          aria-label="Collapse AI assistant"
          aria-expanded
          className="px-1 text-[13px] leading-none text-terminal-faint hover:text-terminal-text"
        >
          ›
        </button>
      </header>

      <div ref={scroller} className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {messages.length === 0 && (
          <p className="text-[11px] leading-relaxed text-terminal-dim">
            Ask about your positions, request analysis, or place an order in plain language. Trades
            you approve here fill immediately.
          </p>
        )}

        {messages.map((message) =>
          message.role === "user" ? (
            <div key={message.id} className="flex justify-end">
              <p className="max-w-[85%] border border-primary/40 bg-primary/10 px-2.5 py-1.5 text-[11.5px] leading-relaxed text-terminal-text">
                {message.content}
              </p>
            </div>
          ) : (
            <div key={message.id} className="space-y-1.5">
              <span className="eyebrow text-accent">FinAlly</span>
              <p
                className={`whitespace-pre-wrap text-[11.5px] leading-relaxed ${
                  message.failed ? "text-down" : "text-terminal-text"
                }`}
              >
                {message.content}
              </p>
              {(message.trade_results?.length || message.watchlist_results?.length) && (
                <div className="space-y-1 pt-0.5">
                  {message.trade_results?.map((result, index) => (
                    <TradeChip key={`t${index}`} result={result} />
                  ))}
                  {message.watchlist_results?.map((result, index) => (
                    <WatchChip key={`w${index}`} result={result} />
                  ))}
                </div>
              )}
            </div>
          ),
        )}

        {loading && (
          <div className="flex items-center gap-2" role="status" aria-live="polite">
            <span className="eyebrow text-accent">FinAlly</span>
            <span aria-hidden className="h-2 w-[7px] animate-pulse bg-accent" />
            <span className="sr-only">Thinking</span>
          </div>
        )}
      </div>

      <form onSubmit={submit} className="flex shrink-0 border-t border-terminal-line">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask or instruct…"
          aria-label="Message"
          disabled={loading}
          className="min-w-0 flex-1 bg-transparent px-3 py-2.5 text-[11.5px] text-terminal-text placeholder:text-terminal-faint focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || draft.trim().length === 0}
          className="border-l border-terminal-line bg-secondary/85 px-4 text-[10px] font-bold uppercase tracking-[0.12em] text-white transition hover:bg-secondary disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </section>
  );
}
