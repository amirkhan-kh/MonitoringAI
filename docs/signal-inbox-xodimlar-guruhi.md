# Signal inbox: xodimlar guruhida hech bir mijoz javobsiz qolmaydi

AI tahlildan o'tgan har bir riskli mijoz izohi xodimlar Telegram guruhiga **tugmali
kartochka** bo'lib tushadi. Kartochka ostidagi tugmalar orqali guruh ikkita savolga
javob beradi: **kim tekshirdi** va **kim mijozga javob berdi**. Guruhda pin qilingan
xabar esa **hali javob berilmagan signallar sonini** ko'rsatib turadi.

Dashboarddagi *Signal inbox* paneli — shu ishning aynan o'zi, faqat brauzerda.
Ikkalasi bitta yozuvni yangilaydi: guruhda tugma bossangiz dashboardda ko'rinadi,
dashboardda bossangiz Telegramdagi kartochka o'zgaradi.

## Kartochka qanday ko'rinadi

```
🟠 Reputatsion xavf signali — Telegram
Brend: Uzum market
Manba: Официальный чат Uzum Market
Muallif: Dildora
Risk: high (0.8)
Kayfiyat: negative (-0.6)
Matn / Xulosa / Tavsiya ...

📌 Holat: 🆕 Yangi — hali olinmagan
[ 🔍 Tekshirdim ] [ 💬 Javob berdim ]
[ 🔗 Havola orqali ochish          ]   ← holatni «Tekshirilyapti» qiladi
[ 🌐 Telegram izohiga o'tish       ]   ← platformadagi komment deep-link
```

