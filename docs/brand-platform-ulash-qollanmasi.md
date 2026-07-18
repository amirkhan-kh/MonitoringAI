# Brand platformalarini ulash: sodda qo'llanma

Bu qo'llanma istalgan brandning Telegram va YouTube manbalarini MonitoringAI'ga
ulash uchun yozilgan. Misollar biror aniq brandga bog'lanmagan.

## 1. Avval brandni tanlang

1. Dashboardda **Profil** sahifasini oching.
2. Mavjud brandni tanlang yoki **Yangi brand** yarating.
3. Telegram va YouTube ulanishlari aynan tanlangan brandga yozilishini tekshiring.

Brand tanlanmasa connector saqlanmaydi. Bu boshqa client ma'lumotlarini aralashtirib
yubormaslik uchun kerak.

## 2. Telegram ulash

Dashboardda **Telegram monitoring → Faol brand** orqali brandni tanlang, keyin
source panelidagi **Qo'shish** tugmasini bosing.

Telegram formasidagi barcha maydonlar alohida optional. Sizda bor ma'lumotni
kiritasiz. Forma bo'yicha faqat **umumiy bitta qiymat** kerak: bot link/token, kanal
yoki discussion linkidan istalgan bittasi. Kanal yoki group linki darhol saqlanadi;
monitoring bot accessi yoki authorized Telethon worker chatni o'qigach boshlanadi.
**Faqat bot linkining o'zi esa monitoring bermaydi**: link
botni tanitadi, lekin uning inbox xabarlarini o'qish huquqini bermaydi.

### Telegram imkoniyatlari

| Sizda nima bor | Nima ishlaydi |
| --- | --- |
| Faqat kanal linki | Source saqlanadi; authorized Telethon user kanalni o'qigach postlar kuzatiladi |
| Faqat discussion group linki | Source saqlanadi; monitoring user yoki bot groupga kira olsa yangi group/commentlar olinadi |
| Faqat bot tokeni + dedicated polling | Shu botning yangi private inbox xabarlari olinadi; group/channel uchun ularning refini ham kiriting |
| Faqat bot linki | Reference sifatida saqlanadi; xabar monitoringi yo'q |
| Kanal + discussion | Ikkalasi alohida ulanadi va discussion kanalga bog'lanadi |
| Bot token + kanal/group | Polling rejimida Bot API update'lari olinadi; Reference rejimida token faqat identity/access tekshiradi va live oqim uchun Telethon kerak |

### Serverda bir marta tayyorlanadigan Telegram vositalari

Dashboarddagi public kanal/group linklarini Telethon orqali kuzatish uchun server
operatori bir marta `TELEGRAM_API_ID` va `TELEGRAM_API_HASH` oladi:

