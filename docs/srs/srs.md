<!-- Text extracted from BiletFlow_SRS_v0.3.pdf (Initial Draft) so it can be searched and
     diffed. The PDF is the authoritative copy. Page numbers have been removed. -->

Software Requirements Specification
BiletFlow: Self-Service Event Ticketing Platform for Kazakhstan
Version: 0.3
Status: Initial Draft
Project Type: Web and mobile event and ticket management platform

## Executive Summary

BiletFlow is a Kazakhstan-focused self-service platform that allows individuals, student organi-
zations, businesses, and community groups to create events and issue digital tickets.
Creating an event and distributing free tickets is free. Organizers who want to sell paid tickets
must activate paid sales for the event by paying a one-time activation fee and completing
identity and payout verification.
The platform provides event pages, ticket inventory management, online registration, se-
cure payments, QR-code tickets, calendar export, attendee management, and a mobile ticket-
verification app for event administrators.

## 1. Introduction

### 1.1 Purpose

This document defines the initial requirements for BiletFlow. It describes the platform’s users,
business model, main features, constraints, and MVP scope.

### 1.2 Scope

The platform will allow organizers to:
- Create and publish public or private physical events held at a venue.
- Create multiple ticket types.
- Configure assigned-seating events and interactive seat maps.
- Issue free tickets without paying a platform fee.
- Activate paid ticket sales for individual events.
- Set prices, quantities, and sale periods.
- Track registrations and revenue.
- Send digital tickets containing unique QR codes.
- Allow attendees to download and print their tickets.
- Assign event administrators who verify tickets and check attendees in through a mobile
app.
- Allow attendees to export event details to their preferred calendars.
- Cancel orders and process refunds where permitted.
Attendees will be able to discover events, register or purchase tickets, receive digital tickets,
add event details to their calendars, and present their tickets for check-in.

### 1.3 Definitions

- Organizer: A user who creates and manages an event.
- Attendee: A person who registers for or purchases a ticket.
- Event Admin: An organizer-authorized user who uses the mobile app to verify tickets
and check in attendees. This role is separate from the Platform Admin.
- Free Ticket: A ticket with no payment requirement.
- Paid Ticket: A ticket that requires payment during checkout.
- Paid Sales Activation: The process that enables an organizer to collect money for an
event.
- Support Case: A support request linked to a user, event, order, or ticket and represented
through an asynchronous chat-like conversation.
- Promo Code: An organizer-created code that applies a configured ticket discount and
attributes the resulting order to a campaign.
- Campaign QR Code: A promotional QR code that opens an event page through a trackable
link and automatically applies its associated promo code. It is not an admission ticket.
- Platform Admin: Internal staff responsible for moderation, disputes, and platform man-
agement.
- Payment Processor: An external service that processes payments and organizer payouts.

## 2. Overall Description

### 2.1 Product Perspective

BiletFlow will consist of:
- A responsive web application for organizers and attendees.
- A dedicated iOS and Android application for event administrators to verify tickets and
manage check-in.
- An administrative web portal.
- Backend services for events, orders, payments, tickets, support cases, promotional cam-
paigns, notifications, and reporting.
- Integrations with a payment processor, email provider, and calendar-export services.

### 2.2 Stakeholders

- Event organizers
- Attendees
- Event administrators and check-in staff
- Platform administrators
- Payment and payout providers
- Development and QA teams
- Project sponsors and business stakeholders

### 2.3 User Classes

Attendee
Can browse events, register, purchase tickets, download tickets, and review existing orders.
Organizer
Can create events, configure ticket types, activate paid sales, manage attendees, view sales, and
assign check-in staff.
Event Admin
Can use the mobile app to select assigned events, scan and verify QR-code tickets, search for
attendees, and record or reverse check-ins.
Platform Admin
Can moderate events, manage users, review payment activation requests, handle disputes, and
view platform reports.

## 3. Business and Monetization Model

### 3.1 Free Events

Organizers may:
- Create and publish events without charge.
- Create free ticket types.
- Issue QR-code tickets.
- Use attendee lists and check-in functionality.
- Send basic confirmation messages.

### 3.2 Paid Events

Paid ticket sales remain disabled until the organizer:

1. Creates an event and at least one paid ticket type.
2. Completes identity and payout verification.
3. Pays the event’s Paid Sales Activation Fee.
4. Connects or registers a valid payout account.
5. Accepts the paid-event terms.

