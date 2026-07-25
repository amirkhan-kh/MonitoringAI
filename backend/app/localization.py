from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from fastapi import Request


SUPPORTED_LANGUAGES = {"uz", "ru", "en"}


def _load_catalog_translations() -> dict[str, dict[str, str]]:
    path = Path(__file__).with_name("catalog_translations.json")
    if not path.exists():
        return {"en": {}, "ru": {}}
    return json.loads(path.read_text(encoding="utf-8"))


CATALOG_TRANSLATIONS = _load_catalog_translations()


MAIN_CATEGORY_TRANSLATIONS = {
    "en": {
        "Aerospace va aviatsiya": "Aerospace and aviation",
        "Agro va AgriTech": "Agriculture and AgriTech",
        "Avtomobil va mobilitet": "Automotive and mobility",
        "Beauty va kosmetika": "Beauty and cosmetics",
        "Elektronika va maishiy texnika": "Electronics and home appliances",
        "Customer experience va support": "Customer experience and support",
        "Cybersecurity": "Cybersecurity",
        "Data va analytics": "Data and analytics",
        "Energetika va kommunal xizmatlar": "Energy and utilities",
        "Entertainment va gaming": "Entertainment and gaming",
        "Event va ko'rgazmalar": "Events and exhibitions",
        "Family va childcare": "Family and childcare",
        "E-commerce va marketplace": "E-commerce and marketplaces",
        "Finance va FinTech": "Finance and FinTech",
        "Food va hospitality": "Food and hospitality",
        "Furniture va interyer": "Furniture and interior design",
        "Government va public sector": "Government and public sector",
        "Healthcare va MedTech": "Healthcare and MedTech",
        "Home va personal services": "Home and personal services",
        "HR va recruitment": "HR and recruitment",
        "Industrial va manufacturing": "Industry and manufacturing",
        "Jewelry va luxury": "Jewelry and luxury",
        "Language va localization": "Language and localization",
        "Legal va compliance": "Legal and compliance",
        "Logistika va delivery": "Logistics and delivery",
        "Marine va shipping": "Marine and shipping",
        "Marketing va AdTech": "Marketing and AdTech",
        "Media va creator economy": "Media and creator economy",
        "Mining va metallurgiya": "Mining and metallurgy",
        "Nonprofit va ijtimoiy loyiha": "Nonprofit and social impact",
        "Pet va veterinary": "Pets and veterinary care",
        "Pharma va biotech": "Pharma and biotech",
        "Professional consulting": "Professional consulting",
        "Printing va publishing": "Printing and publishing",
        "Procurement va sourcing": "Procurement and sourcing",
        "Qurilish va ko'chmas mulk": "Construction and real estate",
        "Recycling va waste management": "Recycling and waste management",
        "Research va ilmiy xizmatlar": "Research and scientific services",
        "Robotics va drones": "Robotics and drones",
        "Retail va fashion": "Retail and fashion",
        "Software va SaaS": "Software and SaaS",
        "Security services": "Security services",
        "Semiconductor va hardware": "Semiconductors and hardware",
        "Smart city va urban tech": "Smart cities and urban tech",
        "Space va geospatial": "Space and geospatial",
        "Sport va fitness": "Sports and fitness",
        "Telecom va connectivity": "Telecom and connectivity",
        "Tourism va travel": "Tourism and travel",
        "Transport va mobility": "Transport and mobility",
        "Ta'lim va EdTech": "Education and EdTech",
        "Wholesale va distribyutsiya": "Wholesale and distribution",
        "Workflow va business operations": "Workflow and business operations",
    },
    "ru": {
        "Aerospace va aviatsiya": "Аэрокосмическая отрасль и авиация",
        "Agro va AgriTech": "Сельское хозяйство и AgriTech",
        "Avtomobil va mobilitet": "Автомобили и мобильность",
        "Beauty va kosmetika": "Красота и косметика",
        "Elektronika va maishiy texnika": "Электроника и бытовая техника",
        "Customer experience va support": "Клиентский опыт и поддержка",
        "Cybersecurity": "Кибербезопасность",
        "Data va analytics": "Данные и аналитика",
        "Energetika va kommunal xizmatlar": "Энергетика и коммунальные услуги",
        "Entertainment va gaming": "Развлечения и игры",
        "Event va ko'rgazmalar": "Мероприятия и выставки",
        "Family va childcare": "Семья и уход за детьми",
        "E-commerce va marketplace": "Электронная коммерция и маркетплейсы",
        "Finance va FinTech": "Финансы и FinTech",
        "Food va hospitality": "Питание и гостеприимство",
        "Furniture va interyer": "Мебель и интерьер",
        "Government va public sector": "Государственный сектор",
        "Healthcare va MedTech": "Здравоохранение и MedTech",
        "Home va personal services": "Бытовые и персональные услуги",
        "HR va recruitment": "HR и подбор персонала",
        "Industrial va manufacturing": "Промышленность и производство",
        "Jewelry va luxury": "Ювелирные изделия и люкс",
        "Language va localization": "Языки и локализация",
        "Legal va compliance": "Юридические услуги и комплаенс",
        "Logistika va delivery": "Логистика и доставка",
        "Marine va shipping": "Морские перевозки",
        "Marketing va AdTech": "Маркетинг и AdTech",
        "Media va creator economy": "Медиа и экономика авторов",
        "Mining va metallurgiya": "Горнодобывающая отрасль и металлургия",
        "Nonprofit va ijtimoiy loyiha": "Некоммерческие и социальные проекты",
        "Pet va veterinary": "Домашние животные и ветеринария",
        "Pharma va biotech": "Фармацевтика и биотехнологии",
        "Professional consulting": "Профессиональный консалтинг",
        "Printing va publishing": "Полиграфия и издательское дело",
        "Procurement va sourcing": "Закупки и снабжение",
        "Qurilish va ko'chmas mulk": "Строительство и недвижимость",
        "Recycling va waste management": "Переработка и управление отходами",
        "Research va ilmiy xizmatlar": "Исследования и научные услуги",
        "Robotics va drones": "Робототехника и дроны",
        "Retail va fashion": "Ритейл и мода",
        "Software va SaaS": "Программное обеспечение и SaaS",
        "Security services": "Услуги безопасности",
        "Semiconductor va hardware": "Полупроводники и оборудование",
        "Smart city va urban tech": "Умный город и городские технологии",
        "Space va geospatial": "Космос и геопространственные технологии",
        "Sport va fitness": "Спорт и фитнес",
        "Telecom va connectivity": "Телекоммуникации и связь",
        "Tourism va travel": "Туризм и путешествия",
        "Transport va mobility": "Транспорт и мобильность",
        "Ta'lim va EdTech": "Образование и EdTech",
        "Wholesale va distribyutsiya": "Оптовая торговля и дистрибуция",
        "Workflow va business operations": "Рабочие процессы и бизнес-операции",
    },
}


