import { Suspense } from "react";

import { RequireAuth } from "@/components/require-auth";
import { OrderPage } from "@/components/attendee/order-page";

// The [locale] layout sets the request locale; the dynamic param is read on the client.
export default function Page() {
  return (
    <Suspense>
      <RequireAuth>
        <OrderPage />
      </RequireAuth>
    </Suspense>
  );
}
