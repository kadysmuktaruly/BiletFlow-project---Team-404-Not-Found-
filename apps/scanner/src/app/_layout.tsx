import "@/i18n";

import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useTranslation } from "react-i18next";

import { colors } from "@/components/ui";
import { AuthProvider } from "@/lib/auth";

export default function RootLayout() {
  const { t } = useTranslation();
  return (
    <AuthProvider>
      <StatusBar style="dark" />
      {/* With no header background set, iOS 26 draws a see-through Liquid Glass header and
          every screen's content slides under it. A solid, opaque header keeps it below. */}
      <Stack
        screenOptions={{
          title: t("common.appName"),
          headerTransparent: false,
          headerStyle: { backgroundColor: colors.background },
          headerTintColor: colors.ink,
          contentStyle: { backgroundColor: colors.background },
        }}
      >
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="login" options={{ headerShown: false }} />
      </Stack>
    </AuthProvider>
  );
}