Once activated, the organizer can collect ticket payments for that event.
For the academic MVP, identity checks, activation-fee payment, ticket payment, and organizer
payouts may be implemented with a provider sandbox or clearly labelled simulation. No real
money movement is required for the term demonstration.

### 3.3 Recommended Initial Pricing Model

- Free events: no platform fee.
- Paid Sales Activation Fee: one-time fee per event, charged in KZT; amount to be deter-
mined.
- Payment-processing charges: deducted from each transaction.
- Optional per-ticket service fee: excluded from the initial MVP and considered for a later
release.
This model gives organizers the complete basic workflow at no cost and charges them only
when they intend to generate revenue.

## 4. System Features and Requirements

### 4.1 Account Management

- Users shall be able to register using an email address.
- Users shall be able to verify their email addresses.
- Users shall be able to sign in, sign out, and reset passwords.
- Organizers shall have a profile containing contact and payout information.
- The system shall support role-based permissions.

### 4.2 Event Management

Organizers shall be able to:
- Create, edit, duplicate, publish, unpublish, and cancel events.
- Add an event title, description, category, images, venue, date, and time.
- Create physical, venue-based events.
- Mark events as public, unlisted, or private.
- Define registration opening and closing times.
- Set an event capacity.
- Preview an event before publication.

### 4.3 Ticket Management

Organizers shall be able to:
- Create free and paid ticket types.
- Set ticket name, description, price, and quantity.
- Configure ticket sales start and end times.
- Limit the number of tickets purchased in one order.
- Hide ticket types without deleting them.
- View the number of available, reserved, sold, refunded, and checked-in tickets.
The system shall prevent ticket sales when inventory has been exhausted.

#### 4.3.1 Assigned Seating and Seat Selection

- Organizers shall be able to mark an event as general admission or assigned seating.
- The academic MVP shall provide at least one predefined venue layout containing sections,
rows, seat numbers, accessible seats, and price categories.
- Organizers shall be able to select and configure the predefined layout; a visual venue-
layout editor is not required.
- For assigned-seating events, attendees shall see an interactive seat map during registra-
tion or checkout.
- The seat map shall clearly distinguish available, selected, temporarily held, sold, unavail-
able, and accessible seats with both colors and text or symbols.
- Attendees shall be able to select one or more available seats and see the ticket price before
continuing to checkout.
- Selected seats shall be held temporarily while checkout is in progress.
- A seat hold shall expire and release the seat when checkout is abandoned or its time limit
is reached.
- The system shall prevent two orders from purchasing the same seat, including when
multiple attendees check out concurrently.
- The assigned section, row, and seat number shall be stored on the ticket and order item.

### 4.4 Free Registration

- An attendee shall be able to reserve a free ticket without entering payment information.
- The system shall create an order with a zero-value total.
- The attendee shall receive a confirmation email and QR-code ticket.
- The organizer shall see the registration in the attendee list.

### 4.5 Paid Sales Activation

- Paid tickets shall not be purchasable before activation.
- The organizer shall see an activation checklist.
- The system shall record payment of the activation fee.
- The system shall verify that the simulated or sandbox payout requirements are complete.
- Activation shall apply only to the selected event.
- Platform administrators shall be able to suspend paid sales when fraud or policy violations
are suspected.

### 4.6 Checkout and Payments

- Attendees shall be able to select tickets and provide attendee details.
- Ticket inventory shall be temporarily reserved during checkout.
- The system shall calculate ticket totals and processing charges.
- Payments shall be processed through an external provider sandbox or a clearly labelled
internal simulation for the academic MVP.
- Tickets shall only be issued after successful payment confirmation.
- Failed or abandoned transactions shall not create valid tickets.
- Organizers shall be able to view gross sales, fees, refunds, and estimated payouts.
- Demonstration payment records shall never be presented as real financial transactions.

### 4.7 Digital Tickets

Each issued ticket shall include:
- A unique ticket identifier.
- Event and ticket-type information.
- Attendee information.
- A tamper-resistant QR code.
- Current status: valid, checked in, cancelled, or refunded.
Tickets shall be available through email and the attendee’s account.
- Attendees shall be able to download each ticket as a print-optimized PDF and print it
from a standard browser or PDF viewer.
- A printed ticket shall include the event name, date and time, venue, ticket type, attendee
name, assigned section/row/seat when applicable, ticket identifier, and QR code.
- Payment-card details and other unnecessary sensitive information shall not appear on
the printed ticket.
- The QR code shall remain large and clear enough to be scanned from a paper copy,
including when printed in grayscale.
- Digital and printed copies of the same ticket shall share one ticket identifier and shall not
create separate admissions.

