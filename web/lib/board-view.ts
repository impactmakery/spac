/** How the board lays its posts out. */
export type BoardView = "cards" | "list" | "table";

export const BOARD_VIEWS: BoardView[] = ["cards", "list", "table"];

const KEY = "board-view";

export function isBoardView(value: unknown): value is BoardView {
  return typeof value === "string" && (BOARD_VIEWS as string[]).includes(value);
}

/** Just the two methods used, so a test can pass a plain object. */
type StorageLike = Pick<Storage, "getItem" | "setItem">;

function browserStorage(): StorageLike | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    // private browsing can throw on access, not only on use
    return null;
  }
}

/**
 * Remembered per person, in the browser.
 *
 * Deliberately not on the account: this is how somebody prefers to look at a
 * list, not something the platform needs to know about them, and keeping it
 * server-side would mean a migration, an endpoint and a write on every toggle
 * for a value that costs nothing to lose. The trade is that it does not follow
 * them to another machine — the right trade for a preference that takes one
 * click to set again.
 *
 * Exposed as a subscribable store rather than something a component reads on
 * mount. The server has no localStorage, so the first render must be the
 * default and the stored value can only arrive afterwards; useSyncExternalStore
 * is built for exactly that, and it also keeps two open tabs in step.
 */
export function readBoardView(storage: StorageLike | null = browserStorage()): BoardView {
  try {
    const stored = storage?.getItem(KEY);
    return isBoardView(stored) ? stored : "cards";
  } catch {
    return "cards";
  }
}

/** What the server renders, before any preference is known. */
export function defaultBoardView(): BoardView {
  return "cards";
}

const listeners = new Set<() => void>();

export function subscribeBoardView(onChange: () => void): () => void {
  listeners.add(onChange);
  // 'storage' only fires in *other* tabs, so the local set below notifies too.
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY) onChange();
  };
  if (typeof window !== "undefined") window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(onChange);
    if (typeof window !== "undefined") window.removeEventListener("storage", onStorage);
  };
}

export function writeBoardView(
  view: BoardView,
  storage: StorageLike | null = browserStorage(),
): void {
  try {
    storage?.setItem(KEY, view);
  } catch {
    // not being able to remember the choice must not break making it
  }
  for (const listener of listeners) listener();
}
