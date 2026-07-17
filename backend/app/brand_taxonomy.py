from __future__ import annotations

import re
from typing import Any


def _items(value: str) -> list[str]:
    return [item.strip() for item in value.split("|") if item.strip()]


CATEGORY_SEEDS = [
    ("aerospace_aviation", "Aerospace va aviatsiya", "Aeroport xizmati|Aviakompaniya|Aviatsiya servisi|Dron operatori|Havo yuk tashuvi|Uchuvchilar ta'limi", "regulated", "aviatsiya|parvoz|aeroport|bilet|havo transporti", "reys bekor qilindi|kechikish|bagaj|xavfsizlik|refund"),
    ("agriculture_agritech", "Agro va AgriTech", "Dehqonchilik|Fermer xo'jaligi|Issiqxona|Qishloq xo'jaligi texnikasi|Sug'orish tizimlari|Urug'chilik va seleksiya", "product", "hosil|fermer|agrotexnologiya|sug'orish|urug'", "qurg'oqchilik|hosil yo'qotilishi|kasallik|suv tanqisligi"),
    ("automotive_mobility", "Avtomobil va mobilitet", "Avtosalon|Avtoservis|Avto ehtiyot qismlar|Elektromobil|Korporativ avtopark|Taksi va ride-hailing", "mixed", "avtomobil|servis|ehtiyot qism|elektromobil|transport", "avariya|nosozlik|kafolat|kechikish|xavfsizlik"),
    ("beauty_cosmetics", "Beauty va kosmetika", "Barbershop|Go'zallik saloni|Kosmetika brendi|Kosmetologiya|Parfyumeriya|Spa va wellness", "service", "go'zallik|parvarish|kosmetika|natija|xizmat", "allergiya|asorat|gigiyena|sifatsiz|natija bermadi"),
    ("consumer_electronics", "Elektronika va maishiy texnika", "Audio va video texnika|Kompyuter va noutbuk|Maishiy texnika|Mobil qurilmalar|Smart home|Texnika servisi", "product", "texnika|qurilma|kafolat|model|servis", "nosozlik|qizib ketish|kafolat rad etildi|soxta|ta'mir"),
    ("customer_experience", "Customer experience va support", "Call-markaz|Customer success|Helpdesk platformasi|Kontakt markazi|Outsourced support|Service quality", "service", "mijoz tajribasi|support|murojaat|javob|xizmat sifati", "javob bermadi|qo'pol muomala|yechilmadi|uzoq kutish|eskalatsiya"),
    ("cybersecurity", "Cybersecurity", "Application security|Cloud security|Identity security|Kiberkonsalting|Security operations center|Threat intelligence", "regulated", "kiberxavfsizlik|himoya|zaiflik|SOC|xavf", "hujum|ma'lumot sizishi|ransomware|phishing|zaiflik"),
    ("data_analytics", "Data va analytics", "Data engineering|Data platformasi|Machine learning|Marketing analytics|Product analytics|Statistik tadqiqot", "platform", "data|analitika|hisobot|model|insight", "noto'g'ri ma'lumot|privacy|bias|integratsiya|hisobot xatosi"),
    ("energy_utilities", "Energetika va kommunal xizmatlar", "Elektr energiyasi|Gaz ta'minoti|Issiqlik ta'minoti|Qayta tiklanuvchi energiya|Suv ta'minoti|Utility billing", "public", "energiya|ta'minot|hisoblagich|tarif|uzilish", "avariya|uzilish|qarzdorlik|noto'g'ri hisob|tanqislik"),
    ("entertainment_gaming", "Entertainment va gaming", "Event va konsert|Film va serial|Gaming studio|Ko'ngilochar markaz|Musiqa platformasi|Streaming xizmati", "media", "kontent|o'yin|event|streaming|obuna", "mualliflik huquqi|bekor qilindi|toxicity|to'lov|yosh cheklovi"),
    ("event_exhibition", "Event va ko'rgazmalar", "Biznes konferensiya|Expo va ko'rgazma|Festival|Korporativ event|Sport tadbiri|To'y va marosim", "service", "tadbir|event|chipta|ishtirokchi|dastur", "bekor qilindi|navbat|tashkiliy xato|refund|xavfsizlik"),
    ("family_childcare", "Family va childcare", "Bolalar bog'chasi|Bolalar markazi|Enaga xizmati|Ota-onalar platformasi|Rivojlantirish markazi|Yozgi lager", "service", "bola|ota-ona|tarbiya|rivojlanish|xavfsizlik", "bola xavfsizligi|nazoratsiz|gigiyena|to'lov|shikoyat"),
    ("ecommerce_marketplace", "E-commerce va marketplace", "B2B marketplace|D2C internet do'kon|Mahalliy marketplace|Onlayn supermarket|Seller platformasi|Social commerce", "platform", "buyurtma|seller|marketplace|yetkazish|qaytarish", "kelmadi|refund|soxta tovar|seller firibgarligi|cancel"),
    ("finance_fintech", "Finance va FinTech", "Bank|Billing va invoicing|Investitsiya platformasi|Kredit va mikroqarz|Sug'urta|To'lov tizimi", "regulated", "to'lov|karta|kredit|komissiya|xavfsizlik", "fraud|pul yechildi|bloklandi|ma'lumot sizishi|komissiya"),
    ("food_hospitality", "Food va hospitality", "Catering|Fast food|Kafe|Mehmonxona|Oziq-ovqat ishlab chiqarish|Restoran", "mixed", "ta'm|xizmat|bron|yetkazish|tozalik", "zaharlanish|iflos|kechikdi|sovuq|bron bekor qilindi"),
    ("furniture_interior", "Furniture va interyer", "Dekor brendi|Interyer dizayni|Mebel ishlab chiqarish|Ofis mebeli|Oshxona mebeli|Uy jihozlari", "product", "mebel|interyer|dizayn|o'lchov|yetkazish", "defekt|noto'g'ri o'lcham|kechikdi|montaj|material sifati"),
    ("government_public", "Government va public sector", "Davlat agentligi|Davlat xizmatlari markazi|Hokimlik|Jamoat transporti boshqaruvi|Kommunal boshqaruv|Raqamli davlat xizmati", "public", "davlat xizmati|murojaat|navbat|ariza|ochiqlik", "korrupsiya|navbat|rad etildi|uzilish|shaffoflik"),
    ("healthcare_medtech", "Healthcare va MedTech", "Diagnostika markazi|Klinika|Laboratoriya|MedTech platformasi|Stomatologiya|Telemeditsina", "health", "qabul|shifokor|diagnostika|davolash|navbat", "asorat|noto'g'ri tashxis|maxfiylik|navbat|litsenziya"),
    ("home_personal_services", "Home va personal services", "Cleaning xizmati|Kuryerlik xizmati|Maishiy ta'mirlash|Shaxsiy yordamchi|Tikuvchilik xizmati|Uy ustasi", "service", "usta|xizmat|buyurtma|sifat|vaqt", "zarar yetkazildi|kechikdi|narx oshdi|kelmadi|sifatsiz"),
    ("hr_recruitment", "HR va recruitment", "HR avtomatizatsiya|Kadrlar agentligi|Korporativ trening|Payroll xizmati|Recruitment platformasi|Talant boshqaruvi", "service", "vakansiya|nomzod|xodim|recruitment|trening", "diskriminatsiya|maosh kechikdi|maxfiylik|aldov vakansiya|ishdan bo'shatish"),
    ("industrial_manufacturing", "Industrial va manufacturing", "Avtomatlashtirish|Kimyo ishlab chiqarish|Mashinasozlik|Qadoqlash|Qurilish materiallari|Yengil sanoat", "product", "ishlab chiqarish|zavod|sifat|uskunalar|ta'minot", "avariya|brak|yetkazib berish uzilishi|mehnat xavfsizligi|sertifikat"),
    ("jewelry_luxury", "Jewelry va luxury", "Aksessuar brendi|Luxury retail|Premium sovg'a|Qimmatbaho toshlar|Soat brendi|Zargarlik uyi", "product", "zargarlik|premium|original|dizayn|kolleksiya", "soxta|sertifikat|nuqson|o'g'irlik|kafolat"),
    ("language_localization", "Language va localization", "Interpretatsiya|Kontent lokalizatsiyasi|Subtitr xizmati|Tarjima agentligi|Terminologiya boshqaruvi|Til texnologiyasi", "service", "tarjima|lokalizatsiya|til|termin|subtitr", "noto'g'ri tarjima|maxfiylik|kechikdi|ma'no buzildi|sifat"),
    ("legal_compliance", "Legal va compliance", "Advokatlik byurosi|Audit va assurance|Compliance xizmati|Intellektual mulk|Notarial xizmat|Soliq konsaltingi", "service", "huquq|audit|shartnoma|compliance|soliq", "maxfiylik|manfaatlar to'qnashuvi|jarima|sud|noto'g'ri maslahat"),
    ("logistics_delivery", "Logistika va delivery", "Fulfillment|Kuryer delivery|Ombor logistika|Sovuq zanjir|Xalqaro logistika|Yuk tashish", "mixed", "yetkazish|ombor|tracking|logistika|kuryer", "yo'qoldi|shikastlandi|kechikdi|bojxona|noto'g'ri manzil"),
    ("marine_shipping", "Marine va shipping", "Dengiz ekspeditsiyasi|Kema agentligi|Konteyner tashuvi|Port operatori|Suv transporti|Yuk brokeri", "regulated", "kema|port|konteyner|shipping|yuk", "kechikish|zarar|bojxona|yo'qolgan yuk|xavfsizlik"),
    ("marketing_adtech", "Marketing va AdTech", "Digital agentlik|Influencer marketing|Media buying|PR agentlik|Reklama platformasi|Tadqiqot agentligi", "service", "kampaniya|reklama|reach|lead|konversiya", "fake trafik|brand safety|budget|noto'g'ri targeting|reputatsiya"),
    ("media_creator", "Media va creator economy", "Blog va nashr|Influencer|News media|Podcast|Production studio|YouTube kanal", "media", "kontent|auditoriya|obuna|ko'rish|hamkorlik", "fake news|plagiat|cancel|toxicity|yashirin reklama"),
    ("mining_metallurgy", "Mining va metallurgiya", "Konchilik|Metall qayta ishlash|Metall savdosi|Ruda boyitish|Sanoat xavfsizligi|Tog'-kon servisi", "regulated", "kon|metall|ruda|ishlab chiqarish|xomashyo", "avariya|ekologiya|mehnat xavfsizligi|ta'minot|ifloslanish"),
    ("nonprofit_social", "Nonprofit va ijtimoiy loyiha", "Ekologik loyiha|Fond|Hayriya platformasi|Ijtimoiy korxona|NNT|Volunteer community", "public", "ijtimoiy ta'sir|donation|volunteer|loyiha|hisobot", "mablag' shaffofligi|firibgarlik|hisobot|ishonch|suiiste'mol"),
    ("pet_veterinary", "Pet va veterinary", "Hayvonlar mehmonxonasi|Pet food|Pet shop|Veterinar klinika|Veterinar laboratoriya|Zooparvarish", "health", "hayvon|veterinar|parvarish|ozuqa|qabul", "allergiya|noto'g'ri davolash|gigiyena|sertifikat|asorat"),
    ("pharma_biotech", "Pharma va biotech", "Biotexnologiya|Dori distribyutsiyasi|Dori ishlab chiqarish|Dorixona|Klinik tadqiqot|Tibbiy buyumlar", "regulated", "dori|dorixona|tadqiqot|sertifikat|ta'minot", "qalbaki dori|nojo'ya ta'sir|retsept|litsenziya|ta'minot uzilishi"),
    ("professional_consulting", "Professional consulting", "Boshqaruv konsaltingi|Biznes jarayonlari|Eksport konsaltingi|Moliyaviy konsalting|Strategiya konsaltingi|Texnologik konsalting", "service", "konsalting|strategiya|jarayon|natija|ekspert", "manfaatlar to'qnashuvi|maxfiylik|va'da bajarilmadi|kechikish|natija yo'q"),
    ("printing_publishing", "Printing va publishing", "Book publishing|Digital publishing|Etiketka bosmasi|Qadoqlash bosmasi|Reklama poligrafiyasi|Tipografiya", "product", "nashr|bosma|kitob|dizayn|tiraj", "bosma xatosi|kechikdi|mualliflik huquqi|rang xatosi|tiraj"),
    ("procurement_sourcing", "Procurement va sourcing", "B2B sourcing|Davlat xaridlari|Import sourcing|Korporativ procurement|Tender platformasi|Vendor management", "platform", "xarid|tender|vendor|ta'minotchi|shartnoma", "korrupsiya|soxta tender|kechikish|narx oshishi|shaffoflik"),
    ("real_estate_construction", "Qurilish va ko'chmas mulk", "Arxitektura|Developer|Facility management|Ko'chmas mulk agentligi|Qurilish kompaniyasi|Uy-joy majmuasi", "mixed", "qurilish|uy-joy|obyekt|topshirish|ta'mir", "kechikdi|hujjat|sifat|kadastr|xavfsizlik"),
    ("recycling_waste", "Recycling va waste management", "Chiqindi logistika|Elektron chiqindi|Plastik qayta ishlash|Sanoat chiqindisi|Saralash xizmati|Zero-waste loyiha", "public", "chiqindi|qayta ishlash|saralash|ekologiya|tozalash", "ifloslanish|noqonuniy tashlash|hid|sanitariya|hisobot"),
    ("research_science", "Research va ilmiy xizmatlar", "Bozor tadqiqoti|Ilmiy laboratoriya|R&D markazi|Sotsiologik tadqiqot|Texnologiya transferi|Universitet tadqiqoti", "education", "tadqiqot|ilmiy|laboratoriya|metodologiya|natija", "soxta natija|bias|maxfiylik|plagiat|metodologiya xatosi"),
    ("robotics_drones", "Robotics va drones", "Dron ishlab chiqarish|Dron servisi|Industrial robot|Robototexnika ta'limi|Service robot|Warehouse robotics", "product", "robot|dron|avtomatizatsiya|sensor|boshqaruv", "nosozlik|xavfsizlik|ruxsatnoma|aloqa uzildi|avariya"),
    ("retail_fashion", "Retail va fashion", "Aksessuar|Bolalar kiyimi|Kundalik kiyim|Onlayn do'kon|Poyabzal|Sport kiyimlari", "product", "sifat|razmer|narx|original|chegirma", "soxta|defekt|qaytarish|mos kelmadi|kechikdi"),
    ("software_saas", "Software va SaaS", "AI mahsulot|API platforma|CRM va ERP|Dashboard va BI|Mobile app|Workflow automation", "platform", "demo|integratsiya|API|support|avtomatizatsiya", "bug|login|ma'lumot yo'qoldi|sekin|to'lov"),
    ("security_services", "Security services", "Event xavfsizligi|Kiber-fizik xavfsizlik|Qo'riqlash xizmati|Signalizatsiya|Videokuzatuv|Xavfsizlik konsaltingi", "regulated", "xavfsizlik|qo'riqlash|kamera|signalizatsiya|nazorat", "o'g'irlik|kamera ishlamadi|nazoratsiz|maxfiylik|hodisa"),
    ("semiconductor_hardware", "Semiconductor va hardware", "Chip dizayni|Embedded systems|Hardware distribyutsiyasi|Industrial sensor|PCB ishlab chiqarish|Prototiplash", "product", "chip|hardware|sensor|PCB|komponent", "defekt|ta'minot uzilishi|mos kelmadi|qizib ketish|sertifikat"),
    ("smart_city_urban", "Smart city va urban tech", "Aqlli parking|Jamoat xavfsizligi|Shahar analitikasi|Smart lighting|Transport boshqaruvi|Urban platforma", "public", "smart city|shahar|parking|transport|infratuzilma", "tizim ishlamadi|maxfiylik|uzilish|navbat|xavfsizlik"),
    ("space_geospatial", "Space va geospatial", "GIS platformasi|Kartografiya|Masofaviy zondlash|Navigatsiya xizmati|Sun'iy yo'ldosh ma'lumoti|Yer monitoringi", "platform", "GIS|xarita|geodata|navigatsiya|monitoring", "noto'g'ri koordinata|maxfiylik|ma'lumot eskirgan|signal yo'q|aniqlik"),
    ("sports_fitness", "Sport va fitness", "Fitness klub|Sport akademiyasi|Sport event|Sport federatsiyasi|Sport oziqlanishi|Sport texnologiyasi", "mixed", "mashg'ulot|sport|murabbiy|a'zolik|natija", "jarohat|bekor qilindi|doping|gigiyena|to'lov"),
    ("telecom_connectivity", "Telecom va connectivity", "Cloud communication|Internet provayder|IoT connectivity|Mobil operator|Satellite aloqa|VoIP xizmati", "regulated", "aloqa|internet|tarif|signal|tezlik", "uzilish|qoplama|sekinlik|billing|spam"),
    ("tourism_travel", "Tourism va travel", "Aviabilet servisi|Ichki turizm|Sayohat agentligi|Turoperator|Visa xizmati|Ziyorat turizmi", "service", "sayohat|tur|bron|bilet|mehmon", "reys bekor qilindi|refund|viza rad etildi|aldov|bron"),
    ("transport_mobility", "Transport va mobility", "Avtobus operatori|Mikromobilitet|Temir yo'l|Transport agregatori|Yuk transporti|Yo'lovchi tashish", "mixed", "transport|yo'nalish|chipta|haydovchi|jadval", "kechikish|avariya|bekor qilindi|xavfsizlik|narx"),
    ("education_edtech", "Ta'lim va EdTech", "Korporativ ta'lim|Maktab|O'quv markazi|Onlayn ta'lim|Universitet|Til markazi", "education", "dars|mentor|kurs|sertifikat|natija", "sifatsiz|pul qaytarish|va'da|bekor qilindi|natija yo'q"),
    ("wholesale_trade", "Wholesale va distribyutsiya", "B2B distribyutor|FMCG distribyutsiya|Importchi|Regional diler|Savdo uyi|Ulgurji marketplace", "mixed", "ulgurji|distribyutor|diler|ombor|yetkazish", "ta'minot uzilishi|soxta mahsulot|qarzdorlik|kechikish|narx"),
    ("workflow_operations", "Workflow va business operations", "Document workflow|Field service|Low-code platforma|Operations consulting|Process mining|Task management", "platform", "workflow|jarayon|vazifa|avtomatizatsiya|operatsiya", "integratsiya xatosi|data loss|sekinlik|support|uzilish"),
]


