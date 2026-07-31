import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientError, apiRequest } from "@/lib/http";
import { householdApi, PlatformApiError } from "@/lib/platformApi";

const TOKEN_KEY = "nutriflavor_token";
const USER_KEY = "nfos_user";

function jsonResponse(payload: unknown, status: number): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("shared API request contract", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
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
    expect(error).toBeInstanceOf(ApiClientError);
    expect(error).toMatchObject({
      status: 409,
      message: "Inventory item was modified",
    });
  });

  it("formats FastAPI validation arrays with field locations", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        jsonResponse(
          {
            detail: [
              { loc: ["body", "quantity", "quantity_min"], msg: "Input should be greater than or equal to 0" },
              { loc: ["body", "unit"], msg: "Field required" },
            ],
          },
          422,
        ),
      ),
    );

    await expect(householdApi.list()).rejects.toMatchObject({
      status: 422,
      message:
        "body.quantity.quantity_min: Input should be greater than or equal to 0; body.unit: Field required",
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

  it("does not attach authorization or content type to an empty GET", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse([], 200));
    vi.stubGlobal("fetch", fetchMock);

    await expect(householdApi.list()).resolves.toEqual([]);

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options?.headers);
    expect(headers.has("Authorization")).toBe(false);
    expect(headers.has("Content-Type")).toBe(false);
  });

  it("sets JSON content type only when a non-FormData body exists", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ id: "h" }, 201));
    vi.stubGlobal("fetch", fetchMock);

    await householdApi.create("Home", "UTC");

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options?.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("returns undefined for an empty 204 response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(new Response(null, { status: 204 })),
    );

    await expect(apiRequest<void>("/no-content", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("preserves malformed JSON response text instead of throwing a parser error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response("upstream returned invalid JSON", {
          status: 502,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(apiRequest("/malformed")).rejects.toMatchObject({
      status: 502,
      message: "upstream returned invalid JSON",
      detail: "upstream returned invalid JSON",
    });
  });

  it("does not wrap network failures as misleading HTTP responses", async () => {
    const networkError = new TypeError("Network connection failed");
    vi.stubGlobal("fetch", vi.fn<typeof fetch>().mockRejectedValue(networkError));

    await expect(apiRequest("/network")).rejects.toBe(networkError);
  });
});
