import { describe, expect, it } from "vitest";
import { attempt, MAX_SEND_BYTES, TRANSPORT_FAILED, tooBigToSend } from "./actions";

describe("calling a server action", () => {
  it("passes a result straight through", async () => {
    expect(await attempt(async () => ({ ok: true as const, data: 7 }))).toEqual({
      ok: true,
      data: 7,
    });
  });

  it("passes a returned error straight through", async () => {
    expect(await attempt(async () => ({ error: "bad_type", status: 415 }))).toEqual({
      error: "bad_type",
      status: 415,
    });
  });

  it("turns a rejection into an error rather than letting it escape", async () => {
    // This is the whole point: uncaught, the caller's `setBusy(false)` never
    // ran and the button stayed disabled with nothing said.
    const res = await attempt(async () => {
      throw new Error("An unexpected response was received from the server.");
    });
    expect(res).toEqual({ error: TRANSPORT_FAILED });
  });
});

describe("what can be sent", () => {
  it("accepts a file under the transport ceiling", () => {
    expect(tooBigToSend({ size: MAX_SEND_BYTES - 1 })).toBe(false);
  });

  it("refuses one over it", () => {
    expect(tooBigToSend({ size: MAX_SEND_BYTES + 1 })).toBe(true);
  });

  it("stays under the host's own limit, which is the thing that refuses us", () => {
    // 4.5 MB. Sitting exactly on it would fail for anyone whose form fields
    // push the body over.
    expect(MAX_SEND_BYTES).toBeLessThan(4.5 * 1024 * 1024);
  });
});