### 4.8 Mobile Ticket Verification and Event Check-In

The system shall provide a dedicated mobile app for authorized event administrators. The app
shall allow them to:
- Sign in securely and view only assigned events.
- Scan ticket QR codes using the device camera.
- Validate ticket authenticity and status in real time.
- Display a clear valid, invalid, cancelled, refunded, or already-used result.
- Record a successful check-in and prevent the same ticket from being used twice.
- Search for attendees manually.
- Undo an accidental check-in where authorized.
- View the total number of registered and checked-in attendees.
- Synchronize check-in records with the central platform.
The academic MVP requires online verification only. Offline synchronization is deferred.

### 4.9 Orders, Cancellations, and Refunds

- Attendees shall be able to view their orders.
- Organizers shall be able to define a refund policy.
- Organizers shall be able to cancel free registrations.
- Authorized organizers shall be able to initiate full refunds.
- Refunded or cancelled tickets shall become invalid.
- All payment and refund actions shall be recorded in an audit log.

### 4.10 Notifications

The system shall send notifications for:
- Account verification
- Registration or purchase confirmation
- Payment failure
- Ticket delivery
- Event updates
- Event cancellation
- Refund completion
- Organizer payout status
- New support message, support-case assignment, and support-case status changes

### 4.11 Calendar Export

- Attendees shall be able to download event details as a standard iCalendar ( .ics) file.
- The event page and order confirmation shall provide one-click options for common
calendar services.
- Calendar entries shall include the event title, start and end times, time zone, venue name
and address, description, and event URL.
- Calendar exports shall use a stable event identifier so updated event details can replace
an earlier calendar entry.
- When an event is cancelled, the system shall provide an updated cancellation calendar
file or link.
- Calendar export shall not require the platform to request write access to an attendee’s
calendar account.

### 4.12 Administration

Platform administrators shall be able to:
- Search for users, events, orders, and payments.
- Suspend users or events.
- Review reported events.
- Inspect paid-sales activation records.
- Monitor refunds, disputes, and payment failures.
- Configure activation fees and platform settings.
- Review escalated support cases and promotional-code activity.
- Export basic operational reports.

### 4.13 Support Chat and Case Management

- An attendee shall be able to open a support request from an event, order, or ticket page.
- An organizer shall be able to open a platform-support request concerning account, acti-
vation, payment, or technical issues.
- A support case shall automatically include the relevant user, event, order, and ticket
context when available.
- The requester shall select an issue category such as ticket delivery, payment, refund,
seating, event information, check-in, account, or technical problem.
- Each support case shall provide an asynchronous chat-like message thread.
- Attendees and organizer support staff shall be able to exchange messages within attendee
support cases.
- Organizers and Platform Admins shall be able to exchange messages within organizer
support cases.
- Authorized staff shall be able to assign a case and change its status among Open, In
Progress, Waiting for Customer , and Resolved.
- Users shall receive in-app or email notifications when a new reply or relevant status
change occurs.
- The system shall retain the case history and prevent users from viewing cases they are
not authorized to access.
- The academic MVP does not require typing indicators, presence information, voice
messages, AI chatbots, or real-time WebSocket delivery.

### 4.14 Promo Codes and Campaign QR Codes

- Organizers shall be able to create a promotional campaign for an event.
- A campaign may have a percentage or fixed-KZT discount, validity dates, maximum
redemptions, and applicable ticket types.
- The system shall generate a unique promo code and a special Campaign QR Code for the
campaign.
- The Campaign QR Code shall encode a trackable HTTPS event link containing an opaque
campaign or promo token rather than a discount amount trusted by the client.
- Scanning the Campaign QR Code shall open the correct event page and automatically
apply the associated promo code after server-side validation.
- The attendee shall see the applied code, discount, and updated order total before com-
pleting checkout.
- Expired, disabled, exhausted, or inapplicable codes shall be rejected with a clear message.
- The server shall calculate and validate all discounts and shall prevent redemption beyond
the campaign limit.
- The Campaign QR Code shall be visually and functionally distinct from an admission-
ticket QR code.
- The mobile ticket-verification app and admission endpoint shall never accept a Campaign
QR Code as permission to enter an event.
- BiletFlow shall record exact redemptions, orders, tickets sold, gross revenue, discount
amount, and net revenue for each campaign.
- GA4 may record campaign-link visits, checkout starts, and traffic attribution without
receiving attendee names, email addresses, phone numbers, ticket identifiers, or other
direct personal information.

