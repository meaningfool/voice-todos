import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(resolve(process.cwd(), "src/index.css"), "utf8");

function getBlock(selector: string) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = css.match(new RegExp(`${escaped}\\s*\\{([\\s\\S]*?)\\}`, "m"));

  expect(match).not.toBeNull();

  return match![1];
}

describe("index.css reference alignment", () => {
  it("keeps the outer page background flat like the checked-in reference", () => {
    expect(getBlock("body")).toContain("background: #fdf8f6;");
  });

  it("keeps the device shell opaque instead of glassy", () => {
    const shell = getBlock(".voice-device-shell");

    expect(shell).toContain("background: #fff;");
    expect(shell).toContain("border: 1px solid #fff;");
    expect(shell).not.toContain("backdrop-filter");
  });

  it("keeps todo cards and neutral metadata close to the reference styling", () => {
    expect(getBlock(".voice-todo-circle")).toContain("width: 1.5rem;");
    expect(getBlock(".voice-todo-circle")).toContain("height: 1.5rem;");
    expect(getBlock(".voice-todo-card")).toContain("background: #fff;");
    expect(getBlock(".voice-meta-chip--calendar")).toContain("background: #fafafa;");
    expect(getBlock(".voice-meta-chip--tag")).toContain("background: #fafafa;");
    expect(getBlock(".voice-meta-chip--user")).toContain("background: rgba(244, 244, 245, 0.5);");
  });
});
