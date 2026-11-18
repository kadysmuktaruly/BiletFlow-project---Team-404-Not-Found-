# BiletFlow design direction ("Afisha")

The web app's visual system, and the reasons behind it. The tokens live in
`apps/web/src/app/globals.css` (one `@theme` block). The shared components are in
`apps/web/src/components/ui.tsx`. Every web screen is built from those two files.

## Where the principles come from

The brief named dice.fm as a reference for *principles*, not for its look. Its public pages
(home/browse, event detail, checkout) answer automated browsers with a Cloudflare bot check,
and we did not try to get past it, so this summary is based on our own familiarity with the
public site rather than fresh captures. Nothing of Dice's was copied: no logo, wordmark, name,
colours, fonts, icons, images, copy or code. BiletFlow keeps its own name and identity.

What we took from it, in our own words:

| Principle | What it means |
|---|---|
| **The event is the hero** | Artwork and the event title are by far the largest things on screen. Chrome (nav, filters, footers) stays small, monochrome and quiet. |
| **Type does the shouting** | Headlines are heavy, tightly tracked and large, and there are few of them. Body text stays plain. Hierarchy comes from size and weight, not from colour or boxes. |
| **Flat, not floaty** | No drop shadows or gradients. Surfaces are separated by a background tone or a single hairline. |
| **One obvious action** | Each screen has one primary CTA, usually a full-width pill. The price sits right next to it, so "how much" and "buy" read as one unit. |
| **Listings scan like a poster wall** | A grid of image-led tiles. Date, title, venue and price are always in the same order and position. |
| **Tickets look like tickets** | A ticket is shown as an object with a big scannable code and very little else around it. |
| **Calm motion** | Almost none. Pressed states and focus respond, and nothing animates on its own. |

## BiletFlow's own identity

"Afisha" is the word for a poster bill in Kazakh and Russian. Every event is shown as a
**typographic poster**: a solid colour block with the day of the month set huge in a sharp,
heavy face. When an organizer uploads a cover image, the image takes the poster's place. This
poster is the system's one bold element. Everything around it is disciplined and quiet.

The two accent colours come from Kazakhstan's flag (sky and sun), adjusted for contrast. They
are used for the posters, focus, links and the DEMO marker, never as decoration.

### Colour

Light base. The app is mostly forms, tables and dashboards for organizers and admins, and a
dark base would cost contrast in charts and dense tables. The dark ink is used as the colour
of the primary actions instead.

| Token | Hex | Role |
|---|---|---|
| `paper` | `#EEF0F3` | Page background (cool grey) |
| `surface` | `#FFFFFF` | Cards, inputs, header |
| `ink` | `#101418` | Text, primary buttons, one poster colour |
| `ink-muted` | `#4A5260` | Secondary text, hints, metadata |
| `line` | `#D5D9E0` | Decorative dividers and card borders only (not used as the only edge of a control) |
| `line-strong` | `#868E9B` | Input and secondary-button borders (UI ≥ 3:1) |
| `sky` | `#00A3C4` | Poster colour, with ink text |
| `sky-ink` | `#00677F` | Links, focus ring, active tab, date line |
| `sun` | `#FFC61A` | Poster colour and the DEMO marker, with ink text |
| `steppe` | `#1D6B47` | Poster colour, with white text |
| `pomegranate` | `#B4233F` | Poster colour, with white text |
| `danger` / `danger-soft` | `#B42318` / `#FDECEA` | Errors, destructive buttons |
| `success` / `success-soft` | `#1E7A46` / `#E6F4EC` | Success states |
| `info-soft` | `#E3F4F8` | Info alerts (with ink text) |
| `demo-soft` | `#FFF1C2` | DEMO banners (with ink text) |

### Contrast (WCAG 2.1 AA)

Computed with the WCAG relative-luminance formula. Requirement: text ≥ 4.5:1, large text and
UI ≥ 3:1.

