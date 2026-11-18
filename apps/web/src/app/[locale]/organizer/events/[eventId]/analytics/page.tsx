import { EventAnalytics } from "@/components/organizer/event-analytics";

// The event layout reads the event on the client (inside Suspense); so does this tab.
export default function Page() {
  return <EventAnalytics />;
}
