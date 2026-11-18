import { router, Stack, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";

import { Banner, Body, colors, Field, Screen } from "@/components/ui";
import { errorKey } from "@/lib/api";
import { searchAttendees, type CheckInTicket } from "@/lib/checkin";

type Params = { eventId: string; title?: string; timezone?: string; canUndo?: string };

const STATUS_COLOR: Record<CheckInTicket["status"], string> = {
  valid: "#15803d",
  checked_in: "#b45309",
  cancelled: "#374151",
  refunded: "#6d28d9",
};

/** SRS 4.8 "Search for attendees manually": find a ticket when its QR won't scan, then
 * check it in with the same atomic call as a scan. */
export default function SearchScreen() {
  const { t, i18n } = useTranslation();
  const { eventId, title, timezone, canUndo } = useLocalSearchParams<Params>();
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState<{ q: string; tickets?: CheckInTicket[]; error?: string } | null>(null);

  useEffect(() => {
    let active = true;
    const q = query;
    // Wait for a pause in typing before asking the server.
    const timer = setTimeout(() => {
      searchAttendees(eventId, q)
        .then((r) => active && setAnswer({ q, tickets: r.tickets }))
        .catch((err: unknown) => active && setAnswer({ q, error: t(errorKey(err, (k) => i18n.exists(k))) }));
    }, 300);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [eventId, query, t, i18n]);

  return (
    <Screen>
      <Stack.Screen options={{ title: title ?? t("search.title") }} />
      <Field
        label={t("search.label")}
        placeholder={t("search.placeholder")}
        value={query}
        onChangeText={setQuery}
        autoCorrect={false}
        autoCapitalize="none"
        returnKeyType="search"
      />
      {answer?.error ? <Banner kind="error">{answer.error}</Banner> : null}
      {!answer ? <Body>{t("common.loading")}</Body> : null}
      <FlatList
        data={answer?.tickets ?? []}
        keyExtractor={(item) => item.id}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ gap: 10 }}
        ListEmptyComponent={answer?.tickets ? <Body>{t("search.empty")}</Body> : undefined}
        renderItem={({ item }) => (
          <Pressable
            accessibilityRole="button"
            accessibilityHint={t("search.checkInHint")}
            accessibilityLabel={`${item.attendee_name}, ${item.ticket_type_name}, ${item.ticket_number}, ${t(`search.status.${item.status}`)}`}
            onPress={() =>
              router.push({ pathname: "/result", params: { eventId, ticketId: item.id, timezone, canUndo } })
            }
            style={({ pressed }) => [styles.row, pressed && { opacity: 0.8 }]}
          >
            <View style={{ flex: 1 }}>
              <Text style={styles.name}>{item.attendee_name}</Text>
              <Text style={styles.meta}>
                {item.ticket_type_name} · {item.ticket_number}
              </Text>
            </View>
            <Text style={[styles.status, { borderColor: STATUS_COLOR[item.status], color: STATUS_COLOR[item.status] }]}>
              {t(`search.status.${item.status}`)}
            </Text>
          </Pressable>
        )}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 12, backgroundColor: colors.surface, borderRadius: 12, borderWidth: 1, borderColor: colors.border, padding: 14, minHeight: 56 },
  name: { fontSize: 17, fontWeight: "700", color: colors.ink },
  meta: { fontSize: 14, color: colors.muted },
  status: { fontSize: 14, fontWeight: "700", borderWidth: 2, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
});