| Foreground | Background | Ratio | Use | Result |
|---|---|---|---|---|
| ink `#101418` | surface `#FFFFFF` | 18.50 | body text | pass |
| ink `#101418` | paper `#EEF0F3` | 16.20 | body text | pass |
| ink-muted `#4A5260` | surface `#FFFFFF` | 7.87 | secondary text | pass |
| ink-muted `#4A5260` | paper `#EEF0F3` | 6.90 | secondary text | pass |
| sky-ink `#00677F` | surface `#FFFFFF` | 6.47 | links, focus ring | pass |
| sky-ink `#00677F` | paper `#EEF0F3` | 5.67 | links, focus ring | pass |
| line-strong `#868E9B` | surface `#FFFFFF` | 3.30 | input borders (UI) | pass |
| surface `#FFFFFF` | ink `#101418` | 18.50 | primary button, ink poster | pass |
| ink `#101418` | sky `#00A3C4` | 6.20 | sky poster text | pass |
| ink `#101418` | sun `#FFC61A` | 11.75 | sun poster, DEMO badge | pass |
| surface `#FFFFFF` | steppe `#1D6B47` | 6.47 | steppe poster text | pass |
| surface `#FFFFFF` | pomegranate `#B4233F` | 6.46 | pomegranate poster text | pass |
| surface `#FFFFFF` | danger `#B42318` | 6.57 | danger button | pass |
| danger `#B42318` | surface `#FFFFFF` | 6.57 | error text | pass |
| danger `#B42318` | danger-soft `#FDECEA` | 5.75 | error alert | pass |
| success `#1E7A46` | surface `#FFFFFF` | 5.35 | success text | pass |
| success `#1E7A46` | success-soft `#E6F4EC` | 4.71 | success alert | pass |
| ink `#101418` | info-soft `#E3F4F8` | 16.35 | info alert | pass |
| ink `#101418` | demo-soft `#FFF1C2` | 16.40 | DEMO banner | pass |

Pairs we tested and **do not** use:

- `sky` as text or as a control edge on white (2.98:1). It is a fill only.
- A lighter grey `#6B7380` on paper (4.19:1). It was dropped, and all secondary text uses
  `ink-muted`.
- `sky-ink` on ink (2.86:1). Focus inside dark areas uses `#7FDDF0` instead (11.9:1 on ink).

### Typography

**Geologica** (Google Fonts, OFL), self-hosted through `next/font/google` with the latin,
cyrillic and cyrillic-ext subsets. It is one variable family used for everything. We checked
its glyph coverage by downloading the font and reading its character map: it has every Kazakh
letter (Әә Ғғ Ққ Ңң Өө Ұұ Үү Һһ Іі) and the tenge sign ₸. Two other candidates failed the same
check: Unbounded is missing Әә Ғғ Ққ Ңң Өө Ұұ Үү Һһ, and Manrope is missing Әә Ғғ Ққ Ңң Ұұ and ₸.

The headline treatment uses Geologica's **sharpness axis** (`SHRP` 100): display text has
cut, angular corners at weight 800 with tight tracking. Body text stays at the default round
cut, weight 400. Same family, two clearly different voices.

| Step | Size / line height | Weight | Use |
|---|---|---|---|
| display | 2.25rem → 3.5rem (clamp) / 1.0 | 800, sharp | Home headline, event title, poster day |
| h1 | 1.75rem → 2.25rem / 1.1 | 800, sharp | Page titles |
| h2 | 1.25rem / 1.25 | 700, sharp | Section titles |
| h3 | 1.0625rem / 1.35 | 700 | Card titles |
| body | 1rem / 1.55 | 400 | Text |
| small | 0.875rem / 1.45 | 400–600 | Metadata, hints |
| micro | 0.8125rem / 1.3 | 600 | Badges |

