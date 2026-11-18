import { useTranslation } from "react-i18next";
import { ScrollView } from "react-native";

import { ResultView } from "@/components/result-view";
import { Body } from "@/components/ui";
import { RESULT_STATES } from "@/lib/checkin";

/** Every result screen side by side, for training door staff and for review. */
export default function ResultPreviewScreen() {
  const { t } = useTranslation();
  return (
    <ScrollView contentContainerStyle={{ padding: 24, gap: 16 }}>
      <Body>{t("result.mockNotice")}</Body>
      {RESULT_STATES.map((state) => (
        <ResultView
          key={state}
          state={state}
          details={
            state === "invalid"
              ? { campaign: true }
              : { attendeeName: "Aigerim N", ticketTypeName: "Standard", ticketNumber: "BFT-7K2P-9XQM" }
          }
        />
      ))}
    </ScrollView>
  );
}
