import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { StrictMode } from "react";
import { Alert } from "react-native";

import ResultScreen from "@/app/result";
import i18n from "@/i18n";
import { ApiError } from "@/lib/api";
import type { ScanResult } from "@/lib/checkin";

const mockParams: Record<string, string> = {};
const mockBack = jest.fn();
const mockScan = jest.fn();
const mockCheckIn = jest.fn();
const mockUndo = jest.fn();

jest.mock("expo-router", () => ({
  router: { back: () => mockBack(), push: jest.fn() },
  Stack: { Screen: () => null },
  useLocalSearchParams: () => mockParams,
}));
jest.mock("@/lib/checkin", () => ({
  ...jest.requireActual("@/lib/checkin"),
  scanTicket: (...a: unknown[]) => mockScan(...a),
  checkInTicket: (...a: unknown[]) => mockCheckIn(...a),
  undoCheckIn: (...a: unknown[]) => mockUndo(...a),
}));

const ticket = {
  id: "t-1",
  ticket_number: "BFT-7K2P-9XQM",
  status: "checked_in" as const,
  attendee_name: "Aigerim Bekova",
  ticket_type_name: "Standard",
  checked_in_at: "2026-11-22T14:05:00Z",
};
const result = (over: Partial<ScanResult>): ScanResult => ({
  result: "valid",
  reason: null,
  ticket,
  method: "qr_scan",
  stats: { registered: 120, checked_in: 41 },
  ...over,
});

beforeEach(async () => {
  jest.clearAllMocks();
  for (const k of Object.keys(mockParams)) delete mockParams[k];
  Object.assign(mockParams, { eventId: "e-1", payload: "BFT1.abc.def", timezone: "Asia/Almaty", canUndo: "true" });
  await i18n.changeLanguage("en");
});

it("sends the scanned code to the server and shows a live valid result with counts", async () => {
  mockScan.mockResolvedValue(result({}));
  await render(<ResultScreen />);
  expect(await screen.findByTestId("result-valid")).toBeTruthy();
  expect(mockScan).toHaveBeenCalledTimes(1);
  expect(mockScan).toHaveBeenCalledWith("e-1", "BFT1.abc.def");
  expect(screen.getByText("Aigerim Bekova")).toBeTruthy();
  expect(screen.getByText("41 of 120 checked in")).toBeTruthy();
  expect(screen.queryByText(/simulated/i)).toBeNull();
});

it.each([
  ["already_used", "Already used"],
  ["cancelled", "Cancelled"],
  ["refunded", "Refunded"],
] as const)("shows %s from the server with color, symbol and words", async (state, title) => {
  mockScan.mockResolvedValue(result({ result: state }));
  await render(<ResultScreen />);
  expect(await screen.findByTestId(`result-${state}`)).toBeTruthy();
  expect(screen.getByText(title)).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Undo check-in" })).toBeNull();
});

it("shows when an already-used ticket was checked in, in the event's time zone", async () => {
  mockScan.mockResolvedValue(result({ result: "already_used" }));
  await i18n.changeLanguage("en");
  await render(<ResultScreen />);
  // 14:05 UTC is 19:05 in Almaty ("7:05 PM" in English).
  expect(await screen.findByText(/^(19:05|7:05\sPM)$/)).toBeTruthy();
});

it("explains a rejected Campaign QR code", async () => {
  mockScan.mockResolvedValue(result({ result: "invalid", reason: "campaign_qr_not_admission", ticket: null }));
  await render(<ResultScreen />);
  expect(await screen.findByTestId("result-invalid")).toBeTruthy();
  expect(screen.getByText("This is a promo QR code, not a ticket.")).toBeTruthy();
});

it("undoes a check-in after confirmation, for event admins", async () => {
  mockScan.mockResolvedValue(result({}));
  mockUndo.mockResolvedValue({ ticket: { ...ticket, status: "valid" }, stats: { registered: 120, checked_in: 40 } });
  const alert = jest.spyOn(Alert, "alert").mockImplementation((_t, _m, buttons) => {
    void buttons?.find((b) => b.style === "destructive")?.onPress?.();
  });
  await render(<ResultScreen />);
  await fireEvent.press(await screen.findByRole("button", { name: "Undo check-in" }));
  expect(alert).toHaveBeenCalled();
  await waitFor(() => expect(mockUndo).toHaveBeenCalledWith("e-1", "t-1"));
  expect(await screen.findByText("Check-in undone. The ticket is valid again.")).toBeTruthy();
  expect(screen.getByText("40 of 120 checked in")).toBeTruthy();
});

it("doesn't offer undo to check-in staff", async () => {
  mockParams.canUndo = "false";
  mockScan.mockResolvedValue(result({}));
  await render(<ResultScreen />);
  await screen.findByTestId("result-valid");
  expect(screen.queryByRole("button", { name: "Undo check-in" })).toBeNull();
});

it("checks in a ticket chosen from manual search", async () => {
  delete mockParams.payload;
  mockParams.ticketId = "t-9";
  mockCheckIn.mockResolvedValue(result({ method: "manual_search" }));
  await render(<ResultScreen />);
  await screen.findByTestId("result-valid");
  expect(mockCheckIn).toHaveBeenCalledWith("e-1", "t-9");
  expect(mockScan).not.toHaveBeenCalled();
});

it("shows a translated network error and retries", async () => {
  mockScan.mockRejectedValueOnce(new ApiError("network")).mockResolvedValueOnce(result({}));
  await i18n.changeLanguage("ru");
  await render(<ResultScreen />);
  expect(await screen.findByText(i18n.t("errors.network"))).toBeTruthy();
  await fireEvent.press(screen.getByRole("button", { name: i18n.t("common.retry") }));
  expect(await screen.findByTestId("result-valid")).toBeTruthy();
  expect(mockScan).toHaveBeenCalledTimes(2);
});

it("records one check-in even when React runs the effect twice", async () => {
  mockScan.mockResolvedValue(result({}));
  await render(
    <StrictMode>
      <ResultScreen />
    </StrictMode>,
  );
  await screen.findByTestId("result-valid");
  expect(mockScan).toHaveBeenCalledTimes(1);
});
