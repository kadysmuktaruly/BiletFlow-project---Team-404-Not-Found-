# Scanner app: SRS requirements check

This doc checks the Event Admin scanner app (`apps/scanner`) and the check-in API
(`apps/api/app/routers/checkin.py`, `app/services/checkin.py`) against every mobile-app
requirement in the SRS (`docs/srs/BiletFlow_SRS_v0.3.pdf`; the text copy is
`docs/srs/srs.md`). Sections read: §1.3, §2.3, §4.7, §4.8, §4.14, §4.16, §7, §8, §10, §11,
UC4 and UC7.

Checked on branch `fix/scanner-srs-compliance` on 2026-11-23. The scanner had 31 jest tests
and now has 70. The API had 255 pytest tests and now has 259.

Status key:

- **Pass**: the requirement was already met and a test proves it.
- **Fixed**: the audit found a gap, this branch fixed it, and a test proves the fix.
- **Manual only**: automated tests can't cover it (a real camera, a real phone or real
  network), so it is on the [manual device test](#manual-device-test) list.

Test locations: scanner tests are in `apps/scanner/src/__tests__/` (jest, run with
`npm test -w @biletflow/scanner`). API tests are in `apps/api/tests/` (pytest, run with
`uv run pytest` from `apps/api`).

## Results

| # | Requirement | SRS | Status | Evidence (test, file) | Notes |
|---|---|---|---|---|---|
| 1 | Event Admins sign in securely. The session is kept in SecureStore, not AsyncStorage, and sign-out clears it. | §4.8, §7 | Pass (tests added) | `auth.test.tsx`: "keeps the refresh token in SecureStore…", "restores the session at launch…", "sign-out deletes the stored token…", "never depends on AsyncStorage"; `login.test.tsx` | The refresh token goes to the keychain/keystore through `expo-secure-store`, and the access token stays in memory only. AsyncStorage isn't a dependency at all. Sign-out deletes the stored token and clears the in-memory one. Earlier there was no test for this. |
| 2 | The event list shows only assigned events. The server enforces it: an unassigned event returns 404, and so does a check-in on it. | §4.8, §2.3, UC4 | Pass (app test added) | API: `test_checkin_events_lists_only_assignments`, `test_only_owner_and_assigned_staff_can_use_the_door` (`test_checkin_events.py`, `test_checkin.py`). App: `home.test.tsx` "lists exactly the events the server returns" | The server builds the list from `StaffAssignment` (revoked ones excluded). Strangers, platform admins and revoked staff get `404 event_not_found` on scan, manual check-in, undo, stats and search. The event's **owner** (the organizer) also sees it, as role "Organizer". That follows §2.3 (the organizer manages the event). |
| 3 | The camera scans ticket QR codes. Camera permission is requested, and denial shows a clear screen with retry or open settings. | §4.8, §10 | Fixed | `scan.test.tsx`: "asks for camera permission…", "shows a blocked screen with Open settings…", "re-checks permission when the app returns from settings", "only scans while the screen is in front" | **Was failing:** after a permanent denial the scan screen offered only "Allow camera", which does nothing once the OS stops asking. There was no "Open settings", and the screen didn't re-check permission when you came back from Settings. The camera also kept reading codes while the result screen was on top, so a ticket still in view could open a second result ("Already used" on top of "Valid"). Fixed in `app/scan/[eventId].tsx`. Real camera decoding is manual. |
| 4 | Validation happens on the server in real time, checking the signature and the live status. The app never decides that a ticket is valid. | §4.8, §4.7 | Pass | API: `test_forged_tampered_and_garbage_payloads_are_invalid`, `test_cancelled_and_refunded_tickets_are_rejected_live`, `test_signed_token_for_a_ticket_that_does_not_exist_is_invalid`. App: `live-checkin.test.tsx` "sends the scanned code to the server…" | Tokens are `BFT1.<id>.<HMAC>`, and only the server holds the key. Status is read from the database on every scan. The app sends the raw QR text and shows whatever the server answers. The only thing it decides locally is to *reject* a Campaign QR (#10). It never admits anyone on its own. |
| 5 | All five results (valid, invalid, cancelled, refunded, already used) are shown with color and text. "Already used" shows when the earlier check-in happened. | §4.8 | Pass | `checkin.test.tsx` "renders the %s screen with a title and instructions" (all 5); `live-checkin.test.tsx` "shows %s from the server…", "shows when an already-used ticket was checked in, in the event's time zone" | Each result has its own color, its own symbol (✓ ✕ ⊘ ↩ !), a title and an instruction ("Do not admit"). Screen readers announce the result as an alert. The time is shown in the event's IANA time zone. |
| 6 | Check-in is atomic: two simultaneous scans produce exactly one check-in. | §4.8, UC4, §11 | Pass | `test_double_scan_concurrent_one_checkin`, `test_manual_and_scan_racing_admit_once` (`test_checkin.py`) | One conditional `UPDATE … WHERE status='valid' RETURNING`. Ten concurrent requests, each on its own pooled connection (see `tests/conftest.py`), give one `valid`, nine `already_used`, one `CheckInRecord` and one audit entry. The partial unique index `uq_checkin_active_ticket` backs it up. |
| 7 | Manual search by name, email or ticket ID can check someone in, under the same rules as scanning. | §4.8, §2.3 | Pass | `test_manual_search_and_check_in` (`test_checkin.py`); `search.test.tsx`; `live-checkin.test.tsx` "checks in a ticket chosen from manual search" | It matches name, email or ticket number without regard to case, and treats LIKE wildcards literally. The check-in runs through the same `_check_in` as a scan, so a repeat gives "already used" and another event's ticket gives "invalid". |
| 8 | Authorized staff can undo a check-in, and the ticket can be checked in again. Unauthorized users can't undo. | §4.8, UC4 | Fixed | API: `test_undo_by_event_admin_and_owner_writes_audit_and_allows_rescan`, `test_check_in_staff_cannot_undo`. App: `live-checkin.test.tsx` "undoes a check-in after confirmation…", "offers undo on an already-used ticket…", "doesn't offer undo to check-in staff" | **Was partly failing:** the app offered Undo only on the `valid` screen, right after the scan. If an accidental check-in was noticed later (scan again or find in search, then see "Already used"), there was no way to undo it in the app. Undo is now offered on "Already used" too, to owners and event admins only. The server still enforces this (check-in staff get `403 checkin_undo_forbidden`). |
| 9 | Registered and checked-in counts are correct and refresh after each scan or undo. | §4.8 | Pass (app test added) | API: `test_stats_count_registered_and_checked_in`, plus `stats` checked in the scan and undo tests. App: `live-checkin.test.tsx` (counts after scan and after undo), `scan.test.tsx` "refreshes the counts every time the scanner comes back into view" | Every scan, check-in and undo response carries fresh `stats`. The scan screen refetches when it regains focus and every 10 s. Registered = valid + checked in (refunded and cancelled are excluded). |
| 10 | A Campaign QR is always rejected with "Promo code, not a ticket", by the app and by the admission endpoint. A valid ticket scanned right after still works. | §4.14, §7, §11 | Fixed | API: `test_campaign_qr_is_never_admission`, `test_real_campaign_qr_is_rejected_and_the_next_ticket_still_works` (`test_scanner_srs.py`). App: `live-checkin.test.tsx` "rejects a Campaign QR on the phone, without the server and even offline", `checkin.test.tsx` "isCampaignQr" | **Was partly failing:** the app depended on the server to recognize a Campaign QR. With no connection, a promo QR showed a connection error instead of "promo code, not a ticket". The app now recognizes `BFC1.` campaign codes and links itself and rejects them at once (it can only reject, never admit). The endpoint still rejects them as before. The new API test decodes the **real** Campaign QR PDF with zxing, scans it, then admits a real ticket. |
| 11 | Paper and digital copies share one ID: scanning the PDF's QR after the email's QR shows "already used". Tested with the real PDF generator, pypdfium2 and zxing, including a grayscale render. | §4.7, UC7, §7, §11 | Pass (test added) | `test_email_qr_then_printed_pdf_qr_is_already_used` (`test_scanner_srs.py`); `test_pdf_qr_scans_from_a_grayscale_print_and_matches_the_digital_ticket` (`test_documents.py`) | The new test follows the order in the requirement. It decodes the QR image embedded in the confirmation **email**, scans it (`valid`), then renders the attached **PDF** in grayscale at 72, 150 and 300 dpi and scans that (`already_used`, with the same ticket and check-in time). The existing test covered PDF first, then digital. |
| 12 | Validation takes under 2 seconds. There is an API timing test on seeded data, and the app shows a loading state. | §7 | Fixed | API: `test_checkin_under_2s` (`test_checkin.py`), `test_checkin_under_2s_on_seeded_demo_data` (`test_scanner_srs.py`). App: `live-checkin.test.tsx` "shows a loading state while the server checks the ticket" | **Was partly failing:** the result screen showed only a small line of text while waiting, with no spinner and nothing marking it as busy. It now shows a large spinner and "Checking the ticket…". The new API test loads the real demo seed and times scan, undo and stats as the seeded Event Admin (`staff@demo.biletflow.kz`). The test runs in-process, so it measures the server, not the venue's network. That is on the manual list. |
| 13 | Every check-in and undo writes an audit entry and shows in the event's activity timeline. | §4.16, §7 | Pass (test added) | `test_double_scan_concurrent_one_checkin` (one audit entry), `test_undo_by_event_admin_and_owner_writes_audit_and_allows_rescan` (`test_checkin.py`); `test_timeline_shows_the_events_story` (`test_history.py`); `test_scan_manual_check_in_and_undo_all_reach_the_timeline` (`test_scanner_srs.py`) | The new test covers all three paths (QR scan, manual search, undo) and checks the actor, timestamp and description. A rejected scan (campaign, already used) writes nothing. |
| 14 | Network errors: with no connection or on a timeout, the app shows "no connection, not checked in", never anything that looks like success. No offline queue. | §4.8, §10 | Fixed | `api.test.ts` "aborts a request that takes too long…"; `live-checkin.test.tsx` "says the ticket was NOT checked in when offline…", "…on a timeout", "…on a server error" | **Was failing:** (a) requests had no timeout, so a hung connection left "Checking the ticket…" on screen indefinitely; (b) the offline message ("Can't reach BiletFlow…") didn't say the ticket was **not** checked in. Requests now time out after 8 s. Any failure shows a red "Not checked in" panel with ✕, the reason and "Try again". No offline queue (bonus, out of scope per §4.8 and §8). |
| 15 | Translations: every scanner string is in the i18n module, in kk, ru and en. | §7 | Pass (test added) | `i18n.test.ts` "has no hard-coded text in screens or components", "has the same keys in kk, ru and en"; `scripts/check-locales.mjs` (in `npm run lint`) | One limitation: the native iOS camera-permission prompt text comes from `app.json` (`expo-camera` plugin) and is English only. It's native build config, not app UI. It's listed on the manual list. |

**Totals:** 15 requirements. 10 already passed (#1, #2, #4, #5, #6, #7, #9, #11, #13, #15).
6 of those were missing a test, which this branch adds. 5 were failing or partly failing and
are fixed (#3, #8, #10, #12, #14). None are still failing. Real-device behavior is in the
manual checklist below.

## Known limitations (not failures)

- **A timeout after the server already recorded the check-in.** If the response is lost on
  the way back, the phone says "Not checked in", and "Try again" then says "Already used"
  with a check-in time from a few seconds ago. That is correct, because the ticket *was*
  admitted, but staff should know about it. The time on screen tells them. A proper fix
  needs a client request ID with idempotent replay, which means a model change.
- **The owner sees their own events in the scanner.** This is by design (§2.3: organizers
  manage their events). Platform Admins do not get door access from their role alone.

## Manual device test

These need a human with real devices. Use the demo data (`staff@demo.biletflow.kz` /
`Demo-pass-2026`) and the "Almaty Jazz Night" event. Set `EXPO_PUBLIC_API_BASE_URL` to an
address the phone can reach.

| # | Check | Steps | Expected | Android | iPhone |
|---|---|---|---|---|---|
| M1 | Real phones | Install with Expo Go or a dev build. Sign in, sign out, sign in again. Kill and reopen the app. | Stays signed in after a relaunch. After sign-out, a relaunch shows the login screen. | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail |
| M2 | Printed grayscale A4 ticket | Download a ticket PDF, print it on A4 in **grayscale**, and scan the paper. | "Valid" the first time. | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail |
| M3 | Paper after digital | Scan the email QR on a laptop screen, then the printed copy of the same ticket. | The second scan says "Already used" and shows the first scan's time. | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail |
| M4 | Ticket on another phone's screen | Open the ticket in the attendee web app on a second phone at medium brightness, then scan it. | "Valid" (or "Already used" if scanned before). | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail |
| M5 | Campaign QR | Print or show the JAZZ15 Campaign QR (organizer → campaign → QR PDF) and scan it, then scan a valid ticket right away. | Red "Invalid" with "This is a promo QR code, not a ticket.", then the ticket is "Valid". | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail |
| M6 | Mobile data, not Wi-Fi | Turn Wi-Fi off, use 4G/LTE (the API must be reachable from the internet) and scan a ticket. | Result as usual, no errors. | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail |
| M7 | Scan-to-result time | Time 5 scans from the moment the QR is in the frame to the result screen (stopwatch or screen recording). Write down the slowest. | Each one is under 2 s. Slowest: ____ s | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail |
| M8 | Camera permission denied, then granted | Fresh install, tap "Allow camera" and **deny**. Deny again if asked. Tap "Open settings", allow the camera, come back. | A clear "camera is off" screen with "Open settings" and "Try again". Back in the app, the camera starts without a restart. | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail |
| M9 | No connection | Turn on airplane mode and scan a ticket. | A red "Not checked in" panel that says there is no connection. Nothing green. "Try again" works once the connection is back. | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail |
| M10 | Undo | Signed in as the event admin, scan a ticket, tap "Undo check-in" and confirm. Scan it again. | The counts go down, then up again; the second scan is "Valid". | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail |
| M11 | Languages | Set the phone language to Kazakh, then Russian, and go through login → events → scan → result. | No English text, nothing cut off. (The iOS permission prompt is in English; see #15.) | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail |
| M12 | Ticket still in view | Scan a ticket and keep it in front of the camera while the result is showing. | Only one result screen opens. | ☐ Pass ☐ Fail | ☐ Pass ☐ Fail |

| | Android | iPhone |
|---|---|---|
| Device model and OS version | ____________________ | ____________________ |
| Tester name | ____________________ | ____________________ |
| Date | ____________________ | ____________________ |
| Build / commit | ____________________ | ____________________ |
