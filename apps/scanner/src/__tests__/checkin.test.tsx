import { render, screen } from "@testing-library/react-native";

import { ResultView } from "@/components/result-view";
import i18n from "@/i18n";
import { campaignRejection, formatTime, invalidReasonKey, isCampaignQr, RESULT_STATES } from "@/lib/checkin";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});

describe("invalidReasonKey", () => {
  it("explains invalid results only", () => {
    expect(invalidReasonKey({ result: "invalid", reason: "campaign_qr_not_admission" })).toBe(
      "result.reasons.campaign_qr_not_admission",
    );
    expect(invalidReasonKey({ result: "invalid", reason: null })).toBeNull();
    expect(invalidReasonKey({ result: "already_used", reason: null })).toBeNull();
  });

  it("has a translation for every reason the API can send", () => {
    for (const reason of ["unrecognized", "wrong_event", "campaign_qr_not_admission"]) {
      expect(i18n.exists(`result.reasons.${reason}`)).toBe(true);
    }
  });
});

describe("formatTime", () => {
  it("shows the time in the event's time zone", () => {
    expect(formatTime("2026-11-22T14:05:00Z", "Asia/Almaty", "en-GB")).toBe("19:05");
    expect(formatTime(null, "Asia/Almaty", "en")).toBeNull();
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

  it("shows why an invalid code failed", async () => {
    await render(<ResultView state="invalid" details={{ reason: i18n.t("result.reasons.campaign_qr_not_admission") }} />);
    expect(screen.getByText("This is a promo QR code, not a ticket.")).toBeTruthy();
  });

  it("is translated", async () => {
    await i18n.changeLanguage("kk");
    await render(<ResultView state="already_used" />);
    expect(screen.getByText("Пайдаланылған")).toBeTruthy();
  });
});

describe("isCampaignQr", () => {
  it("recognizes Campaign QR codes and links (same rule as the API)", () => {
    expect(isCampaignQr("BFC1.q8Zk2mWv0dX9yTnE4hRp")).toBe(true);
    expect(isCampaignQr("https://biletflow.kz/c/BFC1.q8Zk2mWv0dX9yTnE4hRp")).toBe(true);
    expect(isCampaignQr("  BFC1.x ")).toBe(true);
  });

  it("never treats a ticket or anything else as a campaign", () => {
    expect(isCampaignQr("BFT1.AAAAAAAAAAAAAAAAAAAAAA.bWFj")).toBe(false);
    expect(isCampaignQr("BFT1.BFC1.x")).toBe(false); // the server decides about this one
    expect(isCampaignQr("hello")).toBe(false);
    expect(isCampaignQr("")).toBe(false);
  });

  it("only ever rejects", () => {
    expect(campaignRejection()).toMatchObject({ result: "invalid", reason: "campaign_qr_not_admission", ticket: null });
  });
});
