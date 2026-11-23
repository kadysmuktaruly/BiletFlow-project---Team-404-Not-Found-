import { router, Stack, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, View } from "react-native";

import { NotCheckedInView, ResultView } from "@/components/result-view";
import { Banner, Button, colors } from "@/components/ui";
import { errorKey, isNetworkError } from "@/lib/api";
import {
  campaignRejection,
  checkInTicket,
  formatTime,
  invalidReasonKey,
  isCampaignQr,
  scanTicket,
  undoCheckIn,
  type CheckInStats,
  type DoorResult,
} from "@/lib/checkin";

type Params = {
  eventId: string;
  // From the camera: the raw QR text. From manual search: the ticket id.
  payload?: string;
  ticketId?: string;
  timezone?: string;
  canUndo?: string;
};

type Failure = { offline: boolean; detail: string | null };

/** The live check-in result (SRS 4.8): color, symbol and words for all five states, the
 * attendee, why an invalid code failed, live counts, and an authorized undo. */
export default function ResultScreen() {
  const { t, i18n } = useTranslation();
  const { eventId, payload, ticketId, timezone, canUndo } = useLocalSearchParams<Params>();
  const [result, setResult] = useState<DoorResult | null>(null);
  const [stats, setStats] = useState<CheckInStats | null>(null);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [undoError, setUndoError] = useState<string | null>(null);
  const [undone, setUndone] = useState(false);
  const [busy, setBusy] = useState(false);
  const message = useCallback((err: unknown) => t(errorKey(err, (k) => i18n.exists(k))), [t, i18n]);
  const fail = useCallback(
    (err: unknown) =>
      setFailure(isNetworkError(err) ? { offline: true, detail: null } : { offline: false, detail: message(err) }),
    [message],
  );

  const request = useCallback((): Promise<DoorResult> => {
    if (ticketId) return checkInTicket(eventId, ticketId);
    // A promo QR is never a ticket: reject it on the phone, even with no connection (SRS 4.14).
    if (payload && isCampaignQr(payload)) return Promise.resolve(campaignRejection());
    return scanTicket(eventId, payload ?? "");
  }, [eventId, payload, ticketId]);
  const show = useCallback((r: DoorResult) => {
    setResult(r);
    if (r.stats) setStats(r.stats);
  }, []);

  // One check-in request per screen, even if the effect runs twice: the server records the
  // check-in, so a second call would wrongly report "already used".
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    request().then(show).catch(fail);
  }, [request, show, fail]);

  async function retry() {
    setFailure(null);
    setBusy(true);
    try {
      show(await request());
    } catch (err) {
      fail(err);
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
          setUndoError(null);
          try {
            const r = await undoCheckIn(eventId, id);
            setStats(r.stats);
            setUndone(true);
          } catch (err) {
            setUndoError(`${t("result.undoFailed")} ${message(err)}`);
          } finally {
            setBusy(false);
          }
        },
      },
    ]);
  }

  const ticket = result?.ticket;
  const reasonKey = result ? invalidReasonKey(result) : null;
  // Owners and event admins can reverse a check-in: right after it ("valid") or when they
  // find it later ("already used"). The API enforces the same rule.
  const undoable = canUndo === "true" && !!ticket && (result?.result === "valid" || result?.result === "already_used");
  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Stack.Screen options={{ title: t("result.title") }} />
      {!result && !failure ? (
        <View testID="result-checking" accessible accessibilityLiveRegion="polite" style={styles.checking}>
          <ActivityIndicator size="large" color={colors.ink} />
          <Text style={styles.checkingText}>{t("result.checking")}</Text>
        </View>
      ) : null}
      {failure ? (
        <>
          <NotCheckedInView offline={failure.offline} detail={failure.detail} />
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
      {undoError ? <Banner kind="error">{undoError}</Banner> : null}
      {stats ? (
        <Text accessibilityLiveRegion="polite" style={styles.counts}>
          {t("counts", { checkedIn: stats.checked_in, registered: stats.registered })}
        </Text>
      ) : null}
      {undoable && !undone ? (
        <Button title={t("result.undo")} variant="secondary" busy={busy} onPress={confirmUndo} />
      ) : null}
      <Button title={t("result.scanNext")} onPress={() => router.back()} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { padding: 24, gap: 16, backgroundColor: colors.background, flexGrow: 1 },
  checking: { alignItems: "center", gap: 16, paddingVertical: 48 },
  checkingText: { fontSize: 20, fontWeight: "700", color: colors.ink, textAlign: "center" },
  counts: { fontSize: 18, fontWeight: "700", color: colors.ink, textAlign: "center" },
});
