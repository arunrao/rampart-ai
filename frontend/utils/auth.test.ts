import { describe, expect, it, beforeEach, vi } from "vitest";
import {
  getAuthToken,
  setAuthToken,
  removeAuthToken,
  isAuthenticated,
} from "./auth";

function mockLocalStorage() {
  const store: Record<string, string> = {};
  const ls = {
    getItem: (k: string) => (k in store ? store[k] : null),
    setItem: (k: string, v: string) => {
      store[k] = String(v);
    },
    removeItem: (k: string) => {
      delete store[k];
    },
    clear: () => {
      for (const k of Object.keys(store)) delete store[k];
    },
    key: (i: number) => Object.keys(store)[i] ?? null,
    get length() {
      return Object.keys(store).length;
    },
  };
  vi.stubGlobal("localStorage", ls as Storage);
  return store;
}

describe("auth token storage", () => {
  beforeEach(() => {
    mockLocalStorage();
  });

  it("returns null when no token", () => {
    expect(getAuthToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it("sets and reads token", () => {
    setAuthToken("test-jwt");
    expect(getAuthToken()).toBe("test-jwt");
    expect(isAuthenticated()).toBe(true);
  });

  it("removeAuthToken clears storage", () => {
    setAuthToken("x");
    localStorage.setItem("user_email", "a@b.com");
    removeAuthToken();
    expect(getAuthToken()).toBeNull();
    expect(localStorage.getItem("user_email")).toBeNull();
  });
});
