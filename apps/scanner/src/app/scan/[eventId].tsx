import { CameraView, useCameraPermissions, type BarcodeScanningResult } from "expo-camera";
import { router, Stack, useFocusEffect, useLocalSearchParams } from "expo-router";
import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Body, Button, Screen } from "@/components/ui";
import { fetchStats, type CheckInStats } from "@/lib/checkin";

const STATS_POLL_MS = 10_000;

type Params = { eventId: string; title?: string; timezone?: string; canUndo?: string };

export default function ScanScreen() {
  const { t } = useTranslation();
  const { eventId, title, timezone, canUndo } = useLocalSearchParams<Params>();
  const [permission, requestPermission] = useCameraPermissions();
  const [stats, setStats] = useState<CheckInStats | null>(null);
  // The camera reports the same code many times a second; handle one scan at a time.
  const handling = useRef(false);

  // Live counts (SRS 4.8), refreshed while this screen is in front, including after
  // coming back from a result.
  useFocusEffect(
    useCallback(() => {
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
    handling.current = true;
    router.push({ pathname: "/result", params: { eventId, payload: data, timezone, canUndo } });
    setTimeout(() => {
      handling.current = false;
    }, 1500);
  }

  const counts = stats ? t("counts", { checkedIn: stats.checked_in, registered: stats.registered }) : " ";
  const openSearch = () =>
    router.push({ pathname: "/search/[eventId]", params: { eventId, title, timezone, canUndo } });

  if (!permission?.granted) {
    return (
      <Screen>
        <Stack.Screen options={{ title: title ?? t("scan.title") }} />
        <Body>{t("scan.permissionNeeded")}</Body>
        <Button title={t("home.allowCamera")} onPress={() => void requestPermission()} />
        <Button title={t("scan.search")} variant="secondary" onPress={openSearch} />
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
