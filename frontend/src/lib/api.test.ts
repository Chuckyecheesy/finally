import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchHistory } from "./api";

function stubFetch(json: unknown) {
  const mockFetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => json,
  });
  vi.stubGlobal("fetch", mockFetch);
  return mockFetch;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchHistory", () => {
  it("requests the default bounded limit when called with no argument", async () => {
    const mockFetch = stubFetch([]);

    await fetchHistory();

    const [url] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("limit=500");
  });

  it("honors an explicit limit override", async () => {
    const mockFetch = stubFetch([]);

    await fetchHistory(50);

    const [url] = mockFetch.mock.calls[0];
    expect(String(url)).toContain("limit=50");
  });

  it("still normalizes the response shape", async () => {
    stubFetch([{ total_value: 100, recorded_at: "2026-01-01T00:00:00Z" }]);

    const result = await fetchHistory();

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ total_value: 100, recorded_at: "2026-01-01T00:00:00Z" });
  });
});
