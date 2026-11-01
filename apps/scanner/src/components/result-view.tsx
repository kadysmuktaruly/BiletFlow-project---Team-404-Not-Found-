import { useTranslation } from "react-i18next";
import { StyleSheet, Text, View } from "react-native";

import type { ResultState } from "@/lib/checkin";

// Color plus a symbol plus words: never color alone (colour-blind staff, glare, grayscale).
const LOOK: Record<ResultState, { background: string; foreground: string; symbol: string }> = {
  valid: { background: "#15803d", foreground: "#ffffff", symbol: "✓" },
  invalid: { background: "#b91c1c", foreground: "#ffffff", symbol: "✕" },
  cancelled: { background: "#374151", foreground: "#ffffff", symbol: "⊘" },
  refunded: { background: "#6d28d9", foreground: "#ffffff", symbol: "↩" },
  already_used: { background: "#b45309", foreground: "#ffffff", symbol: "!" },
};

export type ResultDetails = {
  attendeeName?: string | null;
  ticketTypeName?: string | null;
  ticketNumber?: string | null;
  checkedInAt?: string | null;
  campaign?: boolean;
};

export function ResultView({ state, details = {} }: { state: ResultState; details?: ResultDetails }) {
  const { t } = useTranslation();
  const look = LOOK[state];
  const rows: [string, string | null | undefined][] = [
    [t("result.attendee"), details.attendeeName],
    [t("result.ticketType"), details.ticketTypeName],
    [t("result.ticketNumber"), details.ticketNumber],
    [t("result.checkedInAt"), details.checkedInAt],
  ];
  return (
    <View
      testID={`result-${state}`}
      accessible
      accessibilityRole="alert"
      accessibilityLiveRegion="assertive"
      accessibilityLabel={`${t(`result.${state}.title`)}. ${t(`result.${state}.text`)}`}
      style={[styles.panel, { backgroundColor: look.background }]}
    >
      <Text style={[styles.symbol, { color: look.foreground }]}>{look.symbol}</Text>
      <Text style={[styles.title, { color: look.foreground }]}>{t(`result.${state}.title`)}</Text>
      <Text style={[styles.text, { color: look.foreground }]}>{t(`result.${state}.text`)}</Text>
      {details.campaign ? (
        <Text style={[styles.text, styles.bold, { color: look.foreground }]}>{t("result.campaign")}</Text>
      ) : null}
      {rows.some(([, v]) => v) ? (
        <View style={styles.details}>
          {rows
            .filter(([, v]) => v)
            .map(([label, value]) => (
              <Text key={label} style={[styles.detail, { color: look.foreground }]}>
                {label}: <Text style={styles.bold}>{value}</Text>
              </Text>
            ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  panel: { borderRadius: 16, padding: 28, alignItems: "center", gap: 10 },
  symbol: { fontSize: 72, fontWeight: "800", lineHeight: 80 },
  title: { fontSize: 34, fontWeight: "800", textAlign: "center" },
  text: { fontSize: 18, textAlign: "center", lineHeight: 24 },
  bold: { fontWeight: "700" },
  details: { marginTop: 8, alignSelf: "stretch", gap: 4 },
  detail: { fontSize: 17 },
});