ACTIVITIES_BY_MODE = {
    "education": ["Akademik dastur", "Korporativ trening", "Mentorlik", "Onlayn kurs", "Sertifikatlash", "Ta'lim platformasi"],
    "health": ["Diagnostika", "Konsultatsiya", "Monitoring platformasi", "Profilaktika", "Sotuv va distribyutsiya", "Xizmat ko'rsatish"],
    "media": ["Content production", "Event va activation", "Litsenziyalash", "Obuna xizmati", "Reklama monetizatsiyasi", "Streaming yoki platforma"],
    "mixed": ["Distribyutsiya", "Ishlab chiqarish", "Konsalting", "Platforma yoki agregator", "Servis xizmati", "Ulgurji va chakana savdo"],
    "platform": ["API va integratsiya", "Enterprise yechim", "Marketplace", "Mobile mahsulot", "SaaS platforma", "White-label yechim"],
    "product": ["Chakana savdo", "Distribyutsiya", "Import va eksport", "Ishlab chiqarish", "Private label", "Ulgurji savdo"],
    "public": ["Aholiga xizmat", "B2G loyiha", "Infratuzilma boshqaruvi", "Jamoatchilik bilan aloqa", "Raqamli xizmat", "Tartibga solish"],
    "regulated": ["Agentlik va vositachilik", "B2B xizmat", "Compliance platformasi", "Korporativ mahsulot", "Retail mahsulot", "Risk boshqaruvi"],
    "service": ["Abonent xizmati", "Konsalting", "Managed service", "On-demand xizmat", "Premium xizmat", "Project-based xizmat"],
}


