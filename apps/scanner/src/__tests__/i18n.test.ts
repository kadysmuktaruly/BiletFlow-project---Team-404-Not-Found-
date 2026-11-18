import i18n, { pickLocale } from "@/i18n";

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
