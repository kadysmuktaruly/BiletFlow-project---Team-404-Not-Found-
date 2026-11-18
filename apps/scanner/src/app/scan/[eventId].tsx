import { CameraView, useCameraPermissions, type BarcodeScanningResult } from "expo-camera";
import { router, Stack, useLocalSearchParams } from "expo-router";
import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { StyleSheet, Text, View } from "react-native";

import { Body, Button, Screen } from "@/components/ui";

export default function ScanScreen() {
  const { t } = useTranslation();
  const { eventId, title } = useLocalSearchParams<{ eventId: string; title?: string }>();
  const [permission, requestPermission] = useCameraPermissions();
  // The camera reports the same code many times a second; handle one scan at a time.
  const handling = useRef(false);

  function onScanned({ data }: BarcodeScanningResult) {
    if (handling.current) return;
    handling.current = true;
    router.push({ pathname: "/result", params: { eventId, payload: data } });
    setTimeout(() => {
      handling.current = false;
    }, 1500);
  }

  if (!permission?.granted) {
    return (
      <Screen>
        <Stack.Screen options={{ title: title ?? t("scan.title") }} />
        <Body>{t("scan.permissionNeeded")}</Body>
        <Button title={t("home.allowCamera")} onPress={() => void requestPermission()} />
      </Screen>
    );
  }

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ title: title ?? t("scan.title") }} />
      <CameraView
        style={StyleSheet.absoluteFill}
        facing="back"
        barcodeScannerSettings={{ barcodeTypes: ["qr"] }}
        onBarcodeScanned={onScanned}
      />
      <View style={styles.overlay} pointerEvents="none">
        <View style={styles.frame} />
        <Text style={styles.hint}>{t("scan.aim")}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000" },
  overlay: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0, alignItems: "center", justifyContent: "center", gap: 24 },
  frame: { width: 260, height: 260, borderWidth: 4, borderColor: "#ffffff", borderRadius: 20 },
  hint: { color: "#fff", fontSize: 18, fontWeight: "600", backgroundColor: "rgba(0,0,0,0.6)", paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
});
