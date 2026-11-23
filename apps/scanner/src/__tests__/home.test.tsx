import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import HomeScreen from "@/app/home";
import i18n from "@/i18n";

const mockGet = jest.fn();
const mockPush = jest.fn();
const mockReplace = jest.fn();
const mockLogout = jest.fn();

jest.mock("expo-camera", () => ({
  useCameraPermissions: () => [{ granted: true, canAskAgain: true }, jest.fn(), jest.fn()],
}));
jest.mock("expo-router", () => ({
  router: { push: (...a: unknown[]) => mockPush(...a), replace: (...a: unknown[]) => mockReplace(...a) },
  Link: ({ children }: { children: React.ReactNode }) => {
    const { Text } = jest.requireActual("react-native");
    return <Text>{children}</Text>;
  },
  Redirect: () => null,
}));
jest.mock("@/lib/auth", () => ({
  useAuth: () => ({ status: "authenticated", user: { full_name: "Madina Ospanova" }, logout: mockLogout }),
}));
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  api: { GET: (...a: unknown[]) => mockGet(...a) },
}));

const event = (id: string, title: string, role: string, can_undo: boolean) => ({
  id,
  title,
  status: "published",
  starts_at: "2026-11-28T14:00:00Z",
  ends_at: "2026-11-28T18:00:00Z",
  timezone: "Asia/Almaty",
  venue_name: "Kazakhconcert Hall",
  role,
  can_undo,
});
const ok = (data: unknown) => ({ data, response: { ok: true, status: 200 } as Response });

beforeEach(async () => {
  jest.clearAllMocks();
  await i18n.changeLanguage("en");
});

it("lists exactly the events the server returns for this user, with their role", async () => {
  mockGet.mockResolvedValue(
    ok([event("e-1", "Almaty Jazz Night", "event_admin", true), event("e-2", "Student Meetup", "check_in_staff", false)]),
  );
  await render(<HomeScreen />);
  expect(await screen.findByText("Almaty Jazz Night")).toBeTruthy();
  expect(screen.getByText("Student Meetup")).toBeTruthy();
  expect(screen.getByText("Event admin")).toBeTruthy();
  expect(screen.getByText("Check-in staff")).toBeTruthy();
  // The list comes from the server's assignment check, not a client-side filter.
  expect(mockGet).toHaveBeenCalledWith("/api/v1/checkin/events");

  await fireEvent.press(screen.getByText("Student Meetup"));
  expect(mockPush).toHaveBeenCalledWith({
    pathname: "/scan/[eventId]",
    params: { eventId: "e-2", title: "Student Meetup", timezone: "Asia/Almaty", canUndo: "false" },
  });
});

it("explains an empty list", async () => {
  mockGet.mockResolvedValue(ok([]));
  await render(<HomeScreen />);
  expect(await screen.findByText(i18n.t("events.empty"))).toBeTruthy();
});

it("shows a clear message when offline", async () => {
  mockGet.mockRejectedValue(new TypeError("Network request failed"));
  await render(<HomeScreen />);
  expect(await screen.findByText(i18n.t("errors.network"))).toBeTruthy();
});

it("signs out and returns to the login screen", async () => {
  mockGet.mockResolvedValue(ok([]));
  mockLogout.mockResolvedValue(undefined);
  await render(<HomeScreen />);
  await fireEvent.press(screen.getByRole("button", { name: "Sign out" }));
  await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/login"));
  expect(mockLogout).toHaveBeenCalledTimes(1);
});
