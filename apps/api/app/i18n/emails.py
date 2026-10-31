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
