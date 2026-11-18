import { Badge, type BadgeTone } from "./ui";

/**
 * A ticket shown as a ticket: the event part, a perforation, then the admission part with the
 * QR code and number. Children are the actions (PDF download, help link).
 */
export function TicketCard({
  qr,
  number,
  numberLabel,
  title,
  details,
  status,
  note,
  children,
}: {
  qr: React.ReactNode;
  number: string;
  /** "Ticket number", for screen readers and the small label. */
  numberLabel?: string;
  title?: React.ReactNode;
  details: React.ReactNode;
  status?: { label: string; tone: BadgeTone };
  note?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex h-full flex-col overflow-hidden rounded-card border border-line bg-surface">
      <div className="space-y-2 p-5">
        {status && <Badge tone={status.tone}>{status.label}</Badge>}
        {title}
        <p className="text-sm text-ink-muted">{details}</p>
      </div>
      {/* Perforation: two notches and a dashed rule. */}
      <div aria-hidden="true" className="relative h-0">
        <span className="absolute -left-3 -top-3 h-6 w-6 rounded-full border border-line bg-paper" />
        <span className="absolute -right-3 -top-3 h-6 w-6 rounded-full border border-line bg-paper" />
        <span className="absolute inset-x-5 top-0 border-t-2 border-dashed border-line" />
      </div>
      <div className="flex flex-1 flex-col items-center gap-3 p-5 text-center">
        {qr}
        <p className="font-mono text-lg font-bold tracking-wider text-ink">
          {numberLabel && <span className="sr-only">{numberLabel}: </span>}
          {number}
        </p>
        {note}
        <div className="mt-auto flex flex-col items-center gap-2">{children}</div>
      </div>
    </div>
  );
}