MODELS_BY_MODE = {
    "education": ["B2B korporativ", "B2C to'g'ridan-to'g'ri", "Freemium", "Litsenziya", "Obuna", "Pay-per-course"],
    "health": ["B2B klinik hamkorlik", "B2C xizmat", "B2G shartnoma", "Sug'urta orqali", "Obuna", "Pay-per-service"],
    "media": ["Advertising", "Creator partnership", "Freemium", "Litsenziya", "Obuna", "Sponsorship"],
    "mixed": ["B2B shartnoma", "B2C savdo", "Franshiza", "Komissiya", "Obuna", "Ulgurji distribyutsiya"],
    "platform": ["Enterprise license", "Freemium", "Marketplace commission", "SaaS obuna", "Transaction fee", "Usage-based"],
    "product": ["B2B distribyutsiya", "D2C", "Marketplace", "Private label", "Retail", "Ulgurji savdo"],
    "public": ["B2G kontrakt", "Davlat budjeti", "Grant", "PPP", "Tarif asosida", "Xizmat yig'imi"],
    "regulated": ["B2B kontrakt", "B2C retail", "Komissiya", "Litsenziya", "Premium", "Transaction fee"],
    "service": ["B2B retainer", "B2C xizmat", "Franshiza", "Loyiha to'lovi", "Obuna", "Soatbay to'lov"],
}


