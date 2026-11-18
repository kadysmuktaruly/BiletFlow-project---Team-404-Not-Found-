import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import i18n from "@/i18n";
import LoginScreen from "@/app/login";
import { ApiError } from "@/lib/api";

const mockLogin = jest.fn();
const mockReplace = jest.fn();

jest.mock("@/lib/auth", () => ({ useAuth: () => ({ login: mockLogin }) }));
jest.mock("expo-router", () => ({ router: { replace: (...a: unknown[]) => mockReplace(...a) } }));

beforeEach(async () => {
  jest.clearAllMocks();
  await i18n.changeLanguage("en");
});

it("signs in and goes to the home screen", async () => {
  mockLogin.mockResolvedValue(undefined);
  await render(<LoginScreen />);
  await fireEvent.changeText(screen.getByLabelText("Email"), " staff@example.com ");
  await fireEvent.changeText(screen.getByLabelText("Password"), "s3cret-pass");
  await fireEvent.press(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/home"));
  expect(mockLogin).toHaveBeenCalledWith("staff@example.com", "s3cret-pass");
});

it("shows a translated error for wrong credentials", async () => {
  mockLogin.mockRejectedValue(new ApiError("invalid_credentials"));
  await i18n.changeLanguage("ru");
  await render(<LoginScreen />);
  await fireEvent.press(screen.getByRole("button", { name: "Войти" }));
  expect(await screen.findByText("Неверная почта или пароль.")).toBeTruthy();
  expect(mockReplace).not.toHaveBeenCalled();
});
