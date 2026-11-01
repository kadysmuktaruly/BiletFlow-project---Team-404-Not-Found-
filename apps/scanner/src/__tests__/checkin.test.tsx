import { render, screen } from "@testing-library/react-native";

import { ResultView } from "@/components/result-view";
import i18n from "@/i18n";
import { classifyPayload, mockResult, RESULT_STATES } from "@/lib/checkin";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

describe("classifyPayload", () => {
  it("recognises admission tokens", () => {
    expect(classifyPayload("BFT1.jezcqwEwTj-Axg-wQRtEeA.gELHFVz714PmskeuhI-ZRQ")).toBe("admission");
    expect(classifyPayload("  BFT1.abc.def\n")).toBe("admission");
  });

  it("recognises Campaign QR codes, bare or inside a link", () => {
    expect(classifyPayload("BFC1.abcdef")).toBe("campaign");
    expect(classifyPayload("https://biletflow.kz/c/BFC1.abcdef")).toBe("campaign");
  });

  it("treats anything else as unknown, and never shows it as valid", () => {
    expect(classifyPayload("https://example.com")).toBe("unknown");
    expect(mockResult("hello")).toBe("invalid");
    expect(mockResult("https://biletflow.kz/c/BFC1.abc")).toBe("invalid");
  });
});

describe("ResultView", () => {
  it.each(RESULT_STATES)("renders the %s screen with a title and instructions", async (state) => {
    await render(<ResultView state={state} details={{ attendeeName: "Aigerim N" }} />);
    expect(screen.getByTestId(`result-${state}`)).toBeTruthy();
    expect(screen.getByText(i18n.t(`result.${state}.title`))).toBeTruthy();
    expect(screen.getByText(i18n.t(`result.${state}.text`))).toBeTruthy();
    expect(screen.getByText("Aigerim N")).toBeTruthy();
  });

  it("explains a rejected Campaign QR code", async () => {
    await render(<ResultView state="invalid" details={{ campaign: true }} />);
    expect(screen.getByText("This is a promo QR code, not a ticket.")).toBeTruthy();
  });

  it("is translated", async () => {
    await i18n.changeLanguage("kk");
    await render(<ResultView state="already_used" />);
    expect(screen.getByText("Пайдаланылған")).toBeTruthy();
  });
});
