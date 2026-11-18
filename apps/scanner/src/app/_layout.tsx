import "@/i18n";

import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useTranslation } from "react-i18next";

import { AuthProvider } from "@/lib/auth";

export default function RootLayout() {
  const { t } = useTranslation();
  return (
    <AuthProvider>
      <StatusBar style="dark" />
      <Stack screenOptions={{ title: t("common.appName") }}>
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="login" options={{ headerShown: false }} />
      </Stack>
    </AuthProvider>
  );
}
