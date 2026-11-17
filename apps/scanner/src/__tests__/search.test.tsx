import { act, fireEvent, render, screen } from "@testing-library/react-native";

import SearchScreen from "@/app/search/[eventId]";
import i18n from "@/i18n";

const mockPush = jest.fn();
const mockSearch = jest.fn();

jest.mock("expo-router", () => ({
  router: { push: (...a: unknown[]) => mockPush(...a) },
  Stack: { Screen: () => null },
  useLocalSearchParams: () => ({ eventId: "e-1", timezone: "Asia/Almaty", canUndo: "false" }),
}));
jest.mock("@/lib/checkin", () => ({
  ...jest.requireActual("@/lib/checkin"),
  searchAttendees: (...a: unknown[]) => mockSearch(...a),
}));

const row = (name: string, status: "valid" | "checked_in") => ({
  id: `id-${name}`,
  ticket_number: `BFT-${name.slice(0, 4).toUpperCase()}-0000`,
  status,
  attendee_name: name,
  ticket_type_name: "Standard",
  checked_in_at: null,
});

beforeEach(async () => {
  jest.useFakeTimers();
  jest.clearAllMocks();
  await i18n.changeLanguage("en");
});
afterEach(() => jest.useRealTimers());

it("searches after a pause in typing and opens a check-in for the chosen ticket", async () => {
  mockSearch.mockResolvedValue({ tickets: [row("Aigerim Bekova", "valid"), row("Daniyar S", "checked_in")], stats: { registered: 2, checked_in: 1 } });
  await render(<SearchScreen />);
  await fireEvent.changeText(screen.getByLabelText("Name, email or ticket number"), "a");
  await fireEvent.changeText(screen.getByLabelText("Name, email or ticket number"), "ai");
  await act(async () => {
    jest.advanceTimersByTime(350);
  });
  expect(mockSearch).toHaveBeenLastCalledWith("e-1", "ai");
  expect(mockSearch).not.toHaveBeenCalledWith("e-1", "a");
  expect(await screen.findByText("Aigerim Bekova")).toBeTruthy();
  expect(screen.getByText("Checked in")).toBeTruthy();
  expect(screen.getByText("Not checked in")).toBeTruthy();

  await fireEvent.press(screen.getByRole("button", { name: /Aigerim Bekova/ }));
  expect(mockPush).toHaveBeenCalledWith({
    pathname: "/result",
    params: { eventId: "e-1", ticketId: "id-Aigerim Bekova", timezone: "Asia/Almaty", canUndo: "false" },
  });
});
