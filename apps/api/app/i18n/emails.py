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
}
