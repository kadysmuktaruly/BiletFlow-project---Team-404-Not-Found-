import { Suspense } from "react";

import { RequireAuth } from "@/components/require-auth";
import { CheckoutPage } from "@/components/attendee/checkout-page";

// The [locale] layout sets the request locale; the dynamic param is read on the client.
export default function Page() {
  return (
    <Suspense>
      <RequireAuth>
        <CheckoutPage />
      </RequireAuth>
    </Suspense>
  );
}
