import { Suspense } from "react";

import { CampaignLanding } from "@/components/attendee/campaign-landing";

// A Campaign QR opens here (SRS 4.14, UC10). The page resolves the opaque token on the server
// and forwards to the event with the code applied. It never shows a ticket or admits anyone.
export default function Page() {
  return (
    <Suspense>
      <CampaignLanding />
    </Suspense>
  );
}
