import { describe, expect, it, vi, afterEach } from "vitest";
import { CSRF_HEADER, CSRF_HEADER_VALUE, fetchWithAuth, logoutSession, withSession } from "./auth";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("cookie session helpers", () => {
  it("withSession sends cookies and the CSRF header", () => {
    const init = withSession({ method: "POST", headers: { "Content-Type": "application/json" } });
    expect(init.credentials).toBe("include");
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({
      [CSRF_HEADER]: CSRF_HEADER_VALUE,
      "Content-Type": "application/json",
    });
  });

  it("withSession accepts a Headers instance", () => {
    const init = withSession({ headers: new Headers({ Accept: "text/plain" }) });
    expect(init.headers).toMatchObject({ accept: "text/plain", [CSRF_HEADER]: CSRF_HEADER_VALUE });
  });

  it("never attaches a bearer token from storage", () => {
    const init = withSession({});
    const keys = Object.keys(init.headers as Record<string, string>).map((k) => k.toLowerCase());
    expect(keys).not.toContain("authorization");
  });

  it("fetchWithAuth forwards the session init to fetch", async () => {
    const spy = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", spy);
    await fetchWithAuth("http://api.test/x", { method: "DELETE" });
    expect(spy).toHaveBeenCalledWith(
      "http://api.test/x",
      expect.objectContaining({ method: "DELETE", credentials: "include" })
    );
  });

  it("logoutSession posts to /auth/logout and swallows network errors", async () => {
    const spy = vi.fn().mockRejectedValue(new Error("offline"));
    vi.stubGlobal("fetch", spy);
    await expect(logoutSession()).resolves.toBeUndefined();
    expect(spy.mock.calls[0][0]).toMatch(/\/auth\/logout$/);
    expect(spy.mock.calls[0][1]).toMatchObject({ method: "POST", credentials: "include" });
  });
});
