"""Localized copy for the staff-group Telegram alert bot (uz / ru / en).

Language source of truth (first match wins):
  1. Per-group override in AppState ``alert_lang:{chat_id}`` (staff can change live)
  2. Brand ``profile_config.alert_language`` (dashboard preference)
  3. Global AppState ``alert_lang``
  4. Default ``uz``
"""

from __future__ import annotations

from typing import Any

SUPPORTED_LANGS = ("uz", "ru", "en")
DEFAULT_LANG = "uz"
LANG_STATE_GLOBAL = "alert_lang"
LANG_STATE_CHAT_PREFIX = "alert_lang:"

_STRINGS: dict[str, dict[str, str]] = {
    "card_title": {
        "uz": "Reputatsion xavf signali",
        "ru": "Сигнал репутационного риска",
        "en": "Reputation risk signal",
    },
    "brand": {"uz": "Brend", "ru": "Бренд", "en": "Brand"},
    "source": {"uz": "Manba", "ru": "Источник", "en": "Source"},
    "author": {"uz": "Muallif", "ru": "Автор", "en": "Author"},
    "risk": {"uz": "Risk", "ru": "Риск", "en": "Risk"},
    "sentiment": {"uz": "Kayfiyat", "ru": "Тональность", "en": "Sentiment"},
    "text": {"uz": "Matn", "ru": "Текст", "en": "Text"},
    "summary": {"uz": "Xulosa", "ru": "Вывод", "en": "Summary"},
    "suggested_action": {"uz": "Tavsiya", "ru": "Рекомендация", "en": "Suggested action"},
    "platform": {"uz": "Platforma", "ru": "Платформа", "en": "Platform"},
    "status": {"uz": "Holat", "ru": "Статус", "en": "Status"},
    "status_open": {
        "uz": "Yangi — hali olinmagan",
        "ru": "Новый — ещё не взят",
        "en": "New — not claimed yet",
    },
    "status_checking": {
        "uz": "Tahlil qilinmoqda…",
        "ru": "Идёт разбор…",
        "en": "In progress…",
    },
    "status_checked": {
        "uz": "Tahlil qilinmoqda",
        "ru": "Идёт разбор",
        "en": "In progress",
    },
    "status_waiting_reply": {
        "uz": "Xodim kommentga javob yozmoqda — boshqalar kutsin",
        "ru": "Сотрудник отвечает — остальные ждут",
        "en": "Staff is replying — others wait",
    },
    "status_open_link": {
        "uz": "Kommentga o'tish",
        "ru": "Открыть комментарий",
        "en": "Open the comment",
    },
    "status_answered": {
        "uz": "Javob berildi",
        "ru": "Ответ дан",
        "en": "Answered",
    },
    "answered_by": {
        "uz": "Javob bergan xodim",
        "ru": "Ответил сотрудник",
        "en": "Answered by",
    },
    "checked_by": {
        "uz": "Tekshirgan xodim",
        "ru": "Проверил сотрудник",
        "en": "Reviewed by",
    },
    "duration": {"uz": "Javob vaqti", "ru": "Время ответа", "en": "Response time"},
    "btn_reply": {"uz": "Javob berish", "ru": "Ответить", "en": "Reply"},
    "btn_replying": {
        "uz": "Tahlil qilinmoqda…",
        "ru": "Идёт разбор…",
        "en": "In progress…",
    },
    "btn_answer": {"uz": "Javob berdim", "ru": "Ответил", "en": "I replied"},
    "btn_reopen": {"uz": "Qayta ochish", "ru": "Открыть снова", "en": "Reopen"},
    "btn_refresh": {"uz": "Yangilash", "ru": "Обновить", "en": "Refresh"},
    "btn_open_list": {"uz": "Ochiq ro'yxat", "ru": "Открытый список", "en": "Open list"},
    "btn_staff_table": {
        "uz": "Xodimlar jadvali",
        "ru": "Таблица сотрудников",
        "en": "Staff table",
    },
    "btn_lang": {"uz": "Til", "ru": "Язык", "en": "Language"},
    "toast_refreshed": {"uz": "Yangilandi.", "ru": "Обновлено.", "en": "Updated."},
    "toast_staff_only": {
        "uz": "Bu tugmalar faqat xodimlar guruhida ishlaydi.",
        "ru": "Эти кнопки работают только в группе сотрудников.",
        "en": "These buttons only work in the staff group.",
    },
    "toast_not_found": {
        "uz": "Signal topilmadi.",
        "ru": "Сигнал не найден.",
        "en": "Signal not found.",
    },
    "toast_error": {
        "uz": "Xatolik yuz berdi, qayta urinib ko'ring.",
        "ru": "Ошибка, попробуйте ещё раз.",
        "en": "Something went wrong, try again.",
    },
    "toast_reply_claimed": {
        "uz": "Tahlil qilinmoqda. Komment linki shu yerga yuborildi — mijozga reply qilib javob yozing, so'ng «Javob berdim»ni bosing.",
        "ru": "Идёт разбор. Ссылка на комментарий отправлена — ответьте клиенту, затем «Ответил».",
        "en": "In progress. Comment link sent — reply to the customer, then press «I replied».",
    },
    "toast_already_replying": {
        "uz": "{name} allaqachon javob bermoqda ({time}). Boshqa signal oling.",
        "ru": "{name} уже отвечает ({time}). Возьмите другой сигнал.",
        "en": "{name} is already handling this ({time}). Take another signal.",
    },
    "toast_ai_verify_ok": {
        "uz": "AI tasdiqladi: yordam yetarli. Signal yopildi.",
        "ru": "AI подтвердил: помощь достаточна. Сигнал закрыт.",
        "en": "AI confirmed: help was sufficient. Signal closed.",
    },
    "toast_ai_verify_fail": {
        "uz": "AI: javob yetarli emas. Post o'zgarmadi, hisobga olinmadi. Sabab: {reason}",
        "ru": "AI: ответа недостаточно. Пост без изменений. Причина: {reason}",
        "en": "AI: reply not sufficient. Post unchanged. Reason: {reason}",
    },
    "toast_ai_verify_error": {
        "uz": "AI tekshiruvi ishlamadi. Keyinroq qayta urinib ko'ring.",
        "ru": "Проверка AI не удалась. Попробуйте позже.",
        "en": "AI check failed. Try again later.",
    },
    "toast_need_reply_first": {
        "uz": "Avval «Javob berish»ni bosing va kommentga o'ting.",
        "ru": "Сначала нажмите «Ответить» и откройте комментарий.",
        "en": "Press «Reply» first and open the comment.",
    },
    "toast_already_answered_by": {
        "uz": "{name} allaqachon javob bergan ({time}).",
        "ru": "{name} уже ответил(а) ({time}).",
        "en": "{name} already answered ({time}).",
    },
    "toast_already_closed_self": {
        "uz": "Siz bu signalni allaqachon yopgansiz.",
        "ru": "Вы уже закрыли этот сигнал.",
        "en": "You already closed this signal.",
    },
    "toast_closed": {
        "uz": "Rahmat! Signal yopildi.",
        "ru": "Спасибо! Сигнал закрыт.",
        "en": "Thanks! Signal closed.",
    },
    "toast_reopened": {
        "uz": "Qayta ochildi ({name}).",
        "ru": "Снова открыт ({name}).",
        "en": "Reopened ({name}).",
    },
    "toast_closed_cannot_check": {
        "uz": "Bu signal yopilgan — javobni {name} bergan.",
        "ru": "Сигнал закрыт — ответил {name}.",
        "en": "Closed — answered by {name}.",
    },
    "toast_already_open": {
        "uz": "Bu signal allaqachon ochiq.",
        "ru": "Сигнал уже открыт.",
        "en": "This signal is already open.",
    },
    "toast_unknown_action": {
        "uz": "Noma'lum amal.",
        "ru": "Неизвестное действие.",
        "en": "Unknown action.",
    },
    "toast_opening_link": {
        "uz": "Tekshirilyapti… Kommentga o'ting va mijozga javob yozing.",
        "ru": "Проверяется… Откройте комментарий и ответьте клиенту.",
        "en": "Under review… Open the comment and reply to the customer.",
    },
    "toast_no_link": {
        "uz": "Bu signalda ochiladigan havola yo'q.",
        "ru": "У этого сигнала нет ссылки.",
        "en": "This signal has no openable link.",
    },
    "toast_lang_set": {
        "uz": "Bot tili: {name}",
        "ru": "Язык бота: {name}",
        "en": "Bot language: {name}",
    },
    "summary_all_clear": {
        "uz": "Javobsiz signal yo'q — hammasi yopilgan",
        "ru": "Нет открытых сигналов — всё закрыто",
        "en": "No open signals — all closed",
    },
    "summary_waiting": {
        "uz": "Javob kutayotgan signallar: {n}",
        "ru": "Сигналов ждут ответа: {n}",
        "en": "Signals waiting for reply: {n}",
    },
    "summary_oldest": {
        "uz": "Eng eskisi: {d} kutmoqda",
        "ru": "Самый старый: ждёт {d}",
        "en": "Oldest waiting: {d}",
    },
    "summary_checked_waiting": {
        "uz": "Tekshirilgan, javob kutmoqda: {n}",
        "ru": "Проверено, ждут ответа: {n}",
        "en": "Reviewed, waiting for reply: {n}",
    },
    "summary_by_source": {
        "uz": "Manbalar bo'yicha:",
        "ru": "По источникам:",
        "en": "By source:",
    },
    "summary_today_closed": {
        "uz": "Bugun yopildi: {n} · O'rtacha javob vaqti: {avg}",
        "ru": "Закрыто сегодня: {n} · Среднее время ответа: {avg}",
        "en": "Closed today: {n} · Avg response time: {avg}",
    },
    "summary_staff": {"uz": "Xodimlar:", "ru": "Сотрудники:", "en": "Staff:"},
    "summary_updated": {"uz": "Yangilandi:", "ru": "Обновлено:", "en": "Updated:"},
    "open_list_title": {
        "uz": "Javob kutayotgan signallar: {n}",
        "ru": "Сигналы ждут ответа: {n}",
        "en": "Signals waiting for reply: {n}",
    },
    "open_list_empty": {
        "uz": "Ochiq signal yo'q — barcha mijozlarga javob berilgan.",
        "ru": "Открытых сигналов нет — всем клиентам ответили.",
        "en": "No open signals — every customer was answered.",
    },
    "open_list_more": {
        "uz": "... yana {n} ta",
        "ru": "... ещё {n}",
        "en": "... and {n} more",
    },
    "stats_title": {"uz": "Bugungi hisobot", "ru": "Отчёт за сегодня", "en": "Today's report"},
    "stats_closed": {"uz": "Yopilgan: {n}", "ru": "Закрыто: {n}", "en": "Closed: {n}"},
    "stats_avg": {
        "uz": "O'rtacha javob vaqti: {avg}",
        "ru": "Среднее время ответа: {avg}",
        "en": "Avg response time: {avg}",
    },
    "stats_open": {
        "uz": "Ochiq qolgan: {open} (tekshirilgan: {checked})",
        "ru": "Открыто: {open} (проверено: {checked})",
        "en": "Still open: {open} (reviewed: {checked})",
    },
    "leaderboard_title": {
        "uz": "Xodimlar jadvali — bugun kim nechta javob berdi",
        "ru": "Таблица сотрудников — кто сколько ответил сегодня",
        "en": "Staff table — replies closed today",
    },
    "leaderboard_empty": {
        "uz": "Bugun hali hech kim signal yopmagan.",
        "ru": "Сегодня ещё никто не закрыл сигнал.",
        "en": "Nobody has closed a signal today yet.",
    },
    "leaderboard_row": {
        "uz": "{rank}. {name} — {count} ta javob",
        "ru": "{rank}. {name} — {count} ответ(ов)",
        "en": "{rank}. {name} — {count} replies",
    },
    "leaderboard_total": {
        "uz": "Jami yopilgan: {n}",
        "ru": "Всего закрыто: {n}",
        "en": "Total closed: {n}",
    },
    "sla_nudge_unseen": {
        "uz": "Hali hech kim ko'rmadi",
        "ru": "Ещё никто не смотрел",
        "en": "Nobody has looked yet",
    },
    "sla_nudge_checked": {
        "uz": "Tekshirilgan, lekin javob berilmagan",
        "ru": "Проверено, но без ответа",
        "en": "Reviewed but not answered",
    },
    "sla_nudge_body": {
        "uz": "{waited} javobsiz turibdi — {who}.\nManba: {source}\nKim oladi? Javob bergach «Javob berdim» tugmasini bosing.",
        "ru": "{waited} без ответа — {who}.\nИсточник: {source}\nКто возьмёт? После ответа нажмите «Ответил».",
        "en": "{waited} unanswered — {who}.\nSource: {source}\nWho takes it? Press «I replied» after answering.",
    },
    "lang_help": {
        "uz": "Bot tili: {current}\nO'zgartirish: /til uz | /til ru | /til en",
        "ru": "Язык бота: {current}\nСмена: /til uz | /til ru | /til en",
        "en": "Bot language: {current}\nChange: /til uz | /til ru | /til en",
    },
    "lang_pick": {
        "uz": "Guruh bot tili",
        "ru": "Язык бота в группе",
        "en": "Group bot language",
    },
}