TEXT_TRANSLATIONS = {
    "en": {
        "Rasmiy kanallar": "Official channels",
        "Botlar": "Bots",
        "Raqobatchilar": "Competitors",
        "Yangiliklar": "News",
        "Yo'nalish": "Industry",
        "Influencerlar": "Influencers",
        "Chatlar": "Chats",
        "Foydali": "Useful sources",
        "Risk watch": "Risk watch",
        "Tasniflanmagan": "Unclassified",
        "Keyword watch": "Keyword watch",
        "Hashtaglar": "Hashtags",
        "Creatorlar": "Creators",
        "Kampaniyalar": "Campaigns",
        "Rasmiy akkaunt": "Official account",
        "Rasmiy sahifa": "Official page",
        "Raqobatchi": "Competitor",
        "Aniqlanmagan": "Unclassified",
        "Toifasiz.": "Uncategorized.",
        "Kuzatiladigan hashtag oqimi.": "Monitored hashtag feed.",
        "Bloger/ekspert akkauntlari.": "Blogger and expert accounts.",
        "Bloger/ekspert sahifalari.": "Blogger and expert pages.",
        "Raqobatchi sahifa.": "Competitor page.",
        "Raqobatchi akkaunt (mention/hashtag orqali).": "Competitor account monitored through mentions and hashtags.",
        "Brendning o'z Instagram Business akkaunti.": "The brand's own Instagram Business account.",
        "Brendning o'z Facebook Page'i.": "The brand's own Facebook Page.",
        "Clientning rasmiy kanal, group va linked discussion manbalari.": "The client's official channels, groups, and linked discussions.",
        "Rasmiy kanal, guruh va discussion.": "Official channels, groups, and discussions.",
        "Client botlari, monitoring botlari va bot orqali keladigan suhbatlar.": "Client bots, monitoring bots, and bot conversations.",
        "Client va monitoring botlari.": "Client and monitoring bots.",
        "Raqobatchi kompaniya, brend yoki loyiha kanallari.": "Channels of competitor companies, brands, or projects.",
        "Raqobatchi brend kanallari.": "Competitor brand channels.",
        "Media va yangilik kanallari.": "Media and news channels.",
        "Media va yangilik manbalari.": "Media and news sources.",
        "Soha, bozor va mavzu bo'yicha kanallar.": "Channels related to the industry, market, and topic.",
        "Soha va bozor kanallari.": "Industry and market channels.",
        "Bloger, ekspert va shaxsiy media manbalari.": "Blogger, expert, and personal media sources.",
        "Bloger va ekspertlar.": "Bloggers and experts.",
        "Public chat, forum va community guruhlar.": "Public chats, forums, and community groups.",
        "Community va forumlar.": "Communities and forums.",
        "Benchmark, hamkorlik yoki trend kuzatuvi uchun manbalar.": "Sources for benchmarking, partnerships, or trend tracking.",
        "Benchmark va trend manbalari.": "Benchmark and trend sources.",
        "Shikoyat, krizis, salbiy signal yoki reputatsiya xavfi yuqori manbalar.": "Sources with complaints, crises, negative signals, or high reputational risk.",
        "Shikoyat va krizis manbalari.": "Complaint and crisis sources.",
        "Hali tartibga solinmagan source.": "A source that has not been classified yet.",
        "Tartiblanmagan source.": "Unclassified source.",
        "Clientning rasmiy YouTube kanali, Shorts va video comment oqimi.": "The client's official YouTube channel, Shorts, and video comments.",
        "Raqobatchi channel, video va content signallari.": "Competitor channel, video, and content signals.",
        "Brand nomi, mahsulot, muammo yoki bozor so'zlari bo'yicha YouTube search.": "YouTube search for brand, product, issue, or market terms.",
        "Hashtag yoki kampaniya taglari ostidagi video va commentlar.": "Videos and comments under hashtag or campaign tags.",
        "Bloger, sharhlovchi va creator kanallari.": "Blogger, reviewer, and creator channels.",
        "Reklama, launch, promo va event kampaniyalari.": "Advertising, launch, promotion, and event campaigns.",
        "Salbiy signal, shikoyat, crisis va brand safety kuzatuvi.": "Negative-signal, complaint, crisis, and brand-safety monitoring.",
        "Hali tartibga solinmagan YouTube source.": "A YouTube source that has not been classified yet.",
        "O'z profilimdagi post/commentlarni kuzatish": "Monitor posts and comments on owned profiles",
        "Raqobatchilarni kuzatish": "Monitor competitors",
        "Internet bo'ylab brand zikrlarini topish": "Find brand mentions across the internet",
        "Salbiy signal va crisis alert": "Negative-signal and crisis alerts",
        "Kampaniya/hashtag natijasini kuzatish": "Track campaign and hashtag performance",
        "Support va javob berish uchun mention ajratish": "Prioritize mentions that need support or a response",
        "YouTube Data API commentThreads orqali public video commentlarini olish mumkin.": "Public video comments can be collected through YouTube Data API commentThreads.",
        "Transcript/audio AI keyingi bosqichda alohida pipeline bo'ladi.": "Transcript and audio AI will use a separate pipeline in the next phase.",
    },
    "ru": {
        "Rasmiy kanallar": "Официальные каналы",
        "Botlar": "Боты",
        "Raqobatchilar": "Конкуренты",
        "Yangiliklar": "Новости",
        "Yo'nalish": "Отрасль",
        "Influencerlar": "Инфлюенсеры",
        "Chatlar": "Чаты",
        "Foydali": "Полезные источники",
        "Risk watch": "Мониторинг рисков",
        "Tasniflanmagan": "Без категории",
        "Keyword watch": "Мониторинг ключевых слов",
        "Hashtaglar": "Хэштеги",
        "Creatorlar": "Авторы",
        "Kampaniyalar": "Кампании",
        "Rasmiy akkaunt": "Официальный аккаунт",
        "Rasmiy sahifa": "Официальная страница",
        "Raqobatchi": "Конкурент",
        "Aniqlanmagan": "Не определено",
        "Toifasiz.": "Без категории.",
        "Kuzatiladigan hashtag oqimi.": "Отслеживаемая лента хэштега.",
        "Bloger/ekspert akkauntlari.": "Аккаунты блогеров и экспертов.",
        "Bloger/ekspert sahifalari.": "Страницы блогеров и экспертов.",
        "Raqobatchi sahifa.": "Страница конкурента.",
        "Raqobatchi akkaunt (mention/hashtag orqali).": "Аккаунт конкурента, отслеживаемый по упоминаниям и хэштегам.",
        "Brendning o'z Instagram Business akkaunti.": "Собственный аккаунт бренда Instagram Business.",
        "Brendning o'z Facebook Page'i.": "Собственная Facebook Page бренда.",
        "Clientning rasmiy kanal, group va linked discussion manbalari.": "Официальные каналы, группы и связанные обсуждения клиента.",
        "Client botlari, monitoring botlari va bot orqali keladigan suhbatlar.": "Боты клиента, боты мониторинга и диалоги через ботов.",
        "Raqobatchi kompaniya, brend yoki loyiha kanallari.": "Каналы компаний, брендов и проектов конкурентов.",
        "Media va yangilik kanallari.": "Медиа и новостные каналы.",
        "Soha, bozor va mavzu bo'yicha kanallar.": "Каналы по отрасли, рынку и тематике.",
        "Bloger, ekspert va shaxsiy media manbalari.": "Источники блогеров, экспертов и персональных медиа.",
        "Public chat, forum va community guruhlar.": "Публичные чаты, форумы и сообщества.",
        "Benchmark, hamkorlik yoki trend kuzatuvi uchun manbalar.": "Источники для бенчмаркинга, партнёрств и отслеживания трендов.",
        "Shikoyat, krizis, salbiy signal yoki reputatsiya xavfi yuqori manbalar.": "Источники с жалобами, кризисами, негативными сигналами или высоким репутационным риском.",
        "Hali tartibga solinmagan source.": "Источник, который ещё не классифицирован.",
        "Clientning rasmiy YouTube kanali, Shorts va video comment oqimi.": "Официальный YouTube-канал клиента, Shorts и комментарии к видео.",
        "Raqobatchi channel, video va content signallari.": "Сигналы каналов, видео и контента конкурентов.",
        "Brand nomi, mahsulot, muammo yoki bozor so'zlari bo'yicha YouTube search.": "Поиск YouTube по названию бренда, продукту, проблеме или рыночным терминам.",
        "Hashtag yoki kampaniya taglari ostidagi video va commentlar.": "Видео и комментарии по хэштегам и тегам кампаний.",
        "Bloger, sharhlovchi va creator kanallari.": "Каналы блогеров, обозревателей и авторов.",
        "Reklama, launch, promo va event kampaniyalari.": "Рекламные, запусковые, промо- и event-кампании.",
        "Salbiy signal, shikoyat, crisis va brand safety kuzatuvi.": "Мониторинг негативных сигналов, жалоб, кризисов и безопасности бренда.",
        "Hali tartibga solinmagan YouTube source.": "Источник YouTube, который ещё не классифицирован.",
        "O'z profilimdagi post/commentlarni kuzatish": "Отслеживать публикации и комментарии собственных профилей",
        "Raqobatchilarni kuzatish": "Отслеживать конкурентов",
        "Internet bo'ylab brand zikrlarini topish": "Находить упоминания бренда в интернете",
        "Salbiy signal va crisis alert": "Оповещения о негативных сигналах и кризисах",
        "Kampaniya/hashtag natijasini kuzatish": "Отслеживать результаты кампаний и хэштегов",
        "Support va javob berish uchun mention ajratish": "Выделять упоминания для поддержки и ответа",
        "YouTube Data API commentThreads orqali public video commentlarini olish mumkin.": "Публичные комментарии к видео можно получать через YouTube Data API commentThreads.",
        "Transcript/audio AI keyingi bosqichda alohida pipeline bo'ladi.": "Для расшифровки и аудио ИИ на следующем этапе будет отдельный конвейер.",
    },
}


