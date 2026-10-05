// Guard for Dependabot alert 8 (CPID-36): js-yaml < 4.3.2 is vulnerable (CPU use with empty merge
// sources). js-yaml is transitive (eslint -> @eslint/eslintrc), so the lockfile is what pins it.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const PATCHED = [4, 3, 2];

function isAtLeast(version: string, minimum: number[]): boolean {
  const parts = version.split(".").map(Number);
  for (let i = 0; i < minimum.length; i++) {
    if (parts[i] !== minimum[i]) return parts[i] > minimum[i];
  }
  return true;
}

describe("pnpm-lock.yaml advisories", () => {
  const lock = readFileSync(resolve(__dirname, "..", "pnpm-lock.yaml"), "utf8");

  it("resolves js-yaml at or above the patched 4.3.2 everywhere", () => {
    const versions = [...lock.matchAll(/^ {2}js-yaml@(\d+\.\d+\.\d+):/gm)].map((m) => m[1]);
    expect(versions.length).toBeGreaterThan(0);
    for (const version of versions) {
      expect(isAtLeast(version, PATCHED), `js-yaml@${version} is below 4.3.2`).toBe(true);
    }
  });

  it("no dependent edge pins js-yaml to an unpatched version", () => {
    const edges = [...lock.matchAll(/^ +js-yaml: (\d+\.\d+\.\d+)$/gm)].map((m) => m[1]);
    for (const version of edges) {
      expect(isAtLeast(version, PATCHED), `edge to js-yaml ${version} is below 4.3.2`).toBe(true);
    }
  });
});
