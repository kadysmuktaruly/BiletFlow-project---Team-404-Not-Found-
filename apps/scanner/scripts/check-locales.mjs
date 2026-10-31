// Fails if the kk, ru and en message files don't have exactly the same keys.
// Run: part of `npm run lint`.
import { readFileSync } from "node:fs";

const locales = ["kk", "ru", "en"];
const keys = (obj, prefix = "") =>
  Object.entries(obj).flatMap(([k, v]) =>
    v && typeof v === "object" ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
const sets = Object.fromEntries(
  locales.map((l) => [
    l,
    new Set(keys(JSON.parse(readFileSync(new URL(`../src/locales/${l}.json`, import.meta.url))))),
  ]),
);
let ok = true;
for (const a of locales) {
  for (const b of locales) {
    const missing = [...sets[a]].filter((k) => !sets[b].has(k));
    if (a !== b && missing.length) {
      ok = false;
      console.error(`src/locales/${b}.json is missing: ${missing.join(", ")}`);
    }
  }
}
if (!ok) process.exit(1);
console.log(`i18n: ${sets.en.size} keys in ${locales.join(", ")}`);
