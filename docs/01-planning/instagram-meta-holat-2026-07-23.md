# Instagram/Meta yakunlash — holat hisoboti (2026-07-23)

## SaaS modeli: asosiy printsip

App Review o'tilgach, Meta app **Live** rejimga o'tadi va dunyodagi ixtiyoriy
Instagram Business akkaunt "Instagram bilan ulanish" tugmasi orqali ulana oladi —
Telegram/YouTube'dagidek silliq. Mijoz o'z akkaunti bilan kiradi, o'zi ruxsat beradi.
Loyiha egasining akkaunti/tokeni ishtirok etmaydi.

### Yangi mijoz onboarding'i (App Review'dan keyin)

1. Ro'yxatdan o'tish → tarif tanlash → to'lov
2. Brand yaratish (Profile → Gemini auto-fill)
3. Platformalarni o'zi ulaydi:
   - Telegram: bot token + kanal/guruh linklari (tayyor, per-brand connector)
   - YouTube: kanal linki (tayyor; serverdagi global API kalit)
   - Instagram: OAuth tugma (kod tayyor; Live mode kutilmoqda)
   - Facebook: hozir token paste → OAuth tugma kerak (P2)
   - WhatsApp: monitoring emas — faqat bildirishnoma/support kanali (Cloud API)

### Meta bilan kelishuv uchun checklist

| Talab | Holat |
| --- | --- |
| Public legal sahifalar (privacy/terms/data-deletion) | ✅ tayyor |
| Haqiqiy OAuth oqimi (consent screen) | ✅ ishlayapti |
| Faqat zarur 2 scope | ✅ tozalandi |
| Business verification (YaTT) | ⏳ soliq tekshiruvida |
| App icon | ❌ yuklanmagan (fayl tayyor: docs/assets/monitoringai-icon-1024.jpg) |
| Screencast video | ❌ yozilmagan |
| Reviewer test akkaunt + forma bo'limlari | ❌ to'ldirilmagan |
| Mijoz IG akkaunti Professional bo'lishi | onboarding yo'riqnomasiga kiritiladi |

### SaaS uchun mahsulot tomonidagi bo'shliqlar (Meta'dan mustaqil)

1. Multi-user auth (hozir bitta admin .env'da)
2. Tariflar/to'lovlar (Payme/Click), limitlar
3. Tenant izolyatsiyasi (har mijoz faqat o'z ma'lumotini ko'radi)
4. Facebook OAuth tugma
5. Onboarding yo'riqnomasi ("IG akkauntni Professional qiling" 1-qadam)

---

## 1–9: Qilingan va qolgan ishlar

### ✅ 1-qadam — Meta Console → Settings → Basic (TUGADI)

- App Domains: monitoring.avioraai.uz
- Privacy/Terms/Data-deletion URL'lar, kategoriya "Бизнес и Страницы", kontakt email
- Qolgan: App Icon (Meta upload xatosi; JPG tayyor)

### ✅ 2-qadam — OAuth redirect URI + callback'lar (TUGADI)

- .../api/instagram/oauth/callback, .../deauthorize, .../data-deletion — byte-ma-byte
- Kashfiyot: OAuth Instagram app ID (3345064788998743) bilan ishlaydi — lokal .env tuzatildi

### ✅ 3-qadam — Webhook (TUGADI + sinovdan o'tdi)

- Callback URL + verify token, comments + live_comments obunada
- Meta "Тестировать" → POST /instagram/webhook → 200 OK (imzo ishlaydi)

### ✅ 4-qadam — Instagram Tester (TUGADI)

- xakimov_abubakir — Tester roli 16-iyuldan qabul qilingan

### ✅ 5-qadam — Server .env + restart (TUGADI)

- IG_APP_ID/IG_APP_SECRET to'g'ri (Instagram juftligi)
- APP_PUBLIC_BASE_URL + IG_OAUTH_REDIRECT_URI qo'shildi, api + instagram-worker restart

### ✅ 6-qadam — Jonli OAuth testi (TUGADI)

- @xakimov_abubakir haqiqiy consent orqali ulandi
- 65 post import, engagement yangilanadi, AI gate 65/65

### ✅ 7-qadam — Zanjir diagnostikasi (TUGADI — dalillangan)

- Media sync ✅, AI tahlil ✅, webhook yo'li ✅, API komment yozish/o'chirish ✅
- Komment o'qish — POST 200 / GET data:[] → Meta Development mode bloklaydi
- Yechim: faqat App Review (Advanced Access)

### ⏳ 8-qadam — App Review tayyorgarlik (YARMI TAYYOR)

- Bajarildi: 2 ta scope qoldirildi (basic + manage_comments);
  "Требуемые действия" toza; submission formasi ochildi
- Qolgan: icon yuklash → screencast yozish → 4 bo'limni to'ldirish
  (inglizcha tavsiflar + reviewer yo'riqnomasi + test akkaunt) → "Отправить"

### ⏳ 9-qadam — Business verification (JARAYONDA — yagona bloker)

- Bajarildi: birdarcha.uz + ERI orqali YaTT arizasi topshirildi
  (62.01.0 — dasturlash; Face-ID tasdiq) → Soliq organlari tekshiruvida (1 daq – 3 ish kuni)
- Qolgan: guvohnoma PDF → Meta "Завершить подтверждение"
  (yuridik nom = YaTT FIO, haqiqiy manzil + pochta.uz indeksi, guvohnoma yuklash)
  → Meta tasdig'i (~48 soat) → App Review yuborish → Live mode → kommentlar ochiladi

---

## Bugun tugatiladigan parallel ishlar

1. Ikonka yuklash (Basic settings → App Icon → monitoringai-icon-1024.jpg)
2. Screencast yozish (Cmd+Shift+5, ssenariy tayyor)
3. App Review forma bo'limlarini to'ldirish
4. Demo kommentlar joylab dashboard'ni to'ldirish (demo ingest formasi)
