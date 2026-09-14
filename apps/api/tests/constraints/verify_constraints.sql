\set ON_ERROR_STOP on
BEGIN;

-- A minimal valid graph: one organizer, one venue with one seat, one event, one order.
INSERT INTO users (id, email, hashed_password, full_name, role, locale, is_email_verified, is_suspended)
VALUES ('11111111-1111-1111-1111-111111111111', 'org@biletflow.kz', 'x', 'Organizer', 'organizer', 'kk', true, false),
       ('22222222-2222-2222-2222-222222222222', 'buyer@biletflow.kz', 'x', 'Buyer', 'attendee', 'kk', true, false);

INSERT INTO organizer_profiles (id, user_id, display_name, contact_email, is_suspended)
VALUES ('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 'Almaty Events', 'org@biletflow.kz', false);

INSERT INTO venues (id, name, address_line1, city, country_code, has_seat_map)
VALUES ('44444444-4444-4444-4444-444444444444', 'Palace of Republic', 'Dostyk 56', 'Almaty', 'KZ', true);
INSERT INTO venue_sections (id, venue_id, name, display_order)
VALUES ('55555555-5555-5555-5555-555555555555', '44444444-4444-4444-4444-444444444444', 'Parterre', 0);
INSERT INTO seat_rows (id, section_id, label, display_order)
VALUES ('66666666-6666-6666-6666-666666666666', '55555555-5555-5555-5555-555555555555', 'A', 0);
INSERT INTO seats (id, row_id, number, is_accessible, status)
VALUES ('77777777-7777-7777-7777-777777777777', '66666666-6666-6666-6666-666666666666', '1', false, 'available');

INSERT INTO events (id, organizer_profile_id, venue_id, title, slug, status, visibility, seating_mode, starts_at, ends_at, timezone, is_suspended)
VALUES ('88888888-8888-8888-8888-888888888888', '33333333-3333-3333-3333-333333333333', '44444444-4444-4444-4444-444444444444',
        'Test Concert', 'test-concert', 'published', 'public', 'assigned_seating',
        now() + interval '30 days', now() + interval '30 days 3 hours', 'Asia/Almaty', false);

INSERT INTO ticket_types (id, event_id, name, price_kzt, quantity_total, quantity_sold, quantity_reserved, max_per_order, is_hidden)
VALUES ('99999999-9999-9999-9999-999999999999', '88888888-8888-8888-8888-888888888888', 'Standard', 5000, 100, 0, 0, 10, false);

INSERT INTO orders (id, reference, user_id, event_id, status, subtotal_kzt, discount_kzt, processing_fee_kzt, total_kzt, refunded_kzt, currency)
VALUES ('aaaaaaaa-0000-0000-0000-000000000001', 'BF-TEST01', '22222222-2222-2222-2222-222222222222', '88888888-8888-8888-8888-888888888888', 'confirmed', 5000, 0, 0, 5000, 0, 'KZT'),
       ('aaaaaaaa-0000-0000-0000-000000000002', 'BF-TEST02', '22222222-2222-2222-2222-222222222222', '88888888-8888-8888-8888-888888888888', 'confirmed', 5000, 0, 0, 5000, 0, 'KZT');

INSERT INTO order_items (id, order_id, ticket_type_id, quantity, unit_price_kzt, discount_kzt, line_total_kzt, seat_id)
VALUES ('bbbbbbbb-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001', '99999999-9999-9999-9999-999999999999', 1, 5000, 0, 5000, '77777777-7777-7777-7777-777777777777'),
       ('bbbbbbbb-0000-0000-0000-000000000002', 'aaaaaaaa-0000-0000-0000-000000000002', '99999999-9999-9999-9999-999999999999', 1, 5000, 0, 5000, '77777777-7777-7777-7777-777777777777');

INSERT INTO attendees (id, order_id, full_name)
VALUES ('cccccccc-0000-0000-0000-000000000001', 'aaaaaaaa-0000-0000-0000-000000000001', 'Aigerim N'),
       ('cccccccc-0000-0000-0000-000000000002', 'aaaaaaaa-0000-0000-0000-000000000002', 'Daniyar K');

-- Ticket 1 takes seat A1. This must succeed.
INSERT INTO tickets (id, ticket_number, order_id, order_item_id, event_id, ticket_type_id, attendee_id, status, admission_token, seat_id, price_kzt)
VALUES ('dddddddd-0000-0000-0000-000000000001', 'BF-T-0001', 'aaaaaaaa-0000-0000-0000-000000000001', 'bbbbbbbb-0000-0000-0000-000000000001',
        '88888888-8888-8888-8888-888888888888', '99999999-9999-9999-9999-999999999999', 'cccccccc-0000-0000-0000-000000000001',
        'valid', 'BFT1.AAAAAAAAAAAAAAAAAAAAAAAAAA', '77777777-7777-7777-7777-777777777777', 5000);

INSERT INTO promotional_campaigns (id, event_id, name, status, discount_type, discount_percent, qr_token, created_by_user_id)
VALUES ('eeeeeeee-0000-0000-0000-000000000001', '88888888-8888-8888-8888-888888888888', 'Spring', 'active', 'percentage', 10,
        'BFC1.BBBBBBBBBBBBBBBBBBBBBBBBBB', '11111111-1111-1111-1111-111111111111');
INSERT INTO promo_codes (id, campaign_id, code, max_redemptions, redeemed_count, is_active)
VALUES ('ffffffff-0000-0000-0000-000000000001', 'eeeeeeee-0000-0000-0000-000000000001', 'SPRING10', 2, 0, true);

INSERT INTO seat_holds (id, event_id, seat_id, user_id, status, expires_at)
VALUES ('12121212-0000-0000-0000-000000000001', '88888888-8888-8888-8888-888888888888', '77777777-7777-7777-7777-777777777777',
        '22222222-2222-2222-2222-222222222222', 'active', now() + interval '10 minutes');

INSERT INTO audit_log_entries (id, actor_user_id, action_type, entity_type, entity_id, description, event_id)
VALUES ('13131313-0000-0000-0000-000000000001', '11111111-1111-1111-1111-111111111111', 'event.published', 'event',
        '88888888-8888-8888-8888-888888888888', 'Event published', '88888888-8888-8888-8888-888888888888');

COMMIT;

-- ===================================================================
-- Each block below MUST fail. A "PASS" line means the database refused it.
-- ===================================================================
CREATE OR REPLACE FUNCTION expect_failure(label text, stmt text) RETURNS void AS $$
BEGIN
    EXECUTE stmt;
    RAISE WARNING 'FAIL  %  <- statement was ACCEPTED but should have been rejected', label;
EXCEPTION WHEN others THEN
    RAISE NOTICE 'PASS  %  (%)', label, left(SQLERRM, 70);
END;
$$ LANGUAGE plpgsql;

-- 1. SRS 4.3.1 -- two active tickets on the same seat for the same event.
SELECT expect_failure('seat double-sell blocked',
$q$INSERT INTO tickets (id, ticket_number, order_id, order_item_id, event_id, ticket_type_id, attendee_id, status, admission_token, seat_id, price_kzt)
   VALUES ('dddddddd-0000-0000-0000-000000000002','BF-T-0002','aaaaaaaa-0000-0000-0000-000000000002','bbbbbbbb-0000-0000-0000-000000000002',
           '88888888-8888-8888-8888-888888888888','99999999-9999-9999-9999-999999999999','cccccccc-0000-0000-0000-000000000002',
           'valid','BFT1.CCCCCCCCCCCCCCCCCCCCCCCCCC','77777777-7777-7777-7777-777777777777',5000)$q$);

-- 2. SRS 4.3.1 -- a second live hold on a seat already held.
SELECT expect_failure('double seat hold blocked',
$q$INSERT INTO seat_holds (id, event_id, seat_id, user_id, status, expires_at)
   VALUES ('12121212-0000-0000-0000-000000000002','88888888-8888-8888-8888-888888888888','77777777-7777-7777-7777-777777777777',
           '11111111-1111-1111-1111-111111111111','active', now() + interval '10 minutes')$q$);

-- 3. SRS 7 -- redemption counter cannot pass max_redemptions, atomically.
SELECT expect_failure('promo over-redemption blocked',
$q$UPDATE promo_codes SET redeemed_count = redeemed_count + 3 WHERE id = 'ffffffff-0000-0000-0000-000000000001'$q$);

-- 4. SRS 4.16 -- audit log is append-only.
SELECT expect_failure('audit UPDATE blocked',
$q$UPDATE audit_log_entries SET description = 'tampered' WHERE id = '13131313-0000-0000-0000-000000000001'$q$);
SELECT expect_failure('audit DELETE blocked',
$q$DELETE FROM audit_log_entries WHERE id = '13131313-0000-0000-0000-000000000001'$q$);

-- 5. SRS 4.14 -- a discount cannot exceed the subtotal.
SELECT expect_failure('discount over subtotal blocked',
$q$UPDATE orders SET discount_kzt = 999999 WHERE id = 'aaaaaaaa-0000-0000-0000-000000000001'$q$);

-- 6. SRS 4.3 -- inventory cannot be oversold.
SELECT expect_failure('ticket oversell blocked',
$q$UPDATE ticket_types SET quantity_sold = 101 WHERE id = '99999999-9999-9999-9999-999999999999'$q$);

-- 7. Campaign discount shape: percentage type must not carry a fixed-KZT amount.
SELECT expect_failure('malformed campaign discount blocked',
$q$UPDATE promotional_campaigns SET discount_kzt = 500 WHERE id = 'eeeeeeee-0000-0000-0000-000000000001'$q$);

-- ===================================================================
-- These MUST succeed -- the partial index has to release the seat too.
-- ===================================================================
DO $$
BEGIN
    UPDATE tickets SET status = 'refunded', refunded_at = now()
     WHERE id = 'dddddddd-0000-0000-0000-000000000001';
    INSERT INTO tickets (id, ticket_number, order_id, order_item_id, event_id, ticket_type_id, attendee_id, status, admission_token, seat_id, price_kzt)
    VALUES ('dddddddd-0000-0000-0000-000000000003','BF-T-0003','aaaaaaaa-0000-0000-0000-000000000002','bbbbbbbb-0000-0000-0000-000000000002',
            '88888888-8888-8888-8888-888888888888','99999999-9999-9999-9999-999999999999','cccccccc-0000-0000-0000-000000000002',
            'valid','BFT1.DDDDDDDDDDDDDDDDDDDDDDDDDD','77777777-7777-7777-7777-777777777777',5000);
    RAISE NOTICE 'PASS  refunded ticket frees its seat for resale';
EXCEPTION WHEN others THEN
    RAISE WARNING 'FAIL  refunded seat not released: %', SQLERRM;
END $$;

DO $$
BEGIN
    UPDATE promo_codes SET redeemed_count = redeemed_count + 1 WHERE id = 'ffffffff-0000-0000-0000-000000000001';
    UPDATE promo_codes SET redeemed_count = redeemed_count + 1 WHERE id = 'ffffffff-0000-0000-0000-000000000001';
    RAISE NOTICE 'PASS  promo redemption increments up to the limit';
EXCEPTION WHEN others THEN
    RAISE WARNING 'FAIL  legitimate redemption rejected: %', SQLERRM;
END $$;

DO $$
BEGIN
    INSERT INTO audit_log_entries (actor_user_id, action_type, entity_type, description)
    VALUES ('11111111-1111-1111-1111-111111111111','ticket.refunded','ticket','Refunded');
    RAISE NOTICE 'PASS  audit log still accepts new entries';
EXCEPTION WHEN others THEN
    RAISE WARNING 'FAIL  append blocked too: %', SQLERRM;
END $$;

DROP FUNCTION expect_failure(text, text);
