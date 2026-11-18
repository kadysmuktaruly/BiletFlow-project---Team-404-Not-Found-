import { Suspense } from "react";

import { RequireAuth } from "@/components/require-auth";

// RequireAuth reads the current path (to come back after sign-in), which is only known at
// request time, so it sits inside a Suspense boundary.
export default function OrganizerLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense>
      <RequireAuth role="organizer">{children}</RequireAuth>
    </Suspense>
  );
}