### 4.15 Basic Organizer Analytics

- Each organizer shall have access only to analytics for events they manage.
- The dashboard shall show total ticket capacity, tickets sold, tickets remaining, and per-
centage sold.
- The dashboard shall show gross sales, discounts, refunds, and net demonstration revenue
in KZT.
- Organizers shall be able to view sales over time using order timestamps.
- Organizers shall be able to compare sales by ticket type.
- The dashboard shall show campaign and promo-code redemptions, tickets attributed to
each campaign, and resulting revenue.
- The dashboard shall show checked-in attendees, absent ticket holders, and the check-in
percentage after or during the event.
- Basic filters shall include event, date range, and ticket type.
- Required analytics shall be calculated from authoritative BiletFlow order, ticket, cam-
paign, refund, and check-in records.
- Basic analytics shall not require attendees to provide demographic information or com-
plete additional checkout fields.
- GA4 traffic, funnel, geographic, device, or demographic reporting is an optional advanced
analytics feature and is not required for the base MVP.

### 4.16 Organizer Event History and Audit Trail

- The organizer dashboard shall classify events as Upcoming, Active, Completed, or
Cancelled.
- Organizers shall be able to open completed and cancelled events and review their retained
tickets, orders, refunds, check-ins, promo campaigns, support cases, and basic analytics.
- Organizers shall be able to duplicate a past event into a new draft while excluding the
original event’s orders, tickets, payments, check-ins, and support cases.
- Each event shall provide a chronological activity timeline.
- The timeline shall include important actions such as event publication or cancellation,
ticket price or capacity changes, refunds, promo-code creation or disabling, support-case
status changes, check-ins, and check-in reversals.
- Each history entry shall contain a timestamp, acting user, action type, affected entity,
and short description.
- Organizers shall be able to filter history by date range and activity type.
- Organizer staff shall only see history for events they are authorized to manage; Platform
Admins may view history for moderation or support purposes.
- Audit entries shall not be editable or deletable through normal organizer interfaces.
- Full field-by-field version history, rollback, and permanent compliance archival are not
required for the academic MVP.

## 5. Example Use Cases

#### UC1: Organizer Creates a Free Event

Actor: Organizer
Precondition: Organizer has a verified account.
Flow: The organizer enters event details, creates a free ticket type, previews the event, and
publishes it.
Postcondition: Attendees can register without payment.

#### UC2: Organizer Activates Paid Ticket Sales

Actor: Organizer
Precondition: A draft event contains a paid ticket type.
Flow: The organizer completes verification, connects a payout account, pays the activation fee,
and accepts the terms.
Postcondition: Paid checkout becomes available for the event.

#### UC3: Attendee Purchases a Ticket

Actor: Attendee
Precondition: Paid sales are active and tickets are available.
Flow: The attendee selects tickets, enters required information, and completes payment.
Postcondition: An order and QR-code ticket are issued.

#### UC4: Event Admin Verifies and Checks In an Attendee

Actor: Event Admin
Precondition: The Event Admin is signed into the mobile app and assigned to the event.
Flow: The Event Admin selects the event and scans the attendee’s QR code. The mobile app
validates the ticket and records the check-in.
Postcondition: The ticket cannot be checked in again unless the previous action is reversed.

#### UC5: Organizer Refunds an Order

Actor: Organizer
Precondition: The order is eligible for a refund.
Flow: The organizer selects the order, confirms the refund, and the payment provider processes
it.
Postcondition: The ticket is invalidated and the attendee is notified.

#### UC6: Attendee Adds an Event to a Calendar

Actor: Attendee
Precondition: The attendee is viewing an event page, confirmation page, or issued ticket.
Flow: The attendee selects a calendar option or downloads the .ics file.
Postcondition: A calendar entry is prepared with the correct event time zone, venue name and
address, and event URL.

#### UC7: Attendee Prints a Ticket

Actor: Attendee
Precondition: A valid ticket has been issued.
Flow: The attendee opens the order or ticket, downloads the print-optimized PDF, and prints
it.
Postcondition: The paper ticket contains a readable QR code that the Event Admin mobile app
can verify at the entrance.

