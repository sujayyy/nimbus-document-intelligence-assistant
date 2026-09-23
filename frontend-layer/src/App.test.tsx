import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

/* =====================================================
   APP SMOKE TEST

   The redesign split a 2461-line App.tsx into eleven
   components. A production build only proves it compiles,
   so this mounts the real tree in jsdom to prove it
   renders and reaches its empty state.

   jsdom has no 2D canvas, which ParticleField asks for on
   mount; returning null is the documented "unsupported"
   answer and the component already guards for it.
===================================================== */

beforeEach(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => null) as never;

  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve([]),
      }),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("mounting", () => {
  it("renders without crashing", () => {
    const { container } = render(<App />);

    expect(container.firstChild).toBeTruthy();
  });

  it("offers a way to ask a question", async () => {
    render(<App />);

    await waitFor(() => {
      expect(
        screen.getByRole("textbox") ?? screen.getByRole("button"),
      ).toBeInTheDocument();
    });
  });

  it("does not render an error state on a clean mount", () => {
    const { container } = render(<App />);

    expect(container.querySelector(".is-error")).toBeNull();
  });
});
