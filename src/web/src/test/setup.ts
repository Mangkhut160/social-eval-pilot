import "@testing-library/jest-dom/vitest";
import { beforeEach, vi } from "vitest";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      status: 200,
      headers: new Headers({ "Content-Type": "application/json" }),
      json: async () => ({ items: [] }),
      text: async () => "",
    }))
  );
});
