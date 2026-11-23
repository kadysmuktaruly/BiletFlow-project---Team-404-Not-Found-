import i18n, { pickLocale } from "@/i18n";

// Set by jest for every test file.
declare const __dirname: string;

describe("pickLocale", () => {
  it("uses the first supported device language", () => {
    expect(pickLocale(["de", "ru", "en"])).toBe("ru");
    expect(pickLocale(["EN"])).toBe("en");
  });

  it("falls back to Kazakh", () => {
    expect(pickLocale(["de", null, undefined])).toBe("kk");
    expect(pickLocale([])).toBe("kk");
  });
});

describe("translations", () => {
  it("has every user-facing string in kk, ru and en", async () => {
    for (const lng of ["kk", "ru", "en"]) {
      await i18n.changeLanguage(lng);
      expect(i18n.t("login.submit")).not.toBe("login.submit");
      expect(i18n.t("home.signedInAs", { name: "Aigerim" })).toContain("Aigerim");
    }
  });
});

describe("no hard-coded text", () => {
  // Node's fs, typed just enough for this test (the app has no @types/node).
  const { readdirSync, readFileSync, statSync } = jest.requireActual<{
    readdirSync(path: string): string[];
    readFileSync(path: string, encoding: "utf8"): string;
    statSync(path: string): { isDirectory(): boolean };
  }>("fs");
  const join = (...parts: string[]) => parts.join("/");
  const files = (dir: string): string[] =>
    readdirSync(dir).flatMap((name) => {
      const path = join(dir, name);
      return statSync(path).isDirectory() ? files(path) : path.endsWith(".tsx") ? [path] : [];
    });
  const sources = [...files(join(__dirname, "../app")), ...files(join(__dirname, "../components"))];

  it("finds the screens", () => {
    expect(sources.length).toBeGreaterThanOrEqual(8);
  });

  it("has no hard-coded text in screens or components", () => {
    const problems: string[] = [];
    for (const file of sources) {
      const src = readFileSync(file, "utf8");
      // Text between JSX tags, e.g. <Text>Sign in</Text>.
      for (const m of src.matchAll(/(?<![=-])>\s*([^<>{}\n]*\p{L}[^<>{}\n]*?)\s*</gu)) {
        if (!/^[\s\w.]*=>|&&|\|\|/.test(m[1])) problems.push(`${file}: ${m[1]}`);
      }
      // Literal user-facing props, e.g. title="Scan".
      for (const m of src.matchAll(/\b(title|placeholder|accessibilityLabel|accessibilityHint|label)="([^"]*\p{L}[^"]*)"/gu)) {
        problems.push(`${file}: ${m[1]}="${m[2]}"`);
      }
    }
    expect(problems).toEqual([]);
  });
});

describe("locale files", () => {
  const flatten = (obj: object, prefix = ""): string[] =>
    Object.entries(obj).flatMap(([k, v]) => (v && typeof v === "object" ? flatten(v, `${prefix}${k}.`) : [`${prefix}${k}`]));

  it("has the same keys in kk, ru and en, none of them empty", () => {
    const en = flatten(i18n.getResourceBundle("en", "translation")).sort();
    for (const lng of ["kk", "ru"]) {
      expect(flatten(i18n.getResourceBundle(lng, "translation")).sort()).toEqual(en);
    }
    for (const lng of ["kk", "ru", "en"]) {
      for (const key of en) expect(i18n.getFixedT(lng)(key)).not.toBe("");
    }
  });

  it("translates the new door messages instead of falling back to English", () => {
    for (const key of ["result.notCheckedIn.title", "result.notCheckedIn.offline", "result.undoFailed"]) {
      const en = i18n.getFixedT("en")(key);
      expect(i18n.getFixedT("kk")(key)).not.toBe(en);
      expect(i18n.getFixedT("ru")(key)).not.toBe(en);
    }
  });
});
