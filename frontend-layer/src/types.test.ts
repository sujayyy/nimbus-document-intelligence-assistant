import { describe, expect, it } from "vitest";

import { formatTime, getSourcePage, type Source } from "./types";

describe("getSourcePage", () => {
  /* The backend has used both spellings, so the client
     tolerates either. These lock the precedence. */

  it("prefers page_number when both are present", () => {
    expect(getSourcePage({ page_number: 7, page: 3 })).toBe(7);
  });

  it("falls back to page", () => {
    expect(getSourcePage({ page: 3 })).toBe(3);
  });

  it("returns null when neither is present", () => {
    expect(getSourcePage({})).toBeNull();
  });

  it("treats page zero as a real page rather than missing", () => {
    expect(getSourcePage({ page_number: 0 })).toBe(0);
  });

  it("skips a null page_number in favour of page", () => {
    const source: Source = { page_number: null, page: 4 };

    expect(getSourcePage(source)).toBe(4);
  });
});

describe("formatTime", () => {
  it("renders hour and minute", () => {
    const at = new Date(2026, 0, 1, 14, 5);

    expect(formatTime(at)).toMatch(/\b2[:.]05\b|\b14[:.]05\b/);
  });

  it("pads the minute to two digits", () => {
    expect(formatTime(new Date(2026, 0, 1, 9, 7))).toMatch(/07/);
  });
});