CATALOG_REPLACEMENTS = {
    "en": {
        "Qishloq xo'jaligi": "Agricultural",
        "ishlab chiqarish": "manufacturing",
        "qayta ishlash": "processing",
        "boshqaruvi": "management",
        "ta'minoti": "supply",
        "xavfsizligi": "security",
        "xizmati": "service",
        "markazi": "center",
        "platformasi": "platform",
        "agentligi": "agency",
        "kompaniyasi": "company",
        "laboratoriya": "laboratory",
        "tadqiqot": "research",
        "konsaltingi": "consulting",
        "distribyutsiyasi": "distribution",
        "savdosi": "sales",
        "ta'limi": "education",
        "texnologiyasi": "technology",
        "operatori": "operator",
        "brendi": "brand",
        "tizimlari": "systems",
        "xizmat": "service",
        "mahsulot": "product",
        "savdo": "sales",
        "uy": "home",
        "davlat": "government",
        "shahar": "city",
        "raqamli": "digital",
        "xalqaro": "international",
        "korporativ": "corporate",
        "moliyaviy": "financial",
        "tibbiy": "medical",
        "bolalar": "children's",
        "oziq-ovqat": "food",
        "va": "and",
        "yoki": "or",
    },
    "ru": {
        "Qishloq xo'jaligi": "Сельскохозяйственный",
        "ishlab chiqarish": "производство",
        "qayta ishlash": "переработка",
        "boshqaruvi": "управление",
        "ta'minoti": "снабжение",
        "xavfsizligi": "безопасность",
        "xizmati": "услуга",
        "markazi": "центр",
        "platformasi": "платформа",
        "agentligi": "агентство",
        "kompaniyasi": "компания",
        "laboratoriya": "лаборатория",
        "tadqiqot": "исследование",
        "konsaltingi": "консалтинг",
        "distribyutsiyasi": "дистрибуция",
        "savdosi": "продажи",
        "ta'limi": "обучение",
        "texnologiyasi": "технология",
        "operatori": "оператор",
        "brendi": "бренд",
        "tizimlari": "системы",
        "xizmat": "услуга",
        "mahsulot": "продукт",
        "savdo": "торговля",
        "davlat": "государственный",
        "shahar": "городской",
        "raqamli": "цифровой",
        "xalqaro": "международный",
        "korporativ": "корпоративный",
        "moliyaviy": "финансовый",
        "tibbiy": "медицинский",
        "bolalar": "детский",
        "oziq-ovqat": "продукты питания",
        "va": "и",
        "yoki": "или",
    },
}


