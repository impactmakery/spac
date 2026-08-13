/**
 * Calling a server action from the browser.
 *
 * An action can fail *before* it runs. The file travels as the request body,
 * and the host refuses one over about 4.5 MB with a 413 that no code of ours
 * ever sees — the call rejects instead of returning. Every call site already
 * handles `{ error }`; none of them remembered to handle a rejection, so a
 * large upload left the button disabled for good with nothing said, which
 * reads as "still uploading" forever.
 *
 * `attempt` turns a rejection into the shape the call site already handles.
 */

export type ActionResult<T = undefined> =
  | { ok: true; data?: T }
  | { error: string; status?: number };

/** The call never arrived. Distinct from an error the server chose to return. */
export const TRANSPORT_FAILED = "transport_failed";

export async function attempt<T>(
  run: () => Promise<ActionResult<T>>,
): Promise<ActionResult<T>> {
  try {
    return await run();
  } catch {
    return { error: TRANSPORT_FAILED };
  }
}

/**
 * What the browser can actually get to us, which is not what the platform
 * advertises. The 25 MB cap is real and the API enforces it; it is simply not
 * reachable through a server action body. Checked before sending so an
 * oversized file is refused in the same instant it is chosen, rather than
 * after a wait that ends in nothing.
 */
export const MAX_SEND_BYTES = 4 * 1024 * 1024;

export function tooBigToSend(file: { size: number }): boolean {
  return file.size > MAX_SEND_BYTES;
}
