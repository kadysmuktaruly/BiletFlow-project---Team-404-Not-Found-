// Fails if a page or component has user-facing text that isn't from messages/*.json
// (CLAUDE.md: "Put all user-facing web strings in one module"; SRS 7 kk/ru/en). The same
// rules as the scanner's i18n test: text between JSX tags, and literal user-facing props.
// Run: npm run check:hardcoded (part of `npm run lint`).
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const files = (dir) =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : path.endsWith(".tsx") ? [path] : [];
  });
const sources = [...files(join(root, "src/app")), ...files(join(root, "src/components"))];

// Text that is the same in every language: brand names, symbols and units.
const ALLOWED = new Set(["https://", "BiletFlow", "DEMO", "KZT", "PDF", "QR", "SVG", "CSV", "kk", "ru", "en", "Қаз", "Рус", "Eng"]);

const problems = [];
for (const file of sources) {
  const src = readFileSync(file, "utf8");
  const where = relative(root, file);
  // Text between JSX tags, e.g. <p>Sign in</p>.
  for (const m of src.matchAll(/(?<![=-])>\s*([^<>{}\n]*\p{L}[^<>{}\n]*?)\s*</gu)) {
    const text = m[1].trim();
    // Code that happens to sit between > and <: arrows, logic, ternaries, type parameters.
    if (/^[\s\w.]*=>|&&|\|\||^[\w.]+\s*[<>]=?\s*\w|^\)|\s\?\s|\):\s*\w/.test(text)) continue;
    if (ALLOWED.has(text)) continue;
    problems.push(`${where}: "${text}"`);
  }
  // Literal user-facing props, e.g. title="Scan" or aria-label="Close".
  for (const m of src.matchAll(/\b(title|placeholder|aria-label|label|alt|hint)="([^"]*\p{L}[^"]*)"/gu)) {
    if (ALLOWED.has(m[2])) continue;
    problems.push(`${where}: ${m[1]}="${m[2]}"`);
  }
}

if (sources.length < 20) {
  console.error(`check-hardcoded: found only ${sources.length} files; is the path right?`);
  process.exit(1);
}
if (problems.length) {
  console.error(`Hard-coded user-facing text (move it to messages/{kk,ru,en}.json):\n  ${problems.join("\n  ")}`);
  process.exit(1);
}
console.log(`hard-coded text: none in ${sources.length} files`);
