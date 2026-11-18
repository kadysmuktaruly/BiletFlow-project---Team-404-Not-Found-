"""Text printed on server-generated documents: the PDF ticket and the Campaign QR (SRS 4.7,
4.14), in kk / ru / en. Keys are the same in every locale (`tests/test_documents.py`)."""

from app.i18n import Locale

TICKET_PDF: dict[Locale, dict[str, str]] = {
    "kk": {
        "doc_title": "Кіру билеті",
        "when": "Күні мен уақыты",
        "venue": "Өтетін орны",
        "ticket_type": "Билет түрі",
        "attendee": "Қатысушы",
        "seat": "Орын",
        "seat_value": "Секция {section}, қатар {row}, орын {number}",
        "ticket_number": "Билет нөмірі",
        "status": "Мәртебесі",
        "printed_at": "Басып шығарылған уақыт",
        "instructions": (
            "Кіреберісте осы QR кодты көрсетіңіз: экраннан немесе қағазға басып. Басылған және "
            "электрондық көшірме бір билет болып саналады, бір рет қана жарамды."
        ),
        "not_valid": "Бұл билет кіруге жарамсыз.",
    },
    "ru": {
        "doc_title": "Входной билет",
        "when": "Дата и время",
        "venue": "Место проведения",
        "ticket_type": "Тип билета",
        "attendee": "Участник",
        "seat": "Место",
        "seat_value": "Сектор {section}, ряд {row}, место {number}",
        "ticket_number": "Номер билета",
        "status": "Статус",
        "printed_at": "Распечатано",
        "instructions": (
            "Покажите этот QR-код на входе — на экране или на бумаге. Распечатанный и "
            "электронный билет — это один и тот же билет, он действует один раз."
        ),
        "not_valid": "Этот билет недействителен для входа.",
    },
    "en": {
        "doc_title": "Admission ticket",
        "when": "Date and time",
        "venue": "Venue",
        "ticket_type": "Ticket type",
        "attendee": "Attendee",
        "seat": "Seat",
        "seat_value": "Section {section}, row {row}, seat {number}",
        "ticket_number": "Ticket number",
        "status": "Status",
        "printed_at": "Printed",
        "instructions": (
            "Show this QR code at the entrance, on screen or on paper. The printed and digital "
            "copies are the same ticket and admit one person once."
        ),
        "not_valid": "This ticket is not valid for entry.",
    },
}

TICKET_STATUS: dict[Locale, dict[str, str]] = {
    "kk": {
        "valid": "Жарамды",
        "checked_in": "Кіру белгіленді",
        "cancelled": "Тоқтатылды",
        "refunded": "Қайтарылды",
    },
    "ru": {
        "valid": "Действителен",
        "checked_in": "Вход отмечен",
        "cancelled": "Отменён",
        "refunded": "Возвращён",
    },
    "en": {
        "valid": "Valid",
        "checked_in": "Checked in",
        "cancelled": "Cancelled",
        "refunded": "Refunded",
    },
}

CAMPAIGN_QR: dict[Locale, dict[str, str]] = {
    "kk": {
        "banner": "ПРОМО · БИЛЕТ ЕМЕС",
        "scan": "Сканерлеңіз: іс-шара беті промокодпен ашылады",
        "code": "Промокод",
        "no_entry": "Бұл кодпен кіруге болмайды.",
    },
    "ru": {
        "banner": "ПРОМО · НЕ БИЛЕТ",
        "scan": "Отсканируйте: страница события откроется с промокодом",
        "code": "Промокод",
        "no_entry": "По этому коду вход не выполняется.",
    },
    "en": {
        "banner": "PROMO · NOT A TICKET",
        "scan": "Scan to open the event with the promo code applied",
        "code": "Promo code",
        "no_entry": "This code does not admit anyone.",
    },
}
