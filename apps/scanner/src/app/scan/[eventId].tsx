import { CameraView, useCameraPermissions, type BarcodeScanningResult } from "expo-camera";
import { router, Stack, useFocusEffect, useIsFocused, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, AppState, Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { Banner, Body, Button, Screen } from "@/components/ui";
import { fetchStats, type CheckInStats } from "@/lib/checkin";

const STATS_POLL_MS = 10_000;

type Params = { eventId: string; title?: string; timezone?: string; canUndo?: string };

export default function ScanScreen() {
  const { t } = useTranslation();
  const { eventId, title, timezone, canUndo } = useLocalSearchParams<Params>();
  const [permission, requestPermission, getPermission] = useCameraPermissions();
  const [stats, setStats] = useState<CheckInStats | null>(null);
  const focused = useIsFocused();
  // The camera reports the same code many times a second; handle one scan at a time.
  const handling = useRef(false);

  // Coming back from the phone's Settings: read the permission again, so the camera starts
  // without restarting the app.
  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") void getPermission();
    });
    return () => sub.remove();
  }, [getPermission]);

  // Live counts (SRS 4.8), refreshed while this screen is in front, including after
  // coming back from a result.
  useFocusEffect(
    useCallback(() => {
      handling.current = false;
      let active = true;
      const load = () =>
        fetchStats(eventId)
          .then((s) => active && setStats(s))
          .catch(() => undefined);
      void load();
      const timer = setInterval(load, STATS_POLL_MS);
      return () => {
        active = false;
        clearInterval(timer);
      };
    }, [eventId]),
  );

  function onScanned({ data }: BarcodeScanningResult) {
    if (handling.current) return;
    // Stays set until this screen is in front again, so a ticket still in view while the
    // result is showing can't open a second result.
    handling.current = true;
    router.push({ pathname: "/result", params: { eventId, payload: data, timezone, canUndo } });
  }

  const counts = stats ? t("counts", { checkedIn: stats.checked_in, registered: stats.registered }) : " ";
  const openSearch = () =>
    router.push({ pathname: "/search/[eventId]", params: { eventId, title, timezone, canUndo } });
  const header = <Stack.Screen options={{ title: title ?? t("scan.title") }} />;

  if (!permission) {
    return (
      <Screen>
        {header}
        <ActivityIndicator testID="camera-permission-loading" size="large" />
      </Screen>
    );
  }

  if (!permission.granted) {
    // The OS won't show its prompt again once the user said "don't ask" (Android) or denied
    // once (iOS): the only way back is the Settings app.
    const blocked = !permission.canAskAgain;
    return (
      <Screen>
        {header}
        {blocked ? (
          <>
            <Banner kind="error">{t("home.cameraBlocked")}</Banner>
            <Button title={t("home.openSettings")} onPress={() => void Linking.openSettings()} />
            <Button title={t("common.retry")} variant="secondary" onPress={() => void getPermission()} />
          </>
        ) : (
          <>
            <Body>{t("scan.permissionNeeded")}</Body>
            <Button title={t("home.allowCamera")} onPress={() => void requestPermission()} />
          </>
        )}
        <Button title={t("scan.search")} variant="secondary" onPress={openSearch} />
      </Screen>
    );
  }

  return (
    <View style={styles.container}>
      {header}
      {focused ? (
        <CameraView
          testID="camera"
          style={StyleSheet.absoluteFill}
          facing="back"
          barcodeScannerSettings={{ barcodeTypes: ["qr"] }}
          onBarcodeScanned={onScanned}
        />
      ) : null}
      <View style={styles.overlay} pointerEvents="box-none">
        <Text accessibilityLiveRegion="polite" style={styles.counts}>
          {counts}
        </Text>
        <View style={styles.frame} pointerEvents="none" />
        <Text style={styles.hint}>{t("scan.aim")}</Text>
        <Pressable accessibilityRole="button" onPress={openSearch} style={styles.searchButton}>
          <Text style={styles.searchText}>{t("scan.search")}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000" },
  overlay: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0, alignItems: "center", justifyContent: "center", gap: 24 },
  frame: { width: 260, height: 260, borderWidth: 4, borderColor: "#ffffff", borderRadius: 20 },
  hint: { color: "#fff", fontSize: 18, fontWeight: "600", backgroundColor: "rgba(0,0,0,0.6)", paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
  counts: { color: "#fff", fontSize: 18, fontWeight: "700", backgroundColor: "rgba(0,0,0,0.6)", paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
  searchButton: { backgroundColor: "#ffffff", borderRadius: 8, paddingHorizontal: 20, paddingVertical: 14, minHeight: 48 },
  searchText: { color: "#111827", fontSize: 17, fontWeight: "700" },
});