#### UC8: Attendee Selects an Assigned Seat

Actor: Attendee
Precondition: The event uses assigned seating and sales are open.
Flow: The attendee opens the interactive seat map, reviews seat availability and prices, selects
an available seat, and completes checkout before the temporary hold expires.
Postcondition: The purchased seat is linked to the order and ticket and is no longer available
to other attendees.

#### UC9: Attendee Requests Support

Actor: Attendee
Precondition: The attendee is viewing an event, order, or ticket.
Flow: The attendee selects support, chooses an issue category, writes a message, and submits
the case. The organizer replies through the support conversation.
Postcondition: The conversation and its event/order/ticket context are retained until the case
is resolved.

#### UC10: Attendee Purchases Through a Campaign QR Code

Actor: Attendee
Precondition: The organizer has an active promotional campaign with remaining redemptions.
Flow: The attendee scans the Campaign QR Code, opens the event page with the promo code
pre-applied, selects tickets, reviews the discount, and completes checkout.
Postcondition: The discount is recorded on the order and the sale is attributed to the correct
campaign.

#### UC11: Organizer Reviews Basic Analytics

Actor: Organizer
Precondition: The organizer manages an event with ticket, order, campaign, or check-in
activity.
Flow: The organizer opens the event dashboard, selects a date range or ticket type, and reviews
sales progress, revenue, campaign performance, and attendance.
Postcondition: The organizer sees metrics calculated from BiletFlow records without collecting
additional attendee information.

#### UC12: Organizer Reviews and Reuses Event History

Actor: Organizer
Precondition: The organizer manages at least one completed or cancelled event.
Flow: The organizer opens the past-events view, reviews the event activity timeline and retained
operational records, then duplicates the event into a new draft.
Postcondition: Historical records remain unchanged and the new draft contains reusable event
configuration without copying old transactions or attendees.

## 6. Core Data Entities

- User
- Organizer Profile
- Event
- Venue
- Venue Section
- Row
- Seat
- Seat Hold
- Ticket Type
- Order
- Order Item
- Ticket
- Attendee
- Payment
- Refund
- Payout Account
- Check-In Record
- Staff Assignment
- Notification
- Support Case
- Support Message
- Promotional Campaign
- Promo Code
- Promo Redemption
- Audit Log

## 7. Non-Functional Requirements

- The platform should support modern desktop and mobile browsers.
- The ticket-verification app shall support current iOS and Android versions selected for
the MVP.
- The customer-facing interface shall initially support Kazakh and Russian, with English
available as an additional locale.
- Prices, fees, refunds, and payouts shall use KZT for the initial Kazakhstan release.
- Sensitive information shall be encrypted in transit and at rest.
- Passwords shall be stored using secure password hashing.
- Payment-card data shall not be stored directly by the platform.
- Organizer and administrator actions shall be auditable.
- Event pages should meet WCAG 2.1 AA accessibility guidelines.
- The checkout process should remain usable under temporary increases in event traffic.
- Seat availability shall update promptly, and checkout shall use an atomic reservation
process to prevent double-selling a seat.
- The interactive seat map shall be usable on desktop and mobile screens and provide
accessible labels in addition to color indicators.
- QR validation should normally complete within two seconds with an internet connection.
- Printable tickets shall produce legible text and reliably scannable QR codes on standard
A4 paper in color or grayscale.
- Calendar exports shall preserve the event’s configured time zone.
- Support-case access shall be enforced by role and by relationship to the relevant event,
order, or ticket.
- Promo-code validation and redemption limits shall be enforced atomically on the server.
- Campaign QR links shall not contain trusted price or discount values and shall never be
accepted by ticket-verification endpoints.
- Analytics queries and chart generation shall not block or delay ticket selection, checkout,
payment confirmation, or ticket issuance.
- Organizer history and audit data shall be protected by the same event-level authorization
rules as the underlying operational records.
- The architecture should support additional currencies and languages in future releases.
- Regular backups and recovery procedures shall be established.

## 8. MVP Scope

