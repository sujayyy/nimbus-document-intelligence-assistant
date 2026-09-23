/* =====================================================
   TEST SETUP

   jest-dom matchers, plus stubs for the browser APIs
   jsdom does not implement. These are environment gaps,
   not application behaviour: the app calls them on mount
   and jsdom would otherwise throw after a test has
   already passed, which surfaces as an unhandled error
   rather than a failure.
===================================================== */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeAll, vi } from "vitest";

beforeAll(() => {
  /* Called when a new message scrolls into view. */
  Element.prototype.scrollIntoView = vi.fn();

  /* useReducedMotion reads this; jsdom ships no matchMedia. */
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  }
});

afterEach(() => {
  cleanup();
});
