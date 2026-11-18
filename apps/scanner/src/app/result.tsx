import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";

import { ResultView } from "@/components/result-view";
import { Body, Button, Screen } from "@/components/ui";
import { classifyPayload, mockResult } from "@/lib/checkin";

/** Report 3: the result is simulated locally. Report 4 replaces this with the live
 * check-in call, which validates the signature and the ticket's current status. */
export default function ResultScreen() {
  const { t } = useTranslation();
  const { payload = "" } = useLocalSearchParams<{ eventId: string; payload: string }>();
  const state = mockResult(payload);
  return (
    <Screen>
      <ResultView state={state} details={{ campaign: classifyPayload(payload) === "campaign" }} />
      <Body>{t("result.mockNotice")}</Body>
      <Button title={t("result.scanNext")} onPress={() => router.back()} />
    </Screen>
  );
}
