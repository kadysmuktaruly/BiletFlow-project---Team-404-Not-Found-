"""Every user-facing email string, in Kazakh, Russian and English.

Each template is a subject plus an ordered list of body blocks. `app.services.mail.render`
turns them into a plain-text part and an HTML part. Placeholders use `str.format` names;
values are HTML-escaped when rendered, so user input (names, event titles) is safe here.

Payment-related templates must say DEMO wherever money is mentioned (SRS 4.6: demonstration
records are never presented as real financial transactions).
"""

from typing import TypedDict

from app.i18n import Locale


class EmailTemplate(TypedDict, total=False):
    subject: str
    greeting: str
    paragraphs: list[str]
    action: str
    note: str


Catalog = dict[str, dict[Locale, EmailTemplate]]

FOOTER: dict[Locale, str] = {
    "kk": "BiletFlow — Қазақстандағы іс-шараларға билеттер",
    "ru": "BiletFlow — билеты на мероприятия в Казахстане",
    "en": "BiletFlow — event tickets for Kazakhstan",
}

EMAILS: Catalog = {
    "verify_email": {
        "kk": {
            "subject": "BiletFlow электрондық поштаңызды растаңыз",
            "greeting": "Сәлеметсіз бе, {name}!",
            "paragraphs": ["Электрондық пошта мекенжайыңызды төмендегі сілтеме арқылы растаңыз."],
            "action": "Поштаны растау",
            "note": "Сілтеме {hours} сағат жарамды. Егер сіз BiletFlow-та тіркелмеген "
            "болсаңыз, бұл хатты елемеңіз.",
        },
        "ru": {
            "subject": "Подтвердите адрес электронной почты в BiletFlow",
            "greeting": "Здравствуйте, {name}!",
            "paragraphs": ["Подтвердите адрес электронной почты по ссылке ниже."],
            "action": "Подтвердить почту",
            "note": "Ссылка действительна {hours} ч. Если вы не регистрировались в BiletFlow, "
            "просто проигнорируйте это письмо.",
        },
        "en": {
            "subject": "Confirm your BiletFlow email",
            "greeting": "Hello {name},",
            "paragraphs": ["Confirm your email address using the link below."],
            "action": "Confirm email",
            "note": "The link expires in {hours} hours. If you didn't create a BiletFlow "
            "account, you can ignore this email.",
        },
    },
    "reset_password": {
        "kk": {
            "subject": "BiletFlow құпиясөзін қалпына келтіру",
            "greeting": "Сәлеметсіз бе, {name}!",
            "paragraphs": ["Жаңа құпиясөз орнату үшін төмендегі сілтемені ашыңыз."],
            "action": "Жаңа құпиясөз орнату",
            "note": "Сілтеме {minutes} минут жарамды және бір рет қана жұмыс істейді. Егер "
            "құпиясөзді қалпына келтіруді сұрамаған болсаңыз, бұл хатты елемеңіз — "
            "құпиясөзіңіз өзгермейді.",
        },
        "ru": {
            "subject": "Сброс пароля BiletFlow",
            "greeting": "Здравствуйте, {name}!",
            "paragraphs": ["Чтобы задать новый пароль, перейдите по ссылке ниже."],
            "action": "Задать новый пароль",
            "note": "Ссылка действительна {minutes} мин и срабатывает один раз. Если вы не "
            "запрашивали сброс пароля, проигнорируйте это письмо — пароль останется прежним.",
        },
        "en": {
            "subject": "Reset your BiletFlow password",
            "greeting": "Hello {name},",
            "paragraphs": ["To choose a new password, open the link below."],
            "action": "Choose a new password",
            "note": "The link expires in {minutes} minutes and works once. If you didn't ask "
            "to reset your password, ignore this email; your password stays the same.",
        },
    },
    "order_confirmed": {
        "kk": {
            "subject": "Билеттеріңіз: {event}",
            "greeting": "Сәлеметсіз бе, {name}!",
            "paragraphs": [
                "Тапсырыс {reference} расталды. Билеттеріңіз төменде.",
                "{event} — {when}, {venue}.",
            ],
            "action": "Менің билеттерім",
            "note": "Кіреберісте QR-кодты көрсетіңіз. Әр код бір рет қана жарамды.",
        },
        "ru": {
            "subject": "Ваши билеты: {event}",
            "greeting": "Здравствуйте, {name}!",
            "paragraphs": [
                "Заказ {reference} подтверждён. Ваши билеты ниже.",
                "{event} — {when}, {venue}.",
            ],
            "action": "Мои билеты",
            "note": "Покажите QR-код на входе. Каждый код действует один раз.",
        },
        "en": {
            "subject": "Your tickets: {event}",
            "greeting": "Hello {name},",
            "paragraphs": [
                "Order {reference} is confirmed. Your tickets are below.",
                "{event}, {when}, {venue}.",
            ],
            "action": "My tickets",
            "note": "Show the QR code at the entrance. Each code admits one person, once.",
        },
    },
    "payment_failed": {
        "kk": {
            "subject": "DEMO төлемі өтпеді: {event}",
            "greeting": "Сәлеметсіз бе, {name}!",
            "paragraphs": [
                "{reference} тапсырысы бойынша DEMO төлемі өтпеді. Нақты ақша алынған жоқ.",
                "Билеттер сатылымға қайтарылды. Қайталап көргіңіз келсе, іс-шара бетін ашыңыз.",
            ],
            "action": "Іс-шара беті",
        },
        "ru": {
            "subject": "DEMO-оплата не прошла: {event}",
            "greeting": "Здравствуйте, {name}!",
            "paragraphs": [
                "DEMO-оплата по заказу {reference} не прошла. Настоящие деньги не списаны.",
                "Билеты вернулись в продажу. Чтобы попробовать снова, "
                "откройте страницу мероприятия.",
            ],
            "action": "Страница мероприятия",
        },
        "en": {
            "subject": "DEMO payment failed: {event}",
            "greeting": "Hello {name},",
            "paragraphs": [
                "The DEMO payment for order {reference} didn't go through. "
                "No real money was taken.",
                "The tickets have gone back on sale. To try again, open the event page.",
            ],
            "action": "Event page",
        },
    },
    # --- SRS 4.10: event updates and cancellations ----------------------------------------
    "event_updated": {
        "kk": {
            "subject": "Іс-шара өзгерді: {event}",
            "greeting": "Сәлеметсіз бе, {name}!",
            "paragraphs": [
                "Ұйымдастырушы {event} іс-шарасын өзгертті: {changes}.",
                "Қазіргі мәлімет: {when}, {venue}. Билеттеріңіз жарамды күйінде қалады.",
            ],
            "action": "Іс-шара беті",
        },
        "ru": {
            "subject": "Мероприятие изменилось: {event}",
            "greeting": "Здравствуйте, {name}!",
            "paragraphs": [
                "Организатор изменил мероприятие {event}: {changes}.",
                "Сейчас: {when}, {venue}. Ваши билеты остаются в силе.",
            ],
            "action": "Страница мероприятия",
        },
        "en": {
            "subject": "Event updated: {event}",
            "greeting": "Hello {name},",
            "paragraphs": [
                "The organizer changed {event}: {changes}.",
                "Now: {when}, {venue}. Your tickets are still valid.",
            ],
            "action": "Event page",
        },
    },
    "event_cancelled": {
        "kk": {
            "subject": "Іс-шара тоқтатылды: {event}",
            "greeting": "Сәлеметсіз бе, {name}!",
            "paragraphs": [
                "Ұйымдастырушы {when} өтуі тиіс {event} іс-шарасын тоқтатты.",
                "Билеттеріңіз енді жарамсыз. Ақылы тапсырыстар толық қайтарылады "
                "(DEMO: нақты ақша аударылмайды).",
            ],
            "action": "Менің тапсырыстарым",
        },
        "ru": {
            "subject": "Мероприятие отменено: {event}",
            "greeting": "Здравствуйте, {name}!",
            "paragraphs": [
                "Организатор отменил мероприятие {event}, которое должно было пройти {when}.",
                "Ваши билеты больше не действуют. Платные заказы возвращаются полностью "
                "(DEMO: настоящие деньги не переводятся).",
            ],
            "action": "Мои заказы",
        },
        "en": {
            "subject": "Event cancelled: {event}",
            "greeting": "Hello {name},",
            "paragraphs": [
                "The organizer has cancelled {event}, which was due to take place on {when}.",
                "Your tickets are no longer valid. Paid orders are refunded in full "
                "(DEMO: no real money moves).",
            ],
            "action": "My orders",
        },
    },
    # --- SRS 4.9 / 4.10: refunds ---------------------------------------------------------
    "refund_completed": {
        "kk": {
            "subject": "DEMO қайтарымы аяқталды: {event}",
            "greeting": "Сәлеметсіз бе, {name}!",
            "paragraphs": [
                "{reference} тапсырысы бойынша {amount} DEMO қайтарымы аяқталды. "
                "Бұл симуляция, нақты ақша аударылған жоқ.",
                "Осы тапсырыстағы билеттер енді жарамсыз.",
            ],
            "action": "Тапсырысты ашу",
        },
        "ru": {
            "subject": "DEMO-возврат выполнен: {event}",
            "greeting": "Здравствуйте, {name}!",
            "paragraphs": [
                "DEMO-возврат {amount} по заказу {reference} выполнен. Это симуляция, "
                "настоящие деньги не переводились.",
                "Билеты из этого заказа больше не действуют.",
            ],
            "action": "Открыть заказ",
        },
        "en": {
            "subject": "DEMO refund complete: {event}",
            "greeting": "Hello {name},",
            "paragraphs": [
                "The DEMO refund of {amount} for order {reference} is complete. This is a "
                "simulation; no real money moved.",
                "The tickets in this order are no longer valid.",
            ],
            "action": "View order",
        },
    },
    "registration_cancelled": {
        "kk": {
            "subject": "Тіркеу тоқтатылды: {event}",
            "greeting": "Сәлеметсіз бе, {name}!",
            "paragraphs": [
                "Ұйымдастырушы {event} іс-шарасына {reference} тіркеуіңізді тоқтатты.",
                "Осы тапсырыстағы билеттер енді жарамсыз.",
            ],
            "action": "Тапсырысты ашу",
        },
        "ru": {
            "subject": "Регистрация отменена: {event}",
            "greeting": "Здравствуйте, {name}!",
            "paragraphs": [
                "Организатор отменил вашу регистрацию {reference} на мероприятие {event}.",
                "Билеты из этого заказа больше не действуют.",
            ],
            "action": "Открыть заказ",
        },
        "en": {
            "subject": "Registration cancelled: {event}",
            "greeting": "Hello {name},",
            "paragraphs": [
                "The organizer cancelled your registration {reference} for {event}.",
                "The tickets in this order are no longer valid.",
            ],
            "action": "View order",
        },
    },
    # --- SRS 4.10: organizer payout status (DEMO; payouts are shown, never executed) -------
    "payout_status": {
        "kk": {
            "subject": "Төлем шоты: {status}",
            "greeting": "Сәлеметсіз бе, {name}!",
            "paragraphs": [
                "Соңы {last4} болатын төлем шотыңыздың мәртебесі: {status} (DEMO).",
                "Бұл демонстрацияда төлемдер тек көрсетіледі, нақты ақша аударылмайды.",
            ],
            "action": "Ұйымдастырушы профилі",
        },
        "ru": {
            "subject": "Счёт для выплат: {status}",
            "greeting": "Здравствуйте, {name}!",
            "paragraphs": [
                "Статус счёта для выплат с окончанием {last4}: {status} (DEMO).",
                "В этой демонстрации выплаты только отображаются, настоящие деньги не переводятся.",
            ],
            "action": "Профиль организатора",
        },
        "en": {
            "subject": "Payout account: {status}",
            "greeting": "Hello {name},",
            "paragraphs": [
                "Your payout account ending in {last4} is now {status} (DEMO).",
                "In this demo, payouts are shown but never executed; no real money moves.",
            ],
            "action": "Organizer profile",
        },
    },
    # --- SRS 4.13: support cases ---------------------------------------------------------
    "support_new_message": {
        "kk": {
            "subject": "Жаңа жауап: {reference}",
            "greeting": "Сәлеметсіз бе, {name}!",
            "paragraphs": ["{reference} «{subject}» қолдау өтінішінде жаңа хабарлама бар."],
            "action": "Өтінішті ашу",
        },
        "ru": {
            "subject": "Новый ответ: {reference}",
            "greeting": "Здравствуйте, {name}!",
            "paragraphs": ["В обращении {reference} «{subject}» новое сообщение."],
            "action": "Открыть обращение",
        },
        "en": {
            "subject": "New reply: {reference}",
            "greeting": "Hello {name},",
            "paragraphs": ["There's a new message in support case {reference}, '{subject}'."],
            "action": "Open case",
        },
    },
    "support_case_assigned": {
        "kk": {
            "subject": "Сізге өтініш тағайындалды: {reference}",
            "greeting": "Сәлеметсіз бе, {name}!",
            "paragraphs": ["{reference} «{subject}» қолдау өтініші сізге тағайындалды."],
            "action": "Өтінішті ашу",
        },
        "ru": {
            "subject": "Вам назначено обращение: {reference}",
            "greeting": "Здравствуйте, {name}!",
            "paragraphs": ["Вам назначено обращение в поддержку {reference} «{subject}»."],
            "action": "Открыть обращение",
        },
        "en": {
            "subject": "Case assigned to you: {reference}",
            "greeting": "Hello {name},",
            "paragraphs": ["Support case {reference}, '{subject}', has been assigned to you."],
            "action": "Open case",
        },
    },
    "support_status_changed": {
        "kk": {
            "subject": "Өтініш мәртебесі: {status}",
            "greeting": "Сәлеметсіз бе, {name}!",
            "paragraphs": ["{reference} «{subject}» өтінішінің жаңа мәртебесі: {status}."],
            "action": "Өтінішті ашу",
        },
        "ru": {
            "subject": "Статус обращения: {status}",
            "greeting": "Здравствуйте, {name}!",
            "paragraphs": ["Новый статус обращения {reference} «{subject}»: {status}."],
            "action": "Открыть обращение",
        },
        "en": {
            "subject": "Case status: {status}",
            "greeting": "Hello {name},",
            "paragraphs": ["Support case {reference}, '{subject}', is now: {status}."],
            "action": "Open case",
        },
    },
}