Long Kazakh and Russian words: headings wrap between whole words, with no automatic
hyphenation. `overflow-wrap: break-word` breaks a word only when it alone is wider than the
screen, so nothing overflows at 390px.

### Layout, spacing, shape

- 4px base spacing scale (Tailwind's). Page gutter 16px on mobile, 24px from `sm`.
  Content max width 72rem; reading text max 65ch.
- Left-aligned everywhere. The home headline is left-aligned too, poster-style.
- Corner radius follows hierarchy rather than one value for everything: posters and event
  tiles 20px (`--radius-poster`), cards and panels 16px (`--radius-card`), inputs 12px
  (`--radius-field`), and buttons, badges and tabs fully round (pills).
- Separation is flat: `surface` on `paper`, plus a 1px `line` border on cards. No shadows
  except one for the modal, which sits above the page.
- Touch targets are at least 44px tall (buttons and inputs are 44–48px).

### Images

- With a cover image: the image fills the poster frame (`object-cover`, 4:5 on the event page,
  4:3 in listings). Alt text is unchanged (decorative `alt=""`, since the title follows).
- Without one: the typographic poster. Its colour is picked from the five poster colours by a
  stable hash of the event id, so an event keeps its colour everywhere.

### Patterns

- **Buttons**: pills. `primary` is ink with white text, `secondary` is white with a
  `line-strong` border, `danger` is the danger red, and `ghost` is text-only for low-emphasis
  actions. They are 44px tall. Pressing scales them to 0.98 (skipped under reduced motion).
- **Inputs**: 48px tall, 12px radius, 1px `line-strong` border, a visible label above, the
  hint below in `ink-muted`, and the error below in `danger` with a danger border.
- **Focus**: a 3px `sky-ink` outline with a 2px offset on every interactive element. It is
  more visible than before, and never removed.
- **Price and CTA**: the total is set large in the display face right above a full-width
  primary pill. On desktop the ticket panel is sticky beside the event details.
- **Ticket display**: a ticket card with a perforated divider (two notches and a dashed rule)
  between the event part and the QR part. The QR sits on white with a quiet zone and is at
  least 160px.
- **Empty states**: a dashed-border panel with the existing message and, where the screen
  already has one, its call to action.
- **Badges**: small pills. Status colour comes with its text, never colour alone. **DEMO** is
  ink on sun with an ink border, deliberately loud.
- **Motion**: only in response to the user (press, focus, and the modal opening with a short
  fade). `prefers-reduced-motion` turns it off.

## Screen mapping

| Screen | How the principles apply |
|---|---|
| **Event list** | Poster wall: a 1/2/3-column grid of EventCards (poster with the big day, then the date line in sky-ink, the title, the venue, and a price pill). Search is one rounded field with an attached button. |
| **Event detail** | A two-column hero: the poster or cover on the left, and the display-size title, date, venue and organizer on the right. Description in a 65ch column. The ticket panel is a sticky card with one row per ticket type, the total in the display face, and a full-width primary pill. |
| **Checkout + DEMO payment** | One narrow column. The DEMO badge sits beside the title and the DEMO banner stays at the top. The order summary is a receipt-style card, with the total large. Pay is the one primary pill; "fail" and "cancel" are secondary. |
| **Confirmation** | Big "You're going!" headline. The tickets are shown as ticket cards with the PDF action on each. |
| **My tickets** | A stack of ticket cards (event part, perforation, QR part), one per ticket, with the status badge. |
| **Auth pages** | A single centred card on paper, with the title in the display face, full-width inputs and a full-width primary pill. Secondary links sit below. |
| **Organizer dashboard** | The same tokens, quieter. The event header gets the title in the display face, actions as pills, and tabs as a horizontally scrollable pill bar on mobile. Panels are cards, and tables keep their structure with hairline rows. Analytics KPIs are flat stat cards. |
| **Admin** | The same as the organizer screens: pill tabs, flat cards, hairline tables. DEMO notes keep their marker. |
