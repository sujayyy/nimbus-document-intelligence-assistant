import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const reducedMotion = vi.hoisted(() => ({ value: false }));

vi.mock("motion/react", () => ({
  useReducedMotion: () => reducedMotion.value,
}));

import { CountUp } from "./CountUp";

beforeEach(() => {
  reducedMotion.value = false;
});

describe("accessibility contract", () => {
  /* The figure must be real in the accessibility tree from
     the first frame, so a screen reader never reads a
     number the API did not return. Only the visual span
     tweens. */

  it("exposes the true value immediately, even while tweening", () => {
    const { container } = render(<CountUp value={1240} />);

    expect(container.querySelector(".sr-only")).toHaveTextContent("1,240");
  });

  it("hides the tweening figure from assistive technology", () => {
    const { container } = render(<CountUp value={1240} />);

    expect(container.querySelector("[aria-hidden='true']")).toBeTruthy();
  });
});

describe("when the tween is skipped", () => {
  it("shows a small value at once rather than glitching up to it", () => {
    /* Default threshold is 8. */
    const { container } = render(<CountUp value={3} />);

    expect(container.querySelector("[aria-hidden='true']")).toHaveTextContent(
      "3",
    );
  });

  it("respects a custom threshold", () => {
    const { container } = render(<CountUp value={40} threshold={100} />);

    expect(container.querySelector("[aria-hidden='true']")).toHaveTextContent(
      "40",
    );
  });

  it("shows the final value at once under reduced motion", () => {
    reducedMotion.value = true;

    const { container } = render(<CountUp value={1240} />);

    expect(container.querySelector("[aria-hidden='true']")).toHaveTextContent(
      "1,240",
    );
  });
});

describe("when the tween runs", () => {
  it("starts below the target and lands exactly on it", async () => {
    const { container } = render(<CountUp value={900} />);

    const visual = container.querySelector("[aria-hidden='true']");

    expect(visual).toHaveTextContent("0");

    await waitFor(
      () => {
        expect(visual).toHaveTextContent("900");
      },
      { timeout: 3000 },
    );
  });

  it("renders thousands separators", async () => {
    render(<CountUp value={12345} />);

    await waitFor(
      () => {
        expect(screen.getByText("12,345", { selector: ".sr-only" }))
          .toBeInTheDocument();
      },
      { timeout: 3000 },
    );
  });
});
