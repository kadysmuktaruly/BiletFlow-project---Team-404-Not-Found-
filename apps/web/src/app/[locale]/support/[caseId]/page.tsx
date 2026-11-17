import { Suspense } from "react";

import { RequireAuth } from "@/components/require-auth";
import { CasePage } from "@/components/support/case-page";

// The [locale] layout sets the request locale; the case id is read on the client (inside
// Suspense), so nothing here waits on request data during prerendering.
export default function Page() {
  return (
    <Suspense>
      <RequireAuth>
        <CasePage />
      </RequireAuth>
    </Suspense>
  );
}