PLATFORM_LABELS = {
    "telegram": {"uz": "Telegram", "ru": "Telegram", "en": "Telegram"},
    "youtube": {"uz": "YouTube", "ru": "YouTube", "en": "YouTube"},
    "instagram": {"uz": "Instagram", "ru": "Instagram", "en": "Instagram"},
    "facebook": {"uz": "Facebook", "ru": "Facebook", "en": "Facebook"},
}

OPEN_LINK_KEYS = {
    "telegram": "btn_open_telegram",
    "youtube": "btn_open_youtube",
    "instagram": "btn_open_instagram",
    "facebook": "btn_open_facebook",
}


def normalize_lang(value: str | None) -> str:
    code = (value or "").strip().lower().split("-", 1)[0]
    return code if code in SUPPORTED_LANGS else DEFAULT_LANG


def t(key: str, lang: str | None = None, **kwargs: Any) -> str:
    lang = normalize_lang(lang)
    table = _STRINGS.get(key) or {}
    text = table.get(lang) or table.get(DEFAULT_LANG) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def platform_label(platform: str | None, lang: str | None = None) -> str:
    lang = normalize_lang(lang)
    key = (platform or "").lower()
    row = PLATFORM_LABELS.get(key)
    if not row:
        return platform or "?"
    return row.get(lang) or row.get(DEFAULT_LANG) or key


def open_link_label(platform: str | None, lang: str | None = None) -> str:
    key = OPEN_LINK_KEYS.get((platform or "").lower(), "btn_open_comment")
    return t(key, lang)


def lang_display_name(lang: str | None) -> str:
    code = normalize_lang(lang)
    return {"uz": "O'zbekcha", "ru": "Русский", "en": "English"}[code]
