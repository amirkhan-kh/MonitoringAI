# Instagram + Meta: to'liq yakunlash yo'li

Bu hujjat MonitoringAI da Instagram monitoringini **oxirigacha** ishga tushirish
uchun kerak bo'lgan barcha qadamlarni tartib bilan beradi. Kod loyihada bor;
qolgan ish — Meta Developer Console, server env, public URL va App Review.

**Public domain (prod):** `https://monitoring.avioraai.uz`  
**Kompaniya:** Aviora AI · **Mahsulot:** MonitoringAI

---

## Nima allaqachon kodda bor

| Qism | Holat |
| --- | --- |
| Source ulash (token qo'lda / OAuth) | Bor |
| Business Login OAuth (`/instagram/oauth/start`, `/callback`) | Bor |
| Long-lived token (~60 kun) | Bor |
| Polling worker (`instagram-worker`) | Bor |
| Webhook (`/instagram/webhook`) | Bor |
| Deauthorize + data-deletion callback | Bor |
| AI tahlil (Gemini) | Bor |
| Signal inbox (risk → xodimlar) | Bor |
| Landing, Privacy, Terms, Data deletion (auth'siz) | Bor |

Sizda `.env` da hozir:

- `IG_APP_ID` — **SET**
- `IG_APP_SECRET` — **SET**
- `IG_VERIFY_TOKEN` — **SET**
- `IG_OAUTH_REDIRECT_URI` — **hali yo'q** (qo'shiladi)
- `APP_PUBLIC_BASE_URL` — **hali yo'q** (qo'shiladi)

---

## 0-bosqich. Talablar (tekshirish ro'yxati)

Instagram Business/Creator monitoring ishlashi uchun:

1. **Meta Developer App** (Instagram product yoqilgan).
2. Instagram akkaunt **Professional** (Business yoki Creator) bo'lsin.
3. Ideal holat: Instagram akkaunt **Facebook Page** ga bog'langan (ba'zi Graph
   oqimlari shuni kutadi; Business Login for Instagram oqimi to'g'ridan-to'g'ri
   IG login bilan ham ishlaydi — kod shu oqimda).
4. Server **HTTPS** public URL (`monitoring.avioraai.uz`).
5. Meta callback URL'lar internetdan ochiq (firewall/nginx).

---

## 1-bosqich. Meta Developer Console sozlamalari

### 1.1. App ochish / tanlash

