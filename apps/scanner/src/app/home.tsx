import type { Schemas } from "@biletflow/api-types";
import { useCameraPermissions } from "expo-camera";
import { Link, Redirect, router } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { FlatList, Linking, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";

import { Banner, Body, Button, colors, Screen, Title } from "@/components/ui";
import { api, errorKey, unwrap } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type CheckInEvent = Schemas["CheckInEvent"];

export default function HomeScreen() {
  const { t, i18n } = useTranslation();
  const { status, user, logout } = useAuth();
  const [permission, requestPermission] = useCameraPermissions();
  const [events, setEvents] = useState<CheckInEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      setEvents(await unwrap(api.GET("/api/v1/checkin/events")));
    } catch (err) {
      setError(t(errorKey(err, (k) => i18n.exists(k))));
    } finally {
      setRefreshing(false);
    }
  }, [t, i18n]);

  useEffect(() => {
    if (status !== "authenticated") return;
    let active = true;
    unwrap(api.GET("/api/v1/checkin/events"))
      .then((data) => active && setEvents(data))
      .catch((err: unknown) => active && setError(t(errorKey(err, (k) => i18n.exists(k)))));
    return () => {
      active = false;
    };
  }, [status, t, i18n]);

  if (status === "anonymous") return <Redirect href="/login" />;
  if (!user) return null;

  const formatter = (tz: string) =>
    new Intl.DateTimeFormat(i18n.language, { dateStyle: "medium", timeStyle: "short", timeZone: tz });

  return (
    <Screen>
      <Body>{t("home.signedInAs", { name: user.full_name })}</Body>
      {permission?.granted ? null : permission && !permission.canAskAgain ? (
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
      <Title>{t("events.title")}</Title>
      <Body>{t("events.lead")}</Body>
      {error ? <Banner kind="error">{error}</Banner> : null}
      <FlatList
        data={events ?? []}
        keyExtractor={(e) => e.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void load()} />}
        ListEmptyComponent={events ? <Body>{t("events.empty")}</Body> : undefined}
        contentContainerStyle={{ gap: 12 }}
        renderItem={({ item }) => (
          <Pressable
            accessibilityRole="button"
            accessibilityHint={t("events.scan")}
            onPress={() => router.push({ pathname: "/scan/[eventId]", params: { eventId: item.id, title: item.title } })}
            style={({ pressed }) => [styles.card, pressed && { opacity: 0.8 }]}
          >
            <Text style={styles.cardTitle}>{item.title}</Text>
            <Text style={styles.cardMeta}>
              {formatter(item.timezone).format(new Date(item.starts_at))}
              {item.venue_name ? ` · ${item.venue_name}` : ""}
            </Text>
            <Text style={styles.cardRole}>{t(`events.roles.${item.role}`)}</Text>
          </Pressable>
        )}
      />
      <View style={{ gap: 12 }}>
        <Link href="/result-preview" style={styles.link}>
          {t("events.previewResults")}
        </Link>
        <Button
          title={t("common.signOut")}
          variant="secondary"
          onPress={async () => {
            await logout();
            router.replace("/login");
          }}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: colors.surface, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 16, gap: 4 },
  cardTitle: { fontSize: 18, fontWeight: "700", color: colors.ink },
  cardMeta: { fontSize: 15, color: colors.muted },
  cardRole: { fontSize: 14, fontWeight: "600", color: colors.ink },
  link: { fontSize: 16, color: colors.ink, textDecorationLine: "underline", textAlign: "center" },
});
