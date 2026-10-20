import { afterEach, expect, test, vi } from "vitest";
import { request } from "./api";

afterEach(() => vi.unstubAllGlobals());

test("authenticated JSON requests keep the access token out of URLs", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => ({ status: "pending" }) });
  vi.stubGlobal("fetch", fetcher);
  await request("private-token", "/proposals", "POST", {
    operation: "event_delete",
  });
  expect(fetcher).toHaveBeenCalledWith(
    "/api/proposals",
    expect.objectContaining({
      headers: {
        Authorization: "Bearer private-token",
        "Content-Type": "application/json",
      },
      body: '{"operation":"event_delete"}',
    }),
  );
});

test("multipart upload leaves boundary generation to the browser", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => ({ id: "job" }) });
  vi.stubGlobal("fetch", fetcher);
  const form = new FormData();
  form.append("audio", new Blob(["audio"]));
  await request("token", "/recordings", "POST", form);
  expect(fetcher.mock.calls[0][1].headers).toEqual({
    Authorization: "Bearer token",
  });
});

test("backend conflicts are shown instead of success", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({
        message: "Event changed; review a fresh proposal",
      }),
    }),
  );
  await expect(
    request("token", "/proposals/p/approve", "POST", {}),
  ).rejects.toThrow("Event changed");
});