AUDIENCE_GROUPS = {
    "business": ["Kichik biznes", "Korporativ mijozlar", "Mahalliy hamkorlar", "Professional mutaxassislar", "Startaplar", "Xalqaro kompaniyalar"],
    "consumer": ["18–24 yosh", "25–34 yosh", "35–44 yosh", "45+ auditoriya", "Oilalar", "Premium xaridorlar", "Talabalar", "Yosh ota-onalar"],
    "public": ["Davlat tashkilotlari", "Fuqarolar", "Mahalliy hamjamiyat", "NNT va fondlar", "Regulyatorlar", "Ta'lim muassasalari"],
    "professional": ["Agentliklar", "Ekspert va konsultantlar", "Freelancerlar", "Klinikalar", "O'qituvchilar", "Savdo vakillari", "Texnik jamoalar"],
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _audience_groups_for(model: str) -> list[str]:
    lowered = model.casefold()
    groups: list[str] = []
    if any(token in lowered for token in ("b2b", "enterprise", "ulgurji", "distribyutsiya", "korporativ", "retainer")):
        groups.append("business")
    if any(token in lowered for token in ("b2c", "d2c", "retail", "freemium", "obuna", "course", "service")):
        groups.append("consumer")
    if any(token in lowered for token in ("b2g", "davlat", "grant", "ppp", "tarif")):
        groups.append("public")
    if any(token in lowered for token in ("license", "litsenziya", "hamkorlik", "sug'urta", "creator")):
        groups.append("professional")
    return groups or ["business", "consumer"]


def build_brand_taxonomy(base: dict[str, Any]) -> dict[str, Any]:
    categories: list[dict[str, Any]] = []
    total_internal_directions = 0
    for key, label, branches, mode, keywords, risk_keywords in CATEGORY_SEEDS:
        activity_rows = [
            {
                "key": _slug(activity),
                "value": activity,
                "label": activity,
                "business_models": [
                    {
                        "key": _slug(model),
                        "value": model,
                        "label": model,
                        "audience_groups": _audience_groups_for(model),
                    }
                    for model in sorted(MODELS_BY_MODE[mode], key=str.casefold)
                ],
            }
            for activity in sorted(ACTIVITIES_BY_MODE[mode], key=str.casefold)
        ]
        children = [
            {
                "key": _slug(branch),
                "value": branch,
                "label": branch,
                "activities": activity_rows,
            }
            for branch in sorted(_items(branches), key=str.casefold)
        ]
        total_internal_directions += len(children)
        categories.append(
            {
                "key": key,
                "value": label,
                "label": label,
                "children": children,
                "keywords": _items(keywords),
                "risk_keywords": _items(risk_keywords),
            }
        )

    return {
        "categories": sorted(categories, key=lambda item: item["label"].casefold()),
        "audience_groups": AUDIENCE_GROUPS,
        "goals": base.get("goals", []),
        "source_playbooks": base.get("source_playbooks", {}),
        "meta": {
            "primary_categories": len(categories),
            "internal_directions": total_internal_directions,
            "searchable": True,
            "version": 2,
        },
    }
