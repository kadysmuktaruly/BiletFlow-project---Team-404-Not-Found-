import { useCameraPermissions } from "expo-camera";
import { Redirect, router } from "expo-router";
import { useTranslation } from "react-i18next";
import { Linking } from "react-native";

import { Banner, Body, Button, Screen, Title } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export default function HomeScreen() {
  const { t } = useTranslation();
  const { status, user, logout } = useAuth();
  const [permission, requestPermission] = useCameraPermissions();

  if (status === "anonymous") return <Redirect href="/login" />;
  if (!user) return null;

  return (
    <Screen>
      <Body>{t("home.signedInAs", { name: user.full_name })}</Body>
      <Title>{t("home.cameraTitle")}</Title>
      {permission?.granted ? (
        <Banner kind="success">{t("home.cameraGranted")}</Banner>
      ) : permission && !permission.canAskAgain ? (
        <>
          <Banner kind="error">{t("home.cameraBlocked")}</Banner>
          <Button title={t("home.openSettings")} onPress={() => void Linking.openSettings()} />
        </>
      ) : (
        <>
          <Body>{t("home.cameraNeeded")}</Body>
          <Button title={t("home.allowCamera")} onPress={() => void requestPermission()} />
        </>
      )}
      <Button
        title={t("common.signOut")}
        variant="secondary"
        onPress={async () => {
          await logout();
          router.replace("/login");
        }}
      />
    </Screen>
  );
}
