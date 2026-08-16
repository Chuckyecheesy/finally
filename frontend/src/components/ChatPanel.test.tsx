import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "./ChatPanel";
import * as api from "@/lib/api";
import type { ChatResponse } from "@/lib/types";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof api>()),
  sendChat: vi.fn(),
}));

const sendChat = vi.mocked(api.sendChat);

const reply = (overrides: Partial<ChatResponse> = {}): ChatResponse => ({
  message: "Bought the dip in AAPL.",
  trade_results: [],
  watchlist_results: [],
  ...overrides,
});

function renderPanel(onActions = vi.fn()) {
  render(<ChatPanel onActions={onActions} collapsed={false} onToggle={vi.fn()} />);
  return onActions;
}

async function ask(text: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Message"), text);
  await user.click(screen.getByRole("button", { name: "Send" }));
}

describe("ChatPanel", () => {
  beforeEach(() => {
    sendChat.mockReset();
  });

  it("renders the user message and the assistant reply", async () => {
    sendChat.mockResolvedValue(reply());
    renderPanel();

    await ask("buy 5 AAPL");

    expect(screen.getByText("buy 5 AAPL")).toBeInTheDocument();
    expect(await screen.findByText("Bought the dip in AAPL.")).toBeInTheDocument();
    expect(sendChat).toHaveBeenCalledWith("buy 5 AAPL");
  });

  it("shows a loading indicator until the reply lands", async () => {
    let resolve!: (value: ChatResponse) => void;
    sendChat.mockReturnValue(new Promise<ChatResponse>((r) => (resolve = r)));
    renderPanel();

    await ask("how am I doing?");

    expect(screen.getByRole("status")).toHaveTextContent("Thinking");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();

    resolve(reply({ message: "Up 2% today." }));

    expect(await screen.findByText("Up 2% today.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  });

  it("shows executed and rejected actions side by side", async () => {
    sendChat.mockResolvedValue(
      reply({
        message: "One filled, one short on cash.",
        trade_results: [
          { ticker: "AAPL", side: "buy", quantity: 5, status: "executed", trade: { price: 191.2 } },
          {
            ticker: "NVDA",
            side: "buy",
            quantity: 100,
            status: "failed",
            error: "Insufficient cash",
          },
        ],
        watchlist_results: [{ ticker: "PYPL", action: "add", status: "executed" }],
      }),
    );
    renderPanel();

    await ask("rebalance me");

    expect(await screen.findByText(/BUY 5 AAPL @ 191\.20/)).toBeInTheDocument();
    expect(screen.getByText(/BUY 100 NVDA — Insufficient cash/)).toBeInTheDocument();
    expect(screen.getByText("Added PYPL")).toBeInTheDocument();
  });

  it("refreshes terminal state after the assistant acts", async () => {
    sendChat.mockResolvedValue(reply());
    const onActions = renderPanel();

    await ask("buy 1 AAPL");

    await waitFor(() => expect(onActions).toHaveBeenCalled());
  });

  it("surfaces a failed request in the transcript", async () => {
    sendChat.mockRejectedValue(new api.ApiError(500, "The assistant is unavailable."));
    renderPanel();

    await ask("hello");

    expect(await screen.findByText("The assistant is unavailable.")).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toBeEnabled();
  });

  it("collapses to a rail that can be reopened", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(<ChatPanel onActions={vi.fn()} collapsed onToggle={onToggle} />);

    await user.click(screen.getByRole("button", { name: "Open AI assistant" }));
    expect(onToggle).toHaveBeenCalled();
    expect(screen.queryByLabelText("Message")).not.toBeInTheDocument();
  });
});
