import { act, fireEvent, render, screen } from "@testing-library/react-native";
import { AppState, Linking } from "react-native";

import ScanScreen from "@/app/scan/[eventId]";
import i18n from "@/i18n";

type Permission = { granted: boolean; canAskAgain: boolean } | null;
type CameraProps = { onBarcodeScanned?: (scan: { data: string }) => void };

const mockPermission: { current: Permission } = { current: null };
const mockRequest = jest.fn();
const mockGet = jest.fn();
const mockCamera: { props: CameraProps | null } = { props: null };
const mockPush = jest.fn();
const mockFocused = { current: true };
const mockFocus: { current: (() => void | (() => void)) | null; cleanup: (() => void) | void } = {
  current: null,
  cleanup: undefined,
};
/** Blur then focus the screen again, as when coming back from the result screen. */
function refocus() {
  mockFocus.cleanup?.();
  mockFocus.cleanup = mockFocus.current?.();
}
const mockStats = jest.fn();

jest.mock("expo-camera", () => ({
  useCameraPermissions: () => [mockPermission.current, mockRequest, mockGet],
  CameraView: (props: CameraProps) => {
    mockCamera.props = props;
    return null;
  },
}));
jest.mock("expo-router", () => {
  const { useEffect } = jest.requireActual("react");
  return {
    router: { push: (...a: unknown[]) => mockPush(...a) },
    Stack: { Screen: () => null },
    useLocalSearchParams: () => ({ eventId: "e-1", title: "Jazz", timezone: "Asia/Almaty", canUndo: "true" }),
    useIsFocused: () => mockFocused.current,
    useFocusEffect: (cb: () => void | (() => void)) =>
      useEffect(() => {
        mockFocus.current = cb;
        mockFocus.cleanup = cb();
        return () => mockFocus.cleanup?.();
      }, [cb]),
  };
});
jest.mock("@/lib/checkin", () => ({
  ...jest.requireActual("@/lib/checkin"),
  fetchStats: (...a: unknown[]) => mockStats(...a),
}));

let appStateListener: ((state: string) => void) | null = null;

beforeEach(async () => {
  jest.clearAllMocks();
  mockPermission.current = { granted: true, canAskAgain: true };
  mockCamera.props = null;
  mockFocused.current = true;
  mockStats.mockResolvedValue({ registered: 120, checked_in: 41 });
  jest.spyOn(AppState, "addEventListener").mockImplementation((_type, listener) => {
    appStateListener = listener as (state: string) => void;
    return { remove: jest.fn() } as unknown as ReturnType<typeof AppState.addEventListener>;
  });
  await i18n.changeLanguage("en");
});

it("asks for camera permission when it hasn't been decided", async () => {
  mockPermission.current = { granted: false, canAskAgain: true };
  await render(<ScanScreen />);
  expect(screen.getByText("Allow camera access to scan tickets.")).toBeTruthy();
  await fireEvent.press(screen.getByRole("button", { name: "Allow camera" }));
  expect(mockRequest).toHaveBeenCalledTimes(1);
  expect(mockCamera.props).toBeNull();
  // Manual search still works without the camera.
  expect(screen.getByRole("button", { name: "Search attendees" })).toBeTruthy();
});

it("shows a blocked screen with Open settings and Try again after the user denied it", async () => {
  mockPermission.current = { granted: false, canAskAgain: false };
  const openSettings = jest.spyOn(Linking, "openSettings").mockResolvedValue(undefined);
  await render(<ScanScreen />);
  expect(screen.getByText(i18n.t("home.cameraBlocked"))).toBeTruthy();
  // The OS won't prompt again, so "Allow camera" would do nothing: it isn't offered.
  expect(screen.queryByRole("button", { name: "Allow camera" })).toBeNull();
  await fireEvent.press(screen.getByRole("button", { name: "Open settings" }));
  expect(openSettings).toHaveBeenCalledTimes(1);
  await fireEvent.press(screen.getByRole("button", { name: "Try again" }));
  expect(mockGet).toHaveBeenCalledTimes(1);
  expect(mockCamera.props).toBeNull();
});

it("is translated on the blocked screen", async () => {
  mockPermission.current = { granted: false, canAskAgain: false };
  await i18n.changeLanguage("kk");
  await render(<ScanScreen />);
  expect(screen.getByRole("button", { name: i18n.t("home.openSettings") })).toBeTruthy();
  expect(i18n.t("home.openSettings")).not.toBe("Open settings");
});

it("re-checks permission when the app returns from settings", async () => {
  mockPermission.current = { granted: false, canAskAgain: false };
  await render(<ScanScreen />);
  expect(appStateListener).not.toBeNull();
  await act(async () => appStateListener?.("background"));
  expect(mockGet).not.toHaveBeenCalled();
  await act(async () => appStateListener?.("active"));
  expect(mockGet).toHaveBeenCalledTimes(1);
});

it("waits for the permission status instead of flashing the 'allow' screen", async () => {
  mockPermission.current = null;
  await render(<ScanScreen />);
  expect(screen.getByTestId("camera-permission-loading")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Allow camera" })).toBeNull();
});

it("sends one scan to the result screen, ignoring repeats until it is in front again", async () => {
  await render(<ScanScreen />);
  const scanned = mockCamera.props?.onBarcodeScanned;
  expect(scanned).toBeDefined();
  await act(async () => {
    scanned?.({ data: "BFT1.abc.def" });
    scanned?.({ data: "BFT1.abc.def" });
    scanned?.({ data: "BFT1.other.xyz" });
  });
  expect(mockPush).toHaveBeenCalledTimes(1);
  expect(mockPush).toHaveBeenCalledWith({
    pathname: "/result",
    params: { eventId: "e-1", payload: "BFT1.abc.def", timezone: "Asia/Almaty", canUndo: "true" },
  });
  // Back from the result screen: the next ticket scans.
  await act(async () => refocus());
  await act(async () => scanned?.({ data: "BFT1.next.ghi" }));
  expect(mockPush).toHaveBeenCalledTimes(2);
});

it("only scans while the screen is in front", async () => {
  mockFocused.current = false;
  await render(<ScanScreen />);
  // No camera at all while the result screen is on top, so nothing can be scanned twice.
  expect(mockCamera.props).toBeNull();
});

it("refreshes the counts every time the scanner comes back into view", async () => {
  await render(<ScanScreen />);
  expect(await screen.findByText("41 of 120 checked in")).toBeTruthy();
  mockStats.mockResolvedValue({ registered: 120, checked_in: 42 });
  await act(async () => refocus());
  expect(await screen.findByText("42 of 120 checked in")).toBeTruthy();
  expect(mockStats).toHaveBeenCalledWith("e-1");
});
