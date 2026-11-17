import { router, Stack, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Alert, ScrollView, StyleSheet, Text } from "react-native";

import { ResultView } from "@/components/result-view";
import { Banner, Body, Button, colors } from "@/components/ui";
import { errorKey } from "@/lib/api";
import {
  checkInTicket,
  formatTime,
  invalidReasonKey,
  scanTicket,
  undoCheckIn,
  type CheckInStats,
  type ScanResult,
} from "@/lib/checkin";

type Params = {
  eventId: string;
  // From the camera: the raw QR text. From manual search: the ticket id.
  payload?: string;
  ticketId?: string;
  timezone?: string;
  canUndo?: string;
};

/** The live check-in result (SRS 4.8): color, symbol and words for all five states, the
 * attendee, why an invalid code failed, live counts, and an authorized undo. */
export default function ResultScreen() {
  const { t, i18n } = useTranslation();
  const { eventId, payload, ticketId, timezone, canUndo } = useLocalSearchParams<Params>();
  const [result, setResult] = useState<ScanResult | null>(null);
  const [stats, setStats] = useState<CheckInStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [undone, setUndone] = useState(false);
  const [busy, setBusy] = useState(false);
  const message = useCallback((err: unknown) => t(errorKey(err, (k) => i18n.exists(k))), [t, i18n]);

  const request = useCallback(
    () => (ticketId ? checkInTicket(eventId, ticketId) : scanTicket(eventId, payload ?? "")),
    [eventId, payload, ticketId],
  );
  const show = useCallback((r: ScanResult) => {
    setResult(r);
    setStats(r.stats);
  }, []);

  // One check-in request per screen, even if the effect runs twice: the server records the
  // check-in, so a second call would wrongly report "already used".
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    request()
      .then(show)
      .catch((err: unknown) => setError(message(err)));
  }, [request, show, message]);

  async function retry() {
    setError(null);
    setBusy(true);
    try {
      show(await request());
    } catch (err) {
      setError(message(err));
    } finally {
      setBusy(false);
    }
  }

  function confirmUndo() {
    if (!result?.ticket) return;
    const id = result.ticket.id;
    Alert.alert(t("result.undoTitle"), t("result.undoText", { name: result.ticket.attendee_name }), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("result.undo"),
        style: "destructive",
        onPress: async () => {
          setBusy(true);
          try {
            const r = await undoCheckIn(eventId, id);
            setStats(r.stats);
            setUndone(true);
          } catch (err) {
            setError(message(err));
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  const ticket = result?.ticket;
  const reasonKey = result ? invalidReasonKey(result) : null;
  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Stack.Screen options={{ title: t("result.title") }} />
      {!result && !error ? <Body>{t("result.checking")}</Body> : null}
      {error ? (
        <>
          <Banner kind="error">{error}</Banner>
          <Button title={t("common.retry")} busy={busy} onPress={() => void retry()} />
        </>
      ) : null}
      {result ? (
        <ResultView
          state={result.result}
          details={{
            attendeeName: ticket?.attendee_name,
            ticketTypeName: ticket?.ticket_type_name,
            ticketNumber: ticket?.ticket_number,
            checkedInAt: result.result === "already_used" ? formatTime(ticket?.checked_in_at, timezone, i18n.language) : null,
            reason: reasonKey ? t(reasonKey) : null,
          }}
        />
      ) : null}
      {undone ? <Banner kind="success">{t("result.undone")}</Banner> : null}
      {stats ? (
        <Text accessibilityLiveRegion="polite" style={styles.counts}>
          {t("counts", { checkedIn: stats.checked_in, registered: stats.registered })}
        </Text>
      ) : null}
      {result?.result === "valid" && canUndo === "true" && !undone ? (
        <Button title={t("result.undo")} variant="secondary" busy={busy} onPress={confirmUndo} />
      ) : null}
      <Button title={t("result.scanNext")} onPress={() => router.back()} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 24, gap: 16, backgroundColor: colors.background, flexGrow: 1 },
  counts: { fontSize: 18, fontWeight: "700", color: colors.ink, textAlign: "center" },
});