Required MVP Features
- User registration and authentication
- Organizer profiles
- Event creation and publication
- Free and paid ticket types
- Simulated or sandboxed paid-sales activation
- Simulated or sandboxed KZT checkout
- QR-code ticket generation
- Downloadable and printable PDF tickets
- Email confirmations
- Attendee and order management
- Dedicated iOS and Android ticket-verification app for Event Admins
- Basic cancellations and refunds
- Administrative moderation
- Basic organizer analytics for capacity, sales over time, revenue, ticket types, campaigns,
and attendance
- Organizer event history with past/completed/cancelled views, event duplication, and an
activity timeline
- Asynchronous support chat with case status and contextual event/order/ticket links
- Promo codes with special Campaign QR Codes and basic campaign sales reporting
- Docker-based local or demonstration deployment
Bonus and Stretch Features
- One predefined assigned-seating layout with an interactive seat-selection UI
- Calendar export through .ics files and common calendar links
- Advanced organizer analytics using GA4 traffic/funnel data combined with authoritative
BiletFlow order data
- Offline ticket-verification synchronization
- Support-message file attachments or enhanced real-time delivery
Excluded from the Initial MVP
- Real-money organizer payouts and production financial processing
- Production KYC/KYB or identity-verification workflows
- Visual venue-layout designer and arbitrary venue imports
- Production-grade offline scanner synchronization
- Advanced refund and dispute workflows
- App Store and Google Play publication
- Ticket resale or transfer marketplace
- Native attendee and organizer mobile applications
- Affiliate marketing
- Recurring events
- Advanced marketing automation
- On-site hardware integrations
- Multiple organizer payout splits
- Detailed accounting and tax automation
- Full field-by-field version history, rollback, and production compliance archival

## 9. Suggested Technology Stack

The frontend and mobile technologies are recommended for consistency, while the team may
choose the backend language that best matches its experience. The academic MVP shall use
one primary backend implementation; creating the same services in multiple languages or
introducing unnecessary microservices is outside the term scope.
- Database: PostgreSQL or MongoDB with Mongoose. PostgreSQL may be paired with
Node.js, Python, Go, or Java; selecting Node.js does not require MongoDB.
- Backend Option 1 - JavaScript/TypeScript: Node.js with Express or a comparable frame-
work; this produces a MERN-style stack when combined with MongoDB and React
- Backend Option 2 - Python: FastAPI or Django
- Backend Option 3 - Go: Go with a lightweight HTTP framework or the standard HTTP
library
- Backend Option 4 - Java: Spring Boot
- Web Application: React; Next.js may be used when server-side rendering or search
visibility is needed
- Seat Map UI: React with SVG or Canvas rendering, one predefined layout, and server-
validated seat holds
- Mobile Ticket-Verification App: React Native, optionally with Expo
- Frontend Language: TypeScript is recommended across the web application and React
Native app; it may also be shared with the backend when Node.js is selected
- Styling: Tailwind CSS
- Payments: Provider sandbox or internal simulation using KZT; production provider
integration is deferred
- Email: Transactional email provider
- File Storage: S3-compatible object storage
- Printable Tickets: Server-generated PDF based on the canonical ticket record
- Support Chat: REST API with periodic refresh or lightweight polling; real-time sockets
are optional and not required
- Campaign QR Codes: Server-generated QR images containing signed or opaque promo-
tional links
- Analytics: Database aggregation for exact sales/redemption data and optional GA4
ecommerce/campaign events for traffic attribution
- Deployment: Docker containers
- Design: Figma
- Testing: Automated API, interface, payment, and QR-validation tests
The backend language and database shall be selected during the initial architecture phase and
documented with a short rationale covering team familiarity, development speed, data-model
requirements, and deployment complexity.

## 10. Assumptions and Dependencies

- The team can access a suitable payment sandbox or implement a clearly labelled payment
simulation.
- The initial release will operate in Kazakhstan and use KZT as its settlement currency.
- Payment, privacy, refund, and organizer-verification rules will be reviewed for compliance
with applicable Kazakhstan requirements before launch.
- Organizers are responsible for event legality, descriptions, and refund policies.
- Attendees have access to email or an online account for ticket delivery.
- Event Admins have supported iOS or Android devices with working cameras.
- Event venues provide internet access for real-time check-in; offline check-in is outside
the academic MVP.
- AI-assisted tools may be used during development; this document does not prescribe a
particular tool or AI-assisted workflow.
- Final production fees, supported payment methods, payment provider, and payout timing
remain future decisions.

## 11. Initial Success Criteria