1. Telegram akkaunti bilan [my.telegram.org](https://my.telegram.org) saytiga kiring.
2. **API development tools** bo'limini oching.
3. App nomi va qisqa nomini kiriting.
4. Berilgan `api_id` va `api_hash`ni serverdagi `.env`ga yozing:

```env
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
```

Rasmiy ko'rsatma: https://core.telegram.org/api/obtaining_api_id

Bot tokenlari bazaga shifrlab yozilishi uchun server operatori Fernet keyni bir
marta yaratadi. Key restartlarda o'zgarmasligi kerak:

```bash
docker compose build api
docker compose run --rm --no-deps api python -c \
  'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Natijani `.env`ga `CONNECTOR_ENCRYPTION_KEY=...` qilib yozing. Bu key client
formasiga kiritilmaydi va hech kimga yuborilmaydi.

### A. Bot linkini olish

1. Telegramda bot profilingizni oching.
2. Bot username'ini ko'ring, masalan `@my_brand_bot`.
3. Link quyidagicha bo'ladi: `https://t.me/my_brand_bot`.
4. Shu linkni **Bot link yoki username** maydoniga kiriting.

Bot linkning o'zi faqat reference. Botga kelgan xabarlarni olish uchun token va
update transporti kerak.

### B. Bot tokenini olish

1. Telegramda rasmiy [@BotFather](https://t.me/BotFather) botini oching.
2. `/mybots` yuboring.
3. Kerakli botni tanlang.
4. **API Token** bo'limini oching. Yangi bot yaratayotgan bo'lsangiz `/newbot`
   orqali token beriladi.
5. Tokenni dashboarddagi **Bot token** password maydoniga kiriting.

Token parolga teng. Uni chat, screenshot, hujjat yoki source code'ga yozmang.
Telegramning rasmiy qo'llanmasi token egasi bot ustidan to'liq nazorat olishini
ogohlantiradi: https://core.telegram.org/bots

### C. Bot rejimini tanlash

#### Reference

Quyidagi holatlarda tanlang:

- bot boshqa serverda ishlab turibdi;
- bot webhook ishlatyapti;
- faqat kanal yoki discussion monitoringi kerak;
- bot tokenini MonitoringAI pollingiga bermoqchi emassiz.

Bu rejim mavjud production bot ishini buzmaydi.

Serverdagi ayni bot allaqachon `TELEGRAM_BOT_TOKEN` sifatida legacy workerga
ulangan bo'lsa, uni **Dedicated polling**ga o'tkazmang. Reference rejimida kanal va
group source'lari legacy worker oqimida qoladi. Faol webhook aniqlansa MonitoringAI
uni o'chirmaydi va polling tayyor deb ko'rsatilmaydi.

#### Dedicated polling

Faqat quyidagi holatda tanlang:

- bot boshqa server yoki dasturda `getUpdates` ishlatmaydi;
- botda outgoing webhook o'rnatilmagan;
- MonitoringAI shu bot update'larining yagona consumer'i bo'ladi.

Telegram bir token uchun `getUpdates` va webhookni bir vaqtda ishlatmaydi. Rasmiy
FAQ: https://core.telegram.org/bots/faq

MonitoringAI mavjud webhookni avtomatik o'chirmaydi. Webhook topilsa polling
yoqilmaydi va conflict status qaytadi.

### D. Kanal linkini olish

1. Telegram kanalini oching.
2. Kanal nomiga bosing.
3. Public kanal bo'lsa username yoki **Copy Link** orqali linkni oling.
4. Masalan: `https://t.me/my_brand_channel`.
5. Linkni **Kanal linki, username yoki ID** maydoniga kiriting.

Public kanal uchun linkning o'zi yetishi mumkin. Private kanal uchun MonitoringAI
Telethon user'i kanalga a'zo bo'lishi yoki bot kerakli accessga ega bo'lishi kerak.

Bot API orqali kanal postlarini olish uchun kanal egasi:

1. Kanal profilini ochadi va **Administrators** bo'limiga kiradi.
2. **Add Admin**ni bosib bot username'ini topadi.
3. Botni administrator qilib saqlaydi.
4. Dashboarddagi source qatorida **Tekshirish**ni bosadi.

### E. Discussion group linkini olish

1. Kanalni oching va post commentini bosing.
2. Ochilgan discussion group nomiga bosing.
3. Group linkini **Copy Link** orqali nusxalang.
4. Linkni **Group linki, username yoki ID** maydoniga kiriting.

Public groupda `https://t.me/group_username` yetadi. Private `https://t.me/+...`
invite link Bot API uchun chat ID emas: avval Telethon monitoring userini groupga
qo'shing, `make telethon-live-login` bilan sessionni tayyorlang, keyin:

```bash
make telethon-dialogs
```

Natijadan group nomi yonidagi `-100...` qiymatni dashboardga kiriting. Bu usul
uchinchi tomon botiga private group ma'lumotini yubormaydi.

Faqat yangi group xabarlarini bot orqali olish uchun:

- botni groupga qo'shing;
- eng ishonchli usul — botni admin qilish;
- yoki BotFather'da `/setprivacy` orqali Privacy Mode'ni o'chirib, botni groupdan
  olib qayta qo'shing.

Telegramda Privacy Mode default yoqilgan; admin botlar barcha group xabarlarini
oladi: https://core.telegram.org/bots/features#privacy-mode

### F. Telegram formasini saqlash

1. Brand tanlanganini tekshiring.
2. Sizda bor maydonlarni kiriting; qolganini bo'sh qoldiring.
3. **Kuzatuv sanasi**ni tanlamasangiz bugungi sana olinadi.
4. **Postlar** va **Comment/group xabarlari** flaglarini tanlang.
5. **Telegram ulanishini saqlash** tugmasini bosing.
6. Natijada bot, kanal va discussion uchun alohida status ko'rsatiladi.

Statuslarni shunday o'qing:

- `monitoring` yoki botdagi `active` — worker transporti va access tasdiqlangan;
- `access kutilmoqda` — source saqlangan, lekin bot yoki Telethon hali o'qiy olgani
  isbotlanmagan;
- `catalog` — link saqlangan, Telegram numeric chat ID hali resolve bo'lmagan;
- `reference` — bot profili saqlangan, private inbox olinmaydi;
- `ready` — dedicated worker birinchi polling siklini boshlash arafasida;
- `legacy` — serverning global Telegram worker'i update oqimini boshqaradi;
- `webhook_conflict` yoki `conflict` — boshqa consumer update oqimini ishlatyapti;
- `rate_limited` — Telegram vaqtincha kutishni buyurdi;
- `invalid` — token rad etildi; `encryption_error` — server tokenni decrypt qila olmadi;
- `error` — vaqtinchalik worker xatosi, qayta urinish bo'ladi.

Connector-managed source qatoridagi **Tekshirish** tanlangan brand connection tokeni
yoki shu source uchun worker tasdiqlagan Telethon accessidan foydalanadi. Eski
legacy source'larda serverning global bot fallback'i ishlashi mumkin.

### G. Eski Telegram tarixini olish

Bot API eski to'liq tarixni bermaydi. History backfill uchun alohida Telethon user
session kerak:

```bash
make telethon-login
```

Terminalda telefon, Telegram yuborgan kod va akkauntda yoqilgan bo'lsa 2FA parolni
kiriting. Kod yoki parolni chatga yubormang.

Doimiy live-sync uchun alohida session yarating:

```bash
make telethon-live-login
```

Ikkala session holatini tekshirish:

```bash
make telethon-status
make telethon-live-status
```

`telethon-login` manual history/backfill sessiyasini, `telethon-live-login` esa
doimiy live monitoring sessiyasini tayyorlaydi. Bir xil `.session` faylini ikki
worker yoki server orasida ko'chirmang.

Link-only source kartasi worker birinchi marta chatni muvaffaqiyatli o'qiguncha
public username yoki numeric ID resolve bo'lsa `access kutilmoqda` bo'lib turishi
normal; resolve bo'lmagan link avval `catalog` ko'rinadi. Worker chatni o'qigach
Telethon access holati `ready` sifatida bazaga yoziladi. Eski tarixni olish uchun
source qatoridagi **To'liq olish** tugmasini alohida bosing.

## 3. YouTube ulash

Rasmiy public YouTube kanal monitoringi uchun brand egasi OAuth token yoki shaxsiy
API key kiritmaydi. MonitoringAI serveridagi YouTube Data API key kanalni resolve
qilish, public video va commentlarni olish uchun ishlatiladi.

### Serverda YouTube API keyni bir marta olish

1. [Google Cloud Console](https://console.cloud.google.com/)da project yarating yoki tanlang.
2. **APIs & Services → Library** bo'limida **YouTube Data API v3**ni yoqing.
3. **APIs & Services → Credentials → Create credentials → API key**ni tanlang.
4. Key restrictionda faqat **YouTube Data API v3**ni qoldiring; productionda
   server IP restriction ham qo'ying.
5. Keyni serverdagi `.env`ga yozing:

```env
YOUTUBE_API_KEY=...
```

Rasmiy boshlash qo'llanmasi:
https://developers.google.com/youtube/v3/getting-started

Brand egasi bu keyni dashboardga kiritmaydi. Bitta server key barcha client
brandlarning public kanal ma'lumotlarini oladi.

### YouTube kanalini ulash uchun bittasi yetadi

- Kanal URL: `https://www.youtube.com/@mybrand`
- Handle: `@mybrand`
- Channel ID: `UC...` bilan boshlanadigan 24 belgili ID
- ID-based URL: `https://www.youtube.com/channel/UC...`
- Legacy username URL: `https://www.youtube.com/user/...`

Bir kanal uchun ularning barchasini kiritish shart emas.
`https://www.youtube.com/c/...` custom URL qo'llanmaydi; uning o'rniga `@handle`
yoki `UC...` Channel ID ishlating.

### A. Handle URL'ni olish

1. YouTube Studio'ga kiring.
2. **Customization** bo'limini oching.
3. **Basic info**ni tanlang.
4. **Handle** ostidagi `youtube.com/@...` linkini nusxalang.

Rasmiy YouTube ko'rsatmasi:
https://support.google.com/youtube/answer/6180214

### B. Channel ID'ni olish

1. YouTube'ga channel owner sifatida kiring.
2. Profil rasmi → **Settings**.
3. **Advanced settings**ni oching.
4. **Channel ID** qiymatini nusxalang.

Rasmiy YouTube ko'rsatmasi:
https://support.google.com/youtube/answer/3250431

### C. Rasmiy kanal formasini saqlash

1. Dashboardda **YouTube monitoring** sahifasini oching.
2. Faol brandni tanlab **Qo'shish**ni bosing.
3. **Rasmiy kanal** rejimini tanlang.
4. Kanal URL, handle yoki Channel ID maydonlaridan bittasini kiriting.
5. **Videolar** va kerak bo'lsa **Commentlar**ni yoqing.
6. Kuzatuv sanasini tanlang.
7. **Rasmiy kanalni ulash**ni bosing.

API tayyor bo'lsa MonitoringAI kanal nomi, canonical channel ID va uploads
playlistni avtomatik topadi. YouTube `channels.list` handle yoki channel ID bo'yicha
kanalni topishni qo'llaydi:
https://developers.google.com/youtube/v3/docs/channels/list

YouTube holatlari:

- `Tayyor` — server API keyi bor; `Sozlanmagan` — source kataloglanishi mumkin,
  ammo kanal resolve/sync qilinmaydi;
- `resolved` — kanal API orqali topildi; `cataloged/draft` — key yoki resolve hali yo'q;
- `active` flag — source yoqilganini bildiradi, lekin API/resolve tayyorligini o'zi
  kafolatlamaydi; UI haqiqiy holatni `monitoring`, `API kutilmoqda` yoki
  `kanal resolve kutilmoqda` deb ajratadi; `paused` — source vaqtincha o'chirilgan;
- sync natijasidagi video/comment soni — ayni siklda ko'rilgan ma'lumot;
- sync xatoligi yoki quota ogohlantirishi — source saqlangan bo'lishi mumkin, lekin
  yangi ma'lumot olish yakunlanmagan.

### D. Advanced watch qachon ishlatiladi

Quyidagilar rasmiy kanal formasidan alohida:

- bitta video URL;
- competitor kanal;
- keyword qidiruvi;
- hashtag monitoringi.

Keyword va hashtag `search.list` quota sarflaydi. Rasmiy kanal uchun imkon qadar
kanal URL/handle/ID ishlating.

## 4. Tez tekshiruv

Server `.env` o'zgargach servislarni yangilang:

```bash
make up
```

### Telegram

- Source kartasida to'g'ri brand ko'rsatilganmi?
- Dedicated polling bot statusi worker ishga tushgach `active` bo'ldimi?
- Polling tanlangan bo'lsa webhook/409 conflict yo'qmi?
- Kanal/group `monitoring`mi yoki aniq sabab bilan `access kutilmoqda`mi?
- Yangi test post yoki comment dashboardga keldimi?

### YouTube

- API status `Tayyor`mi?
- Source turi `channel`mi, `keyword` emasmi?
- Canonical `UC...` channel ID topildimi?
- Test sync video va comment sonini qaytardimi?

## 5. Muhim xavfsizlik qoidalari

- Telegram bot tokenini faqat password maydoniga kiriting.
- Tokenni chatga yoki support xabariga yubormang.
- Token oshkor bo'lsa BotFather orqali darhol revoke qiling.
- Production webhook botini dedicated polling rejimiga o'tkazmang.
- Har bir ulashdan oldin dashboardda to'g'ri brand tanlanganini tekshiring.
- YouTube API key brand formasiga kiritilmaydi; u server admin konfiguratsiyasi.
