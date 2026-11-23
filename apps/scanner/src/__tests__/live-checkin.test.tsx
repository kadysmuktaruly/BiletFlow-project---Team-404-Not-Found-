import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { StrictMode } from "react";
import { Alert } from "react-native";

import ResultScreen from "@/app/result";
import i18n from "@/i18n";
import { ApiError, unwrap } from "@/lib/api";
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
  ["already_used", "Already used", "!"],
  ["cancelled", "Cancelled", "⊘"],
  ["refunded", "Refunded", "↩"],
] as const)("shows %s from the server with color, symbol and words", async (state, title, symbol) => {
  mockScan.mockResolvedValue(result({ result: state }));
  await render(<ResultScreen />);
  expect(await screen.findByTestId(`result-${state}`)).toBeTruthy();
  expect(screen.getByText(title)).toBeTruthy();
  expect(screen.getByText(symbol)).toBeTruthy();
  expect(screen.getByText(i18n.t(`result.${state}.text`))).toBeTruthy();
  expect(screen.queryByTestId("result-valid")).toBeNull();
});

it.each(["cancelled", "refunded"] as const)("never offers undo on a %s ticket", async (state) => {
  mockScan.mockResolvedValue(result({ result: state }));
  await render(<ResultScreen />);
  await screen.findByTestId(`result-${state}`);
  expect(screen.queryByRole("button", { name: "Undo check-in" })).toBeNull();
});

it("offers undo on an already-used ticket, so an admin can reverse a check-in found later", async () => {
  mockScan.mockResolvedValue(result({ result: "already_used" }));
  mockUndo.mockResolvedValue({ ticket: { ...ticket, status: "valid" }, stats: { registered: 120, checked_in: 40 } });
  jest.spyOn(Alert, "alert").mockImplementation((_t, _m, buttons) => {
    void buttons?.find((b) => b.style === "destructive")?.onPress?.();
  });
  await render(<ResultScreen />);
  await fireEvent.press(await screen.findByRole("button", { name: "Undo check-in" }));
  await waitFor(() => expect(mockUndo).toHaveBeenCalledWith("e-1", "t-1"));
  expect(await screen.findByText("40 of 120 checked in")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Undo check-in" })).toBeNull();
});

it("shows the server's refusal when undo isn't allowed", async () => {
  mockScan.mockResolvedValue(result({}));
  mockUndo.mockRejectedValue(new ApiError("checkin_undo_forbidden"));
  jest.spyOn(Alert, "alert").mockImplementation((_t, _m, buttons) => {
    void buttons?.find((b) => b.style === "destructive")?.onPress?.();
  });
  await render(<ResultScreen />);
  await fireEvent.press(await screen.findByRole("button", { name: "Undo check-in" }));
  expect(await screen.findByText("The check-in was not undone. Only event admins can undo a check-in.")).toBeTruthy();
  expect(screen.queryByText("Check-in undone. The ticket is valid again.")).toBeNull();
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

it("says the ticket was NOT checked in when offline, in Russian, and retries", async () => {
  mockScan.mockRejectedValueOnce(new ApiError("network")).mockResolvedValueOnce(result({}));
  await i18n.changeLanguage("ru");
  await render(<ResultScreen />);
  expect(await screen.findByTestId("result-not-checked-in")).toBeTruthy();
  expect(screen.getByText("Вход не отмечен")).toBeTruthy();
  expect(screen.getByText(i18n.t("result.notCheckedIn.offline"))).toBeTruthy();
  expect(screen.getByText("✕")).toBeTruthy();
  expect(screen.queryByTestId("result-valid")).toBeNull();
  expect(screen.queryByText(/\d+ из \d+/)).toBeNull(); // no counts that could look like progress
  await fireEvent.press(screen.getByRole("button", { name: i18n.t("common.retry") }));
  expect(await screen.findByTestId("result-valid")).toBeTruthy();
  expect(screen.queryByTestId("result-not-checked-in")).toBeNull();
  expect(mockScan).toHaveBeenCalledTimes(2);
});

it("says the ticket was NOT checked in on a timeout", async () => {
  // What the real client produces when fetchWithTimeout aborts (see api.test.ts).
  const abort = Object.assign(new Error("Aborted"), { name: "AbortError" });
  mockScan.mockImplementation(() => unwrap(Promise.reject(abort)));
  await render(<ResultScreen />);
  expect(await screen.findByTestId("result-not-checked-in")).toBeTruthy();
  expect(screen.getByText("Not checked in")).toBeTruthy();
  expect(screen.getByText(/This ticket was NOT checked in/)).toBeTruthy();
  expect(screen.queryByTestId("result-valid")).toBeNull();
});

it("says the ticket was NOT checked in on a server error", async () => {
  mockScan.mockRejectedValue(new ApiError("internal_error"));
  await render(<ResultScreen />);
  expect(await screen.findByTestId("result-not-checked-in")).toBeTruthy();
  expect(screen.getByText(i18n.t("result.notCheckedIn.text"))).toBeTruthy();
  expect(screen.getByText(i18n.t("errors.generic"))).toBeTruthy();
  expect(screen.queryByTestId("result-valid")).toBeNull();
});

it("shows a loading state while the server checks the ticket", async () => {
  let answer: (r: ScanResult) => void = () => undefined;
  mockScan.mockReturnValue(new Promise<ScanResult>((resolve) => (answer = resolve)));
  await render(<ResultScreen />);
  expect(screen.getByTestId("result-checking")).toBeTruthy();
  expect(screen.getByText("Checking the ticket…")).toBeTruthy();
  expect(screen.queryByTestId("result-valid")).toBeNull();
  await act(async () => answer(result({})));
  expect(await screen.findByTestId("result-valid")).toBeTruthy();
  expect(screen.queryByTestId("result-checking")).toBeNull();
});

it.each([
  "BFC1.q8Zk2mWv0dX9yTnE4hRp",
  "https://biletflow.kz/c/BFC1.q8Zk2mWv0dX9yTnE4hRp",
  "http://localhost:3000/en/c/BFC1.q8Zk2mWv0dX9yTnE4hRp",
])("rejects a Campaign QR on the phone, without the server and even offline: %s", async (payload) => {
  mockParams.payload = payload;
  mockScan.mockRejectedValue(new ApiError("network")); // would fail if it were called
  await render(<ResultScreen />);
  expect(await screen.findByTestId("result-invalid")).toBeTruthy();
  expect(screen.getByText("This is a promo QR code, not a ticket.")).toBeTruthy();
  expect(mockScan).not.toHaveBeenCalled();
  expect(screen.queryByRole("button", { name: "Undo check-in" })).toBeNull();
});

it("still checks in a real ticket scanned right after a Campaign QR", async () => {
  mockParams.payload = "https://biletflow.kz/c/BFC1.q8Zk2mWv0dX9yTnE4hRp";
  const promo = await render(<ResultScreen />);
  await screen.findByTestId("result-invalid");
  await promo.unmount();
  mockParams.payload = "BFT1.abc.def";
  mockScan.mockResolvedValue(result({}));
  await render(<ResultScreen />);
  expect(await screen.findByTestId("result-valid")).toBeTruthy();
  expect(mockScan).toHaveBeenCalledWith("e-1", "BFT1.abc.def");
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