The MVP will be considered successful when:
- An organizer can publish a free event and distribute valid tickets.
- An organizer can complete the simulated or sandboxed paid-sales activation and receive
demonstration orders.
- An attendee can complete checkout and receive a QR-code ticket.
- An attendee can download and print a ticket that remains scannable at check-in.
- An Event Admin can use the mobile app to validate tickets and prevent duplicate entry.
- An attendee can open a contextual support case and exchange asynchronous messages
with authorized organizer staff.
- An attendee can scan a Campaign QR Code, receive a valid discount, and complete an
order attributed to the campaign.
- An admission scanner rejects Campaign QR Codes while continuing to accept valid ticket
QR codes.
- Organizers can view accurate ticket, attendance, payment, and refund records.
- Organizers can view basic sales, capacity, campaign, and attendance analytics without
adding fields to the attendee checkout.
- Organizers can review past and cancelled events, inspect an authorized activity timeline,
and duplicate a past event without copying historical transactions.
- Administrators can suspend a suspicious event and stop further sales.
Bonus features are evaluated separately and are not required to satisfy the base MVP success
criteria.

## 12. Key Decisions for the Next Draft

- Final project and product name
- Final backend selection among Node.js, Python, Go, and Java, together with MongoDB
or PostgreSQL
- Activation fee amount and refundability
- Payment sandbox or simulation method for the academic MVP
- Whether attendees must create accounts
- Whether processing fees are paid by organizers or attendees
- Payout delay and reserve policy
- Organizer verification requirements
- Event cancellation and refund rules
- Predefined seating layout used for the demonstration
- Whether support cases allow file attachments in the academic MVP
- Initial promo-code discount types, redemption limits, and campaign reporting fields
- Default date ranges and chart formats for the basic organizer dashboard
- Academic retention period for event history and audit entries

## 13. Term Feasibility and Delivery Plan

### 13.1 Feasibility Target

The project is planned as a polished academic prototype developed by a team of five over 10–12
weeks. The team may use AI-assisted development tools. The term deliverable is not intended
to be a production financial platform.
The MVP is feasible only if the team maintains the scope boundaries in Section 8. Real payments,
real payouts, production identity verification, arbitrary venue-map creation, offline scanner
synchronization, and application-store publication are not term requirements.

### 13.2 Suggested Team Ownership

Each area shall have one primary owner, with peer review from at least one other team mem-
ber:

## 1. Architecture, integration, authentication, and deployment

## 2. Backend event, ticket, order, and seat-reservation services

## 3. Organizer and attendee web interfaces

## 4. Admin interface, promotional campaigns, basic reporting, organizer history, calendar

bonus, and printable tickets

## 5. React Native verification app, support workflow, assigned-seating bonus, automated

testing, and release coordination
Ownership does not prevent collaboration. Shared API contracts and data models should be
agreed before parallel implementation begins.

### 13.3 Suggested 12-Week Schedule

- Weeks 1–2: select one backend stack, confirm scope, prepare wireframes, define API
contracts and data model, and configure repositories and automated checks
- Weeks 3–4: implement authentication, roles, organizer profiles, and event creation
- Weeks 5–6: implement ticket types, inventory, sandbox checkout, orders, and QR gener-
ation
- Week 7: implement printable PDF tickets, promo codes, and Campaign QR Codes; add
calendar export only if the core flow is on schedule
- Week 8: implement the React Native online verification app and asynchronous support
workflow
- Week 9: implement basic administration, organizer history, and the required analytics
dashboard; add assigned seating or advanced GA4 analytics only if the core flow is stable
- Week 10: integrate features, resolve cross-application defects, and complete core-flow
tests
- Weeks 11–12: stabilize, improve usability, prepare documentation, rehearse the demon-
stration, and retain contingency time
For a 10-week term, Weeks 7–9 should overlap where team capacity permits, while Week 10
remains reserved for integration and stabilization.

### 13.4 Scope and Quality Controls

- Core end-to-end flow takes priority: create event, distribute a campaign QR, apply a
promo code, select or reserve a ticket, complete simulated checkout, issue the ticket,
request support, and verify entry.
- Feature development should stop after Week 9 unless a missing feature blocks the core
demonstration.
- Each feature is complete only when integrated, reviewed, tested, and documented.
- Bonus features shall not be started at the expense of an incomplete required flow.
- If the project falls behind, remove assigned seating, calendar export, advanced analytics,
localization polish, and refund simulation before cutting the core ticketing flow.