1. [developers.facebook.com](https://developers.facebook.com/) → **My Apps**.
2. MonitoringAI / Aviora AI app ni oching (yoki yangi **Business** tipida yarating).
3. **App settings → Basic**:
   - **App ID** → `.env` dagi `IG_APP_ID` bilan bir xil.
   - **App Secret** → `IG_APP_SECRET` (Show → copy; hech qachon gitga yozmang).
   - **App Domains:** `monitoring.avioraai.uz`
   - **Privacy Policy URL:** `https://monitoring.avioraai.uz/privacy`
   - **Terms of Service URL:** `https://monitoring.avioraai.uz/terms`
   - **User data deletion:**  
     - Data Deletion Instructions URL: `https://monitoring.avioraai.uz/data-deletion`  
     - yoki Data Deletion Request Callback: `https://monitoring.avioraai.uz/api/instagram/data-deletion`
   - **Category:** Business and pages / Monitoring (eng yaqini).
   - **App Icon**, contact email to'ldiring.

### 1.2. Instagram product qo'shish

1. **Add product** → **Instagram**.
2. **API setup with Instagram login** (Business Login for Instagram) ni tanlang —
   kod `www.instagram.com/oauth/authorize` oqimini ishlatadi, **Facebook Login
   orqali Instagram** emas.
3. **Business** tipidagi Instagram app sozlamalarida scopes:
   - `instagram_business_basic`
   - `instagram_business_manage_comments`  
   (koddagi `DEFAULT_SCOPES` shu ikkalasi.)

### 1.3. OAuth redirect URI (eng muhim, byte-ma-byte)

Meta da **Valid OAuth Redirect URIs** ga **faqat** shu qiymatni yozing:

```text
https://monitoring.avioraai.uz/api/instagram/oauth/callback
```

Sabab: nginx `/api/` ni backendga uzatadi; backend route:
`GET /instagram/oauth/callback`.

**Xato qiladigan variantlar (ishlamaydi):**

- `http://...` (HTTPS bo'lishi shart)
- `.../instagram/oauth/callback` (`/api` yo'q)
- oxirida `/` ortiqcha
- `www.` farqi

### 1.4. Deauthorize callback

```text
https://monitoring.avioraai.uz/api/instagram/deauthorize
```

### 1.5. Data deletion callback

```text
https://monitoring.avioraai.uz/api/instagram/data-deletion
```

### 1.6. Webhook (real-time kommentlar)

1. Instagram product → **Webhooks** (yoki **Configuration**).
2. **Callback URL:**

```text
https://monitoring.avioraai.uz/api/instagram/webhook
```

3. **Verify token:** `.env` dagi `IG_VERIFY_TOKEN` bilan **bir xil** matn.
4. Subscribe fields (minimal monitoring uchun):
   - `comments`
   - `live_comments` (ixtiyoriy)
   - kerak bo'lsa `mentions` / platform ro'yxatidagi comment-related fieldlar
5. **Verify and save** — Meta `GET` bilan hub.challenge yuboradi; backend
   `IG_VERIFY_TOKEN` mos bo'lsa 200 qaytaradi.

### 1.7. Roles (Development mode)

App **Development** rejimida bo'lsa:

1. **App roles → Roles**: Instagram akkaunt egasini **Instagram Tester** qilib qo'shing.
2. Tester Instagram app / sozlamalarida **invitation** ni qabul qilsin.
3. Faqat shu tester akkauntlari OAuth orqali ulanadi — to **App Review** o'tmaguncha.

---

## 2-bosqich. Server `.env` (prod)

Loyiha ildizidagi `.env` ga qo'shing / yangilang (qiymatlarni o'zingiznikiga
almashtiring; bu misol):

```env
# --- Instagram / Meta ---
IG_APP_ID=<Meta App ID>
IG_APP_SECRET=<Meta App Secret>
IG_VERIFY_TOKEN=<webhook verify token — Meta bilan bir xil>
IG_GRAPH_VERSION=v21.0

# Public URL (SPA redirect va OAuth uchun)
APP_PUBLIC_BASE_URL=https://monitoring.avioraai.uz

# OAuth callback — Meta dagi Valid OAuth Redirect URIs bilan 1:1
IG_OAUTH_REDIRECT_URI=https://monitoring.avioraai.uz/api/instagram/oauth/callback

# Ixtiyoriy: bitta default token (OAuth bo'lsa kerak emas)
# IG_ACCESS_TOKEN=

INSTAGRAM_POLL_INTERVAL_SECONDS=60
INSTAGRAM_COMMENTS_PER_MEDIA=100
INSTAGRAM_MEDIA_PER_POLL=25

# CORS — frontend domain
CORS_ALLOW_ORIGINS=["https://monitoring.avioraai.uz","http://localhost:5173","http://127.0.0.1:5173"]
```

Lokal dev uchun (Meta redirect lokalga kelishi qiyin — odatda tunnel kerak):

```env
APP_PUBLIC_BASE_URL=http://localhost:5173
IG_OAUTH_REDIRECT_URI=http://localhost:8000/instagram/oauth/callback
```

Lokal OAuth to'liq ishlashi uchun Meta da ham lokal/tunnel URI bo'lishi va HTTPS
talabi bo'lishi mumkin — **prod URL orqali yakunlash tavsiya etiladi**.

Keyin:

```bash
docker compose up -d --build api instagram-worker ai-worker alert-worker
```

---

## 3-bosqich. Nginx / deploy tekshiruvi

`deploy/nginx-monitoringai.conf` allaqachon:

- `server_name monitoring.avioraai.uz`
- SPA: `/`
- API: `/api/` → `127.0.0.1:18090`
- SSE: `/api/events`

Tekshirish:

```bash
# Serverda
curl -sS https://monitoring.avioraai.uz/api/health
# kutiladi: {"status":"ok"} yoki shunga o'xshash

curl -sS -o /dev/null -w "%{http_code}\n" https://monitoring.avioraai.uz/privacy
# 200

curl -sS -o /dev/null -w "%{http_code}\n" https://monitoring.avioraai.uz/terms
# 200

curl -sS -o /dev/null -w "%{http_code}\n" https://monitoring.avioraai.uz/data-deletion
# 200
```

TLS yo'q bo'lsa:

```bash
sudo certbot --nginx -d monitoring.avioraai.uz
```

Frontend yangilansa:

```bash
cd frontend && npm run build
# dist ni serverdagi /opt/monitoringai/frontend-dist ga ko'chiring
```

---

## 4-bosqich. Dashboard orqali akkaunt ulash (OAuth)

1. `https://monitoring.avioraai.uz/login` — admin login.
2. **Profil** da brand yarating yoki tanlang (masalan Uzum Market demo).
3. **Instagram monitoring** oching.
4. **Instagram bilan ulanish** tugmasi:
   - API `GET /instagram/oauth/start?brand_id=...` → `authorize_url`
   - Brauzer Meta/Instagram consent oynasiga o'tadi
   - Ruxsat berilgach Meta →  
     `https://monitoring.avioraai.uz/api/instagram/oauth/callback?code=...&state=...`
   - Backend: code → short token → long-lived token → `detect_account` → source saqlanadi
   - Redirect:  
     `/instagram-monitoring?ig_connect=ok&username=...`
5. Source ro'yxatida username, sync holati ko'rinsin.
6. **Sync** tugmasi — so'nggi post/kommentlar yig'ilsin.
7. Bir necha daqiqada `ai-worker` tahlil yozsin; risk yuqori bo'lsa alert.

### Qo'lda token (zaxira yo'l)

OAuth ishlamaguncha:

1. Meta Graph API Explorer yoki long-lived token oling.
2. Dashboarddagi **Access token** maydoniga joylashtiring.
3. Brand tanlang → ulash.

Production uchun asosiy yo'l — **OAuth**, chunki App Review shuni ko'radi.

---

## 5-bosqich. Webhook live test

1. Meta Webhooks → **Test** (comments).
2. Yoki o'z IG Business akkauntingiz postiga **tester** sifatida komment yozing.
3. Backend log:

```bash
docker compose logs -f api instagram-worker
```

4. Dashboard **Instagram monitoring** yoki umumiy **mentions** da yangi qator.
5. Imzo tekshiruvi: `IG_APP_SECRET` noto'g'ri bo'lsa webhook 403/400 bo'ladi.

---

## 6-bosqich. App Review (Advanced Access)

Development rejimida faqat testerlar ishlaydi. Mijoz akkauntlari uchun:

### 6.1. Permissions so'rash

App Review da odatda:

| Permission | Nima uchun (inglizcha description yozing) |
| --- | --- |
| `instagram_business_basic` | Identify the connected Instagram professional account and read basic profile/media metadata required to attach the account to a brand workspace. |
| `instagram_business_manage_comments` | Read public comments on the account's media so the product can analyze brand reputation, sentiment and risk and alert the support team. |

**Messaging** scope so'ramang — mahsulot kerak qilmaydi, review sirtini kengaytiradi.

### 6.2. Screencast (majburiy deyarli)

Video (3–7 daqiqa) ketma-ketligi:

1. `https://monitoring.avioraai.uz` landing — kompaniya/mahsulot nima qiladi.
2. Privacy / Terms / Data deletion ochiladi (login **siz**).
3. Login → brand tanlash.
4. Instagram monitoring → **Instagram bilan ulanish**.
5. Meta consent oynasi — so'ralayotgan ruxsatlar ko'rinsin.
6. Muvaffaqiyatli redirect + ulangan username.
7. Postga komment → dashboardda paydo bo'lishi (yoki Sync).
8. (Ixtiyoriy) risk signal → Signal inbox / Telegram guruh.

### 6.3. Reviewer uchun test akkaunt

- App Review formaga **test Instagram user** bering (login/parol yoki Test User
  yo'riqnomasi).
- Reviewer o'sha akkaunt bilan OAuth ni bosib o'ta olishi kerak.
- Development mode da reviewer ni role ga qo'shish kerak bo'lishi mumkin —
  Meta formadagi ko'rsatmalarga amal qiling.

### 6.4. Business verification

Ba'zi ruxsatlar **Business Verification** talab qiladi:

1. Meta Business Suite / Business Manager.
2. Aviora AI yuridik ma'lumotlari, hujjatlar.
3. Domain verification (agar so'ralsa): `avioraai.uz` DNS TXT yoki HTML file.

### 6.5. Reviewdan keyin

- App **Live** mode.
- Mijoz o'z Business IG bilan OAuth qiladi — tester bo'lishi shart emas.
- Token ~60 kun; faol ishlatilsa refresh oqimini keyinroq qo'shish mumkin
  (hozir long-lived saqlanadi; muddati tugasa qayta OAuth yoki "Token yangilash").

---

## 7-bosqich. Xodimlar signal oqimi (Instagram risk)

Instagram comment tahlil → yuqori risk → `alert_events` → Telegram guruh + dashboard.

1. `.env`: `ALERT_TELEGRAM_CHAT_ID` (guruh id, odatda `-100...`).
2. Botni guruhga qo'shing va **admin** qiling (pin uchun).
3. Guruhda `/id` (agar agent/bot qo'llasa) yoki forward orqali chat id oling.
4. `docker compose up -d alert-worker telegram-worker api`
5. Batafsil: [`signal-inbox-xodimlar-guruhi.md`](signal-inbox-xodimlar-guruhi.md)

---

## 8-bosqich. Xavfsizlik checklist

- [ ] `IG_APP_SECRET` faqat `.env` / secret store da
- [ ] `.env` gitda emas
- [ ] Webhook imzo tekshiruvi yoqilgan (`ig_app_secret`)
- [ ] Dashboard `AUTH_ENABLED=true`, kuchli `JWT_SECRET` / admin parol
- [ ] CORS faqat o'z domenlaringiz
- [ ] Public legal sahifalar ishlaydi
- [ ] Production da `IG_OAUTH_REDIRECT_URI` Meta bilan 1:1

---

## 9-bosqich. Xatoliklar va tuzatish

| Alomat | Sabab | Yechim |
| --- | --- | --- |
| `IG_APP_ID / IG_APP_SECRET sozlanmagan` | env bo'sh yoki container eski | `.env` to'ldirib `compose up -d --build api` |
| OAuth `redirect_uri` mismatch | Meta va server URI farq qiladi | ikkalasini bir xil qiling (yuqoridagi URL) |
| Consent ochiladi, keyin error redirect | code exchange fail / secret xato | secret, redirect, app type (Instagram login) |
| `Akkaunt aniqlanmadi` | token scope yetarli emas yoki shaxsiy akkaunt | Professional IG + to'g'ri scopes |
| Webhook verify fail | verify token mos emas | Meta = `IG_VERIFY_TOKEN` |
| Webhook keladi, mention yo'q | field subscribe yo'q / signature | comments field + `IG_APP_SECRET` |
| Development: "App not set up" | tester emas | Roles → Instagram Tester |
| Kommentlar bo'sh | Advanced Access yo'q yoki scope berilmagan | App Review + granted permissions log |
| 60 kundan keyin 401 | long-lived muddati | qayta OAuth yoki Token yangilash |

---

## 10-bosqich. Kunlik ish tartibi (operatsion)

```text
1. Brand → Instagram OAuth ulash (bir marta / token yangilash)
2. instagram-worker poll + webhook real-time
3. ai-worker tahlil
4. alert-worker risk → Telegram + Signal inbox
5. Xodim: Tekshirildi / Javob berdim
```

Docker servislar (minimal IG stack):

```bash
docker compose up -d --build \
  postgres api \
  instagram-worker \
  ai-worker \
  alert-worker
```

To'liq stack (barcha platformalar):

```bash
docker compose up -d --build \
  postgres api \
  telegram-worker telegram-connector-worker telegram-live-sync \
  youtube-worker instagram-worker facebook-worker \
  ai-worker alert-worker
```

---

## 11-bosqich. Sizning navbatdagi amaliy ro'yxat (bugun)

1. Meta Console da redirect / deauth / data-deletion / webhook URL larni yozing.
2. `.env` ga `APP_PUBLIC_BASE_URL` va `IG_OAUTH_REDIRECT_URI` qo'shing.
3. Prod ga frontend build + API restart.
4. `curl` bilan health + privacy 200.
5. Tester IG bilan OAuth bosib o'ting.
6. Komment yozib sync/webhook ni tasdiqlang.
7. App Review screencast yozing va permissions yuboring.
8. Business verification hujjatlarini boshlang (agar so'ralsa).

---

## Tegishli fayllar (kod)

| Fayl | Vazifa |
| --- | --- |
| `backend/app/services/instagram_oauth.py` | OAuth exchange |
| `backend/app/services/instagram_api.py` | Graph API |
| `backend/app/services/instagram_sync.py` | Sync/backfill |
| `backend/app/workers/instagram_worker.py` | Poller |
| `backend/app/main.py` | routes: oauth, webhook, deauth |
| `frontend/src/pages/InstagramMonitoring.jsx` | UI |
| `frontend/src/pages/Landing.jsx` / `Legal.jsx` | Meta public pages |
| `deploy/nginx-monitoringai.conf` | `/api` proxy |

---

## Qisqa sxema

```text
[Operator] → Dashboard "Instagram bilan ulanish"
    → GET /api/instagram/oauth/start
    → Instagram consent
    → GET /api/instagram/oauth/callback?code=
    → long-lived token + InstagramSource

[IG user komment] → Meta Webhook POST /api/instagram/webhook
    → mention row → ai-worker → analysis
    → (risk) alert-worker → Telegram guruh + Signal inbox
```