def request_language(request: Request) -> str:
    value = request.headers.get("accept-language", "uz").split(",", 1)[0].split("-", 1)[0].lower().strip()
    return value if value in SUPPORTED_LANGUAGES else "uz"


def translate_text(value: str, language: str) -> str:
    if language == "uz" or not value:
        return value
    exact = MAIN_CATEGORY_TRANSLATIONS.get(language, {}).get(value)
    if exact:
        return exact
    exact = TEXT_TRANSLATIONS.get(language, {}).get(value)
    if exact:
        return exact
    exact = CATALOG_TRANSLATIONS.get(language, {}).get(value)
    if exact:
        return exact
    translated = value
    for source, target in sorted(CATALOG_REPLACEMENTS.get(language, {}).items(), key=lambda row: len(row[0]), reverse=True):
        translated = translated.replace(source, target)
    return translated


def localize_source_categories(rows: list[dict[str, Any]], language: str) -> list[dict[str, Any]]:
    localized = deepcopy(rows)
    for row in localized:
        row["label"] = translate_text(str(row.get("label") or ""), language)
        row["description"] = translate_text(str(row.get("description") or ""), language)
    return sorted(localized, key=lambda row: str(row.get("label") or "").casefold())


def _localize_catalog_row(row: dict[str, Any], language: str) -> dict[str, Any]:
    localized = deepcopy(row)
    original_label = str(localized.get("value") or localized.get("label") or localized.get("key") or "")
    localized["value"] = original_label
    localized["label"] = translate_text(str(localized.get("label") or original_label), language)
    if "children" in localized:
        localized["children"] = sorted(
            (_localize_catalog_row(item, language) for item in localized["children"]),
            key=lambda item: str(item.get("label") or "").casefold(),
        )
    if "activities" in localized:
        localized["activities"] = sorted(
            (_localize_catalog_row(item, language) for item in localized["activities"]),
            key=lambda item: str(item.get("label") or "").casefold(),
        )
    if "business_models" in localized:
        localized["business_models"] = sorted(
            (_localize_catalog_row(item, language) for item in localized["business_models"]),
            key=lambda item: str(item.get("label") or "").casefold(),
        )
    return localized


def localize_taxonomy(taxonomy: dict[str, Any], language: str) -> dict[str, Any]:
    localized = deepcopy(taxonomy)
    localized["categories"] = sorted(
        (_localize_catalog_row(item, language) for item in taxonomy.get("categories", [])),
        key=lambda item: str(item.get("label") or "").casefold(),
    )
    localized["audience_groups"] = {
        key: [
            {"value": item, "label": translate_text(item, language)}
            for item in values
        ]
        for key, values in taxonomy.get("audience_groups", {}).items()
    }
    for goal in localized.get("goals", []):
        goal["label"] = translate_text(str(goal.get("label") or ""), language)
    localized["source_playbooks"] = {
        platform: [translate_text(item, language) for item in steps]
        for platform, steps in taxonomy.get("source_playbooks", {}).items()
    }
    localized.setdefault("meta", {})["language"] = language
    return localized


def localize_strings(values: list[str], language: str) -> list[str]:
    return [translate_text(value, language) for value in values]
