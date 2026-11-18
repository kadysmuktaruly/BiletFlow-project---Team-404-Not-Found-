"use client";

import { useFormatter } from "next-intl";

import { Link } from "@/i18n/navigation";

// The "Afisha" poster: the design system's one bold element (docs/design-direction.md).
// An event without a cover image gets a typographic poster in one of five colours, picked by
// a stable hash of its id so the same event always has the same colour.

const POSTERS = [
  "bg-ink text-surface on-dark",
  "bg-sky text-ink",
  "bg-sun text-ink",
  "bg-steppe text-surface on-dark",
  "bg-pomegranate text-surface on-dark",
] as const;

function posterColour(seed: string): string {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  return POSTERS[hash % POSTERS.length];
}

/** The poster block: the cover image if there is one, otherwise the date set huge. Decorative
 * (aria-hidden): the same date and title are always given as text next to it. */
export function Poster({
  seed,
  startsAt,
  timezone,
  imageUrl,
  aspect = "aspect-[4/3]",
  className = "",
}: {
  seed: string;
  startsAt: string;
  timezone: string;
  imageUrl?: string | null;
  aspect?: string;
  className?: string;
}) {
  const format = useFormatter();
  const date = new Date(startsAt);
  // Some browsers have no month or weekday names for a locale (Kazakh in Chromium gives
  // "M11" and an English weekday); the poster then shows the month as a number and leaves
  // the weekday out.
  const month = format.dateTime(date, { month: "short", timeZone: timezone }).replace(".", "");
  const named = !/^M\d+$/i.test(month);
  if (imageUrl) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- organizer-supplied URL, any host
      <img src={imageUrl} alt="" className={`${aspect} w-full rounded-poster bg-paper object-cover ${className}`} />
    );
  }
  return (
    <div
      aria-hidden="true"
      className={`${aspect} relative flex w-full flex-col justify-between overflow-hidden rounded-poster p-5 ${posterColour(seed)} ${className}`}
    >
      <span className="text-sm font-semibold capitalize opacity-90">
        {named && format.dateTime(date, { weekday: "long", timeZone: timezone })}
      </span>
      <span className="flex items-end gap-3">
        <span className="font-display text-[clamp(4.5rem,18vw,7rem)] leading-[0.8]">
          {format.dateTime(date, { day: "numeric", timeZone: timezone })}
        </span>
        <span className="font-display pb-1 text-2xl leading-none lowercase">
          {named ? month : `/${format.dateTime(date, { month: "2-digit", timeZone: timezone })}`}
        </span>
      </span>
    </div>
  );
}

/** One event in a listing: poster, then date, title, venue and price in a fixed order. */
export function EventCard({
  href,
  seed,
  title,
  startsAt,
  timezone,
  when,
  venue,
  price,
  imageUrl,
}: {
  href: string;
  seed: string;
  title: string;
  startsAt: string;
  timezone: string;
  /** The formatted date line, as the rest of the app shows it. */
  when: string;
  venue?: string | null;
  price?: string | null;
  imageUrl?: string | null;
}) {
  return (
    <Link href={href} className="group flex h-full flex-col gap-3 rounded-poster">
      <Poster seed={seed} startsAt={startsAt} timezone={timezone} imageUrl={imageUrl} />
      <div className="flex flex-1 flex-col gap-1 px-1">
        <p className="text-sm font-semibold text-sky-ink">{when}</p>
        <h2 className="font-display text-xl leading-tight text-ink group-hover:underline group-hover:decoration-2 group-hover:underline-offset-4">
          {title}
        </h2>
        {venue && <p className="text-sm text-ink-muted">{venue}</p>}
        {price && (
          <p className="mt-auto pt-2">
            <span className="inline-flex rounded-full border border-ink px-3 py-1 text-sm font-semibold text-ink">{price}</span>
          </p>
        )}
      </div>
    </Link>
  );
}
