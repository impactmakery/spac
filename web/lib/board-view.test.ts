import { describe, expect, it } from "vitest";
import {
  defaultBoardView,
  isBoardView,
  readBoardView,
  subscribeBoardView,
  writeBoardView,
} from "./board-view";

/** A stand-in for localStorage, so these run without a browser. */
function fakeStorage(initial: Record<string, string> = {}) {
  const data = { ...initial };
  return {
    getItem: (k: string) => data[k] ?? null,
    setItem: (k: string, v: string) => {
      data[k] = v;
    },
    data,
  };
}

describe("isBoardView", () => {
  it("accepts the layouts that exist", () => {
    expect(["cards", "list", "table"].every(isBoardView)).toBe(true);
  });

  it("rejects anything else", () => {
    // whatever is in storage came from a browser, not from us: a stale value,
    // a hand-edited one, or one written by a different version of the app
    for (const bad of ["kanban", "", null, undefined, 3, {}]) {
      expect(isBoardView(bad), String(bad)).toBe(false);
    }
  });
});

describe("remembering the choice", () => {
  it("defaults to cards when nothing has been chosen", () => {
    expect(readBoardView(fakeStorage())).toBe("cards");
  });

  it("reads back what was written", () => {
    const storage = fakeStorage();
    writeBoardView("table", storage);
    expect(readBoardView(storage)).toBe("table");
  });

  it("falls back to cards on a value it does not recognise", () => {
    expect(readBoardView(fakeStorage({ "board-view": "kanban" }))).toBe("cards");
  });

  it("survives storage being unavailable", () => {
    // private browsing throws on access; failing to remember a preference must
    // not stop the page rendering or the toggle working
    const hostile: Pick<Storage, "getItem" | "setItem"> = {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("denied");
      },
    };
    expect(readBoardView(hostile)).toBe("cards");
    expect(() => writeBoardView("list", hostile)).not.toThrow();
  });

  it("survives there being no storage at all", () => {
    expect(readBoardView(null)).toBe("cards");
    expect(() => writeBoardView("list", null)).not.toThrow();
  });
});

describe("as a store the board page can subscribe to", () => {
  it("renders the default on the server, where storage does not exist", () => {
    // The first render must not depend on the browser, or the markup the
    // server sent and the markup React expects would disagree.
    expect(defaultBoardView()).toBe("cards");
  });

  it("tells subscribers when the choice changes", () => {
    const storage = fakeStorage();
    let called = 0;
    const stop = subscribeBoardView(() => {
      called += 1;
    });

    writeBoardView("table", storage);
    expect(called).toBe(1);

    stop();
    writeBoardView("list", storage);
    expect(called, "a stopped subscriber must not be called").toBe(1);
  });
});
