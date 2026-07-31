import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { householdApi, PlatformApiError } from "@/lib/platformApi";

const TOKEN_KEY = "nutriflavor_token";
const USER_KEY = "nfos_user";

function jsonResponse(payload: unknown, status: number): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("platformApi request contract", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("preserves structured backend error messages and status codes", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        jsonResponse(
          {
            detail: {
              code: "stale_version",
              message: "Inventory item was modified",
              current_version: 4,
            },
          },
          409,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    let error: unknown;
    try {
      await householdApi.list();
    } catch (value) {
      error = value;
    }

    expect(error).toBeInstanceOf(PlatformApiError);
    expect(error).toMatchObject({
      status: 409,
      message: "Inventory item was modified",
    });
  });

  it("sends the bearer token and clears the persisted session on 401", async () => {
    localStorage.setItem(TOKEN_KEY, "signed-token");
    localStorage.setItem(USER_KEY, JSON.stringify({ id: "user@example.test" }));
    const unauthorized = vi.fn();
    window.addEventListener("nutriflavor:unauthorized", unauthorized, { once: true });

    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ detail: "Session expired" }, 401));
    vi.stubGlobal("fetch", fetchMock);

    await expect(householdApi.list()).rejects.toMatchObject({
      status: 401,
      message: "Session expired",
    });

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options?.headers);
    expect(headers.get("Authorization")).toBe("Bearer signed-token");
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(USER_KEY)).toBeNull();
    expect(unauthorized).toHaveBeenCalledTimes(1);
  });

  it("does not attach an authorization header without a stored token", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse([], 200));
    vi.stubGlobal("fetch", fetchMock);

    await expect(householdApi.list()).resolves.toEqual([]);

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options?.headers);
    expect(headers.has("Authorization")).toBe(false);
  });
});
