import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Markdown } from "./Markdown";

describe("citations", () => {
  it("renders every citation in a line", () => {
    /* Regression guard. CITE_NUM_RE deliberately has no /g
       flag: RegExp.test is stateful when global, which made
       repeated calls alternate true/false and silently drop
       every other citation. Three in one line catches it. */

    render(
      <Markdown content="Revenue rose [Page 4] and fell [Page 5] then held [Page 6]." />,
    );

    const labels = screen
      .getAllByRole("button")
      .map((button) => button.textContent);

    expect(labels).toEqual(["p.4", "p.5", "p.6"]);
  });

  it("labels a citation with its short page form", () => {
    render(<Markdown content="Total revenue [Page 12]." />);

    expect(screen.getByRole("button")).toHaveTextContent("p.12");
  });

  it("reports the cited page when clicked", async () => {
    const onCite = vi.fn();

    render(<Markdown content="Revenue [Page 9]." onCite={onCite} />);

    await userEvent.click(screen.getByRole("button"));

    expect(onCite).toHaveBeenCalledWith(9);
  });

  it("marks only the active page as on", () => {
    render(
      <Markdown content="A [Page 2] and B [Page 3]." activePage={3} />,
    );

    const [second, third] = screen.getAllByRole("button");

    expect(second).not.toHaveClass("is-on");
    expect(third).toHaveClass("is-on");
  });

  it("is inert but still rendered without an onCite handler", async () => {
    render(<Markdown content="Revenue [Page 9]." />);

    await userEvent.click(screen.getByRole("button"));

    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("leaves a malformed citation as text", () => {
    render(<Markdown content="See [Page] and [Page abc]." />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("inline grammar", () => {
  it("renders bold, italic and code", () => {
    const { container } = render(
      <Markdown content="**bold** and *lean* and `code`" />,
    );

    expect(container.querySelector("strong")).toHaveTextContent("bold");
    expect(container.querySelector("em")).toHaveTextContent("lean");
    expect(container.querySelector("code.md-code")).toHaveTextContent("code");
  });

  it("does not mistake a bold run for italics", () => {
    const { container } = render(<Markdown content="**bold**" />);

    expect(container.querySelector("em")).toBeNull();
    expect(container.querySelector("strong")).toHaveTextContent("bold");
  });
});

describe("blocks", () => {
  it("renders a pipe table with its header", () => {
    const table = [
      "| Metric | 2023 |",
      "| --- | --- |",
      "| Revenue | 100 |",
      "| Income | 20 |",
    ].join("\n");

    const { container } = render(<Markdown content={table} />);

    expect(container.querySelector("table")).toBeInTheDocument();

    const headers = [...container.querySelectorAll("th")].map(
      (cell) => cell.textContent,
    );

    expect(headers).toEqual(["Metric", "2023"]);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(2);
  });

  it("renders bullet and numbered lists", () => {
    const { container } = render(
      <Markdown content={"- one\n- two\n\n1. first\n2. second"} />,
    );

    expect(container.querySelectorAll("ul li")).toHaveLength(2);
    expect(container.querySelectorAll("ol li")).toHaveLength(2);
  });

  it("renders a citation inside a table cell", () => {
    const table = [
      "| Metric | Source |",
      "| --- | --- |",
      "| Revenue | [Page 8] |",
    ].join("\n");

    render(<Markdown content={table} />);

    expect(screen.getByRole("button")).toHaveTextContent("p.8");
  });

  it("renders an empty string without crashing", () => {
    const { container } = render(<Markdown content="" />);

    expect(container).toBeInTheDocument();
  });
});