# Status names that appear inside notifications, per locale.
SUPPORT_STATUS: dict[Locale, dict[str, str]] = {
    "kk": {
        "open": "Ашық",
        "in_progress": "Өңделуде",
        "waiting_for_customer": "Сіздің жауабыңыз күтілуде",
        "resolved": "Шешілді",
    },
    "ru": {
        "open": "Открыто",
        "in_progress": "В работе",
        "waiting_for_customer": "Ждём вашего ответа",
        "resolved": "Решено",
    },
    "en": {
        "open": "Open",
        "in_progress": "In progress",
        "waiting_for_customer": "Waiting for your reply",
        "resolved": "Resolved",
    },
}

PAYOUT_STATUS: dict[Locale, dict[str, str]] = {
    "kk": {"verified": "расталды", "pending": "тексерілуде", "rejected": "қабылданбады"},
    "ru": {"verified": "подтверждён", "pending": "на проверке", "rejected": "отклонён"},
    "en": {"verified": "verified", "pending": "pending", "rejected": "rejected"},
}

EVENT_CHANGES: dict[Locale, dict[str, str]] = {
    "kk": {"time": "уақыты", "venue": "өтетін орны", "title": "атауы"},
    "ru": {"time": "время", "venue": "место проведения", "title": "название"},
    "en": {"time": "time", "venue": "venue", "title": "title"},
}

# Labels for the per-ticket blocks inside the order confirmation.
TICKET_LABELS: dict[Locale, dict[str, str]] = {
    "kk": {
        "ticket": "Билет",
        "ticket_type": "Түрі",
        "attendee": "Қатысушы",
        "free": "Тегін тіркелу. Төлем қажет емес.",
        "paid": "DEMO төлемі: {amount}. Бұл симуляция, нақты ақша алынған жоқ.",
    },
    "ru": {
        "ticket": "Билет",
        "ticket_type": "Тип",
        "attendee": "Участник",
        "free": "Бесплатная регистрация. Оплата не требуется.",
        "paid": "DEMO-оплата: {amount}. Это симуляция, настоящие деньги не списаны.",
    },
    "en": {
        "ticket": "Ticket",
        "ticket_type": "Type",
        "attendee": "Attendee",
        "free": "Free registration. No payment needed.",
        "paid": "DEMO payment: {amount}. This is a simulation; no real money was charged.",
    },
}
