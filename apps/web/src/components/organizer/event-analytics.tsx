"use client";

import { AnalyticsDashboard } from "./analytics-dashboard";
import { useOrganizerEvent } from "./event-shell";

/** The event's Analytics tab: the dashboard scoped to this event. */
export function EventAnalytics() {
  const { event } = useOrganizerEvent();
  return <AnalyticsDashboard eventId={event.id} />;
}
