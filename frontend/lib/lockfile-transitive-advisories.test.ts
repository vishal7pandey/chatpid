// Guard for the Dependabot alerts that the updater cannot fix itself (CPID-43). These packages are
// transitive, every parent range already allows the patched version, and Dependabot's pnpm helper fails
// with `security_update_not_possible`, so the lockfile is re-resolved by hand and this test keeps it there.
//
//   source-map-js  alert 35      first patched 1.2.2
//   undici         alerts 12-20  first patched 8.10.2
//   brace-expansion alerts 25,26 first patched 5.0.12 (5.x line) and 1.1.21 (1.x line)
//   vitest         alert 5       first patched 4.1.11
//   @vitest/mocker alert 4       first patched 4.1.11
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// package -> first patched version per major line. A major above every listed line is accepted (newer
// than any advisory); a major below the lowest listed line, or between listed lines, fails and needs a look.
const PATCHED: Record<string, Record<number, string>> = {
  "source-map-js": { 1: "1.2.2" },
  undici: { 8: "8.10.2" },
  "brace-expansion": { 1: "1.1.21", 5: "5.0.12" },
  vitest: { 4: "4.1.11" },
  "@vitest/mocker": { 4: "4.1.11" },
};

function parse(version: string): number[] {
  return version.split(".").map(Number);
}

function isAtLeast(version: string, minimum: string): boolean {
  const parts = parse(version);
  const min = parse(minimum);
  for (let i = 0; i < min.length; i++) {
    if (parts[i] !== min[i]) return parts[i] > min[i];
  }
  return true;
}

function problem(name: string, version: string): string | null {
  const lines = PATCHED[name];
  const majors = Object.keys(lines).map(Number);
  const major = parse(version)[0];
  if (major > Math.max(...majors)) return null;
  const minimum = lines[major];
  if (!minimum) return `${name}@${version} is on a major line with no recorded patched version`;
  return isAtLeast(version, minimum) ? null : `${name}@${version} is below ${minimum}`;
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\/]/g, String.raw`\$&`);
}

describe("pnpm-lock.yaml transitive advisories", () => {
  const lock = readFileSync(resolve(__dirname, "..", "pnpm-lock.yaml"), "utf8");

  describe.each(Object.keys(PATCHED))("%s", (name) => {
    const quoted = escapeRegExp(name);

    it("resolves only patched versions in the package and snapshot entries", () => {
      const entry = new RegExp(String.raw`^ {2}'?${quoted}@(\d+\.\d+\.\d+)[(':]`, "gm");
      const versions = [...new Set([...lock.matchAll(entry)].map((m) => m[1]))];
      expect(versions.length).toBeGreaterThan(0);
      const bad = versions.map((v) => problem(name, v)).filter(Boolean);
      expect(bad).toEqual([]);
    });

    it("has no dependent edge pinned to an unpatched version", () => {
      const edge = new RegExp(String.raw`^ +'?${quoted}'?: (\d+\.\d+\.\d+)`, "gm");
      const bad = [...lock.matchAll(edge)].map((m) => problem(name, m[1])).filter(Boolean);
      expect(bad).toEqual([]);
    });
  });
});
