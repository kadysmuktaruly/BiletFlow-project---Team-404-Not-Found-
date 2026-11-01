import { Suspense } from "react";

import { EventShell } from "@/components/organizer/event-shell";

export default function EventLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense>
      <EventShell>{children}</EventShell>
    </Suspense>
  );
}