- **🔍 Tekshirdim** — AI xulosasi o'qildi / ish olingan. Ikkinchi marta bossangiz belgi
  olinadi (faqat o'zingiznikini). Boshqa xodim tekshirgan bo'lsa, bot uning ismini aytadi.
- **💬 Javob berdim** — mijozga javob berildi, signal yopiladi. Kartochkada javob bergan
  xodimning **ismi + @username** va javob vaqti yoziladi.
- **🔗 Havola orqali ochish** — holatni `Tekshirilyapti…` qiladi (kim olgani yoziladi),
  so'ng pastagi platforma havolasidan kommentga o'tasiz.
- **🌐 … izohiga / kommentiga o'tish** — Telegram / YouTube / Instagram / Facebookdagi
  original kommentga deep-link (javob yozish oynasiga yaqin joyga tushadi).
- Yopilgan kartochkada **↩️ Qayta ochish** tugmasi qoladi — noto'g'ri yopilsa qaytariladi.

### Holatlar (professional oqim)

| Holat | Matn | Qachon |
| --- | --- | --- |
| Yangi | `🆕 Yangi — hali olinmagan` | Hali hech kim bosmagan |
| Tekshirilyapti | `👀 Tekshirilyapti…` + xodim ismi | Havola orqali ochish yoki Tekshirdim |
| Javob berildi | `✅ Javob berildi` + `👤 Javob bergan xodim: Ism (@user)` | Javob berdim |

Ikki xodim bir vaqtda bosса, birinchisi yozib qoladi, ikkinchisiga "falonchi
allaqachon javob bergan" deb chiqadi (yozuv DB'da qulflab yangilanadi).

## Javobsiz signallar hisoblagichi

Bot guruhga **pin qilingan** xabar qo'yadi va har o'zgarishda yangilaydi:

```
📌 Javob kutayotgan signallar: 12
🔴 critical 2 · 🟠 high 5 · 🟡 medium 5
⏳ Eng eskisi: 3 soat 12 daq kutmoqda
👀 Tekshirilgan, javob kutmoqda: 4

Manbalar bo'yicha:
• Официальный чат Uzum Market — 7
• Uzum Market — 3

Bugun yopildi: 18 · O'rtacha javob vaqti: 22 daq
Xodimlar: Aziz 7 · Dildora 6
🌐 O'zbekcha

[ 🔄 Yangilash ] [ 📋 Ochiq ro'yxat ]
[ 👥 Xodimlar jadvali ] [ 🌐 Til ]
```

- **👥 Xodimlar jadvali** — bugun kim nechta kommentga javob berganini jadval qilib chiqaradi.
- **🌐 Til** — guruh bot tilini `uz` / `ru` / `en` ga o'zgartirish (dinamik).

Hammasi yopilsa: `✅ Javobsiz signal yo'q — hammasi yopilgan`.

## SLA eslatmasi

`ALERT_SLA_MINUTES` (default 30 daqiqa) ichida javob berilmagan signalga bot
kartochkaning o'ziga **reply** qilib eslatadi. Takrorlanishi
`ALERT_REMINDER_REPEAT_MINUTES` (60 daq), maksimal `ALERT_REMINDER_MAX` (3 marta) —
guruh spamga aylanmasligi uchun cheklangan. `ALERT_SLA_MINUTES=0` — eslatma o'chadi.

## Guruh komandalar (bot admin bo'lishi kerak)

| Komanda | Nima qiladi |
| --- | --- |
| `/id` | Guruh chat id — `ALERT_TELEGRAM_CHAT_ID` yoki brand `profile_config.alert_chat_id` |
| `/ochiq` | Javob kutayotgan signallar ro'yxati (link bilan) |
| `/statistika` | Bugungi yopilganlar, o'rtacha javob vaqti, xodimlar kesimi |
| `/xodimlar` | Kim nechta signalga javob bergani (jadval) |
| `/til uz\|ru\|en` | Guruh bot tilini dinamik o'zgartirish |
| `/jamlanma` | Pin qilingan hisoblagichni majburiy yangilash |

## Multi-platform + brand bot

AI tahlildan o'tgan **Telegram, YouTube, Instagram, Facebook** risk signallari bir xil
kartochka sifatida xodimlar guruhiga tushadi. Yetkazish tartibi:

1. Brand dashboardda ulangan bot tokeni (Telegram setup) — bor bo'lsa shu bot yuboradi.
2. Aks holda global `TELEGRAM_BOT_TOKEN`.
3. Guruh chat id: brand `profile_config.alert_chat_id` (ixtiyoriy) → aks holda
   `ALERT_TELEGRAM_CHAT_ID`.

Deep-link har platformada o'z formatida: `t.me/...`, YouTube `watch?v=&lc=`, Instagram
media permalink, Facebook `permalink_url`.

## Sozlash: 4 qadam

1. Botni xodimlar guruhiga qo'shing va **admin** qiling (pin qilish uchun kerak).
2. Guruhda `/id` yozing → chiqqan manfiy raqamni ko'chirib oling (masalan `-1001234567890`).
3. `.env` faylida `ALERT_TELEGRAM_CHAT_ID` ni shu raqamga almashtiring.
4. Servislarni qayta ishga tushiring:
   ```bash
   docker compose up -d --build api telegram-worker alert-worker
   ```

`TELEGRAM_ALLOWED_UPDATES` ichida `callback_query` bo'lishi kerak — bo'lmasa ham
telegram-worker uni o'zi qo'shadi, lekin `.env` da yozib qo'yish tozaroq.

## Sozlamalar

| Env | Default | Ma'nosi |
| --- | --- | --- |
| `ALERT_TELEGRAM_CHAT_ID` | — | Xodimlar guruhi chat id |
| `ALERT_SLA_MINUTES` | 30 | Necha daqiqadan keyin eslatilsin (0 = o'chiq) |
| `ALERT_REMINDER_REPEAT_MINUTES` | 60 | Eslatma takrorlanish oralig'i |
| `ALERT_REMINDER_MAX` | 3 | Bitta signalga maksimal eslatma |
| `ALERT_SUMMARY_ENABLED` | true | Pin qilingan hisoblagich |
| `ALERT_SUMMARY_REFRESH_SECONDS` | 300 | Hisoblagichni yangilash minimal oraliq |

## Texnik eslatma

- Holat `alert_events` jadvalida: `work_status` (`open` → `checked` → `answered`),
  `checked_by/checked_at`, `answered_by/answered_at`, `telegram_chat_id/message_id`.
- `status` (pending/sent/failed) — bu **yetkazish**, `work_status` — **ish jarayoni**.
  Ikkalasi alohida.
- Bu funksiya kiritilishidan oldin yuborilgan signallar `work_status='archived'` qilinadi:
  ularda tugma yo'q, shuning uchun hisoblagichni yopib bo'lmaydigan qarz bilan
  boshlamasligi uchun.
- API: `GET /alerts/summary`, `GET /alerts/events?work_status=unanswered`,
  `POST /alerts/events/{id}/action` (`check` | `answer` | `reopen`).
