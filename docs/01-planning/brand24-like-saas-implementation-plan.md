# MonitoringAI → Brand24-kabi global SaaS: to‘liq implementatsiya rejasi

**Sana:** 2026-07-27  
**Status:** REJA (kod hali yo‘q — shu hujjat kelishuvdan keyin bosqichma-bosqich yoziladi)  
**Maqsad:** Istalgan foydalanuvchi **register → trial/to‘lov → o‘z dashboardi** orqali to‘liq foydalansin; super-admin platformani boshqarsin. Model: [Brand24](https://brand24.com/) self-serve SaaS.

---

## 0. Nima uchun hozir ishlamaydi (ochiq tan olish)

| Hozir | Brand24 kabi kerak |
|-------|---------------------|
| Bitta `.env` admin | Cheksiz user register |
| Barcha brandlar hammaga ko‘rinadi | Har org faqat o‘z brendlari |
| Tarif faqat landing matn | DB plan + limit + enforcement |
| To‘lov yo‘q | Trial + to‘lov + obuna |
| Super-admin yo‘q | Platform operator paneli |
| AI/worker global | Tenant kvota + adolatli navbat |

**Xulosa:** Mahsulot “bitta operator multi-brand consoli”. SaaS qatlami **qurilmagan**. Oldingi `saas-billing-superadmin-plan.md` — narx/strategiya; **shu hujjat — qanday qurish tartibi**.

---

## 1. Brand24 oqimi (nima nusxa olinadi)

### 1.1. Foydalanuvchi sayohati

```
Marketing sayt (brand24.com)
  → [Sign up free] → app.brand24.com/register
  → email + parol (14 kun trial, ko‘pincha karta ixtiyoriy)
  → birinchi "project/keyword" setup
  → dashboard (mentions, sentiment, alerts)
  → trial tugashi → tarif tanlash → to‘lov → davom
  → jamoa a’zolarini taklif qilish (plan bo‘yicha)
```

### 1.2. Biznes birliklari (Brand24)

| Tushuncha | Ma’nosi |
|-----------|---------|
| Account / workspace | To‘lov va limit birligi |
| Project / brand | Monitoring ob’ekti (kalit so‘zlar) |
| Mentions / mo | Asosiy soft/hard limit |
| Keywords | Qidiruv qamrovi limiti |
| Users / seats | Jamoa o‘rindiqlari |
| Trial | Self-serve kirish |

### 1.3. MonitoringAI da ekvivalent

| Brand24 | MonitoringAI |
|---------|----------------|
| Account | **Organization (org)** |
| Project | **Brand** |
| Mentions/mo | **AI-tahlil qilingan mention / oy** (+ ixtiyoriy raw ingest) |
| Keywords / sources | **Sources** (TG/IG/YT/FB) + plan bo‘yicha platforma limitleari |
| Users | **organization_members** (role) |
| Alerts | **Per-brand Telegram staff** (hozir global env — o‘zgartirish shart) |
| Admin (Brand24 ichki) | **super_admin** |

### 1.4. Bizda farq (raqobat ustunligi — saqlanadi)

- Telegram-first + staff workflow (reply/close) — Brand24 dan kuchliroq mahalliy
- Vertex AI risk + tavsiya
- O‘zbek/RU matn
- UZ to‘lov (Payme/Click) keyinroq

**Nusxa qilinmaydi:** 25M domain crawl. Biz **ulangan manbalar + keyword** modelida qolamiz (allaqachon shunday).

---

## 2. Maqsad holat (Definition of Done — “global ishlaydi”)

1. Yangi odam `monitoring.avioraai.uz` da **Ro‘yxatdan o‘tish** qiladi.  
2. Email+parol bilan **Login**.  
3. Avtomatik **Trial** (masalan 7–14 kun / N free AI mention).  
4. **O‘z org** ichida brand yaratadi, source ulaydi, dashboard ko‘radi.  
5. Boshqa org ma’lumotini **ko‘rmaydi** (IDOR yo‘q).  
6. Limit tugasa yoki trial tugasa — **upgrade / to‘lov** (Faza A: super-admin manual; Faza B: Payme/Click/Stripe).  
7. Super-admin: user/org/plan/usage/ban/impersonate.  
8. Landing “Tanlash” → register?plan=growth.

---

## 3. Ma’lumotlar modeli (asos)

```
users
  id, email (unique), password_hash, full_name, is_super_admin,
  email_verified_at, status, last_login_at, created_at

organizations
  id, name, slug, owner_user_id, status (trial|active|past_due|suspended),
  trial_ends_at, created_at

organization_members
  org_id, user_id, role (owner|admin|member|viewer), invited_at, accepted_at
  UNIQUE(org_id, user_id)

plans
  id, code (start|growth|business|scale), name,
  price_usd, price_uzs,
  ai_mention_limit_monthly, brands_limit, seats_limit,
  platforms jsonb,   -- ["telegram","youtube","instagram","facebook"]
  features jsonb,    -- alerts, export, sla_minutes, ai_tier (flash|hybrid|pro)
  active, sort_order

subscriptions
  id, org_id, plan_id, status, current_period_start, current_period_end,
  payment_provider (manual|payme|click|stripe), external_ref,
  cancel_at_period_end

usage_monthly
  org_id, year_month (2026-07),
  mentions_ingested, ai_analyses, tokens_in, tokens_out, cost_est_usd,
  UNIQUE(org_id, year_month)

brands  (+ organization_id UUID NOT NULL FK, index)
  -- name unique per org: UNIQUE(organization_id, name)  (global unique olib tashlanadi)

-- barcha brand-scoped querylar: brand.organization_id = current_org
```

**Mavjud data migratsiyasi:**  
Bitta default org `Aviora Internal` + super_admin user (eski `.env` admin) + barcha mavjud brandlar shu orgga.

---

## 4. Auth va xavfsizlik

### 4.1. Token (JWT-shaped, mavjud uslub)

```json
{
  "sub": "<user_uuid>",
  "email": "...",
  "org_id": "<org_uuid>",
  "role": "owner|admin|member|viewer|super_admin",
  "exp": ...
}
```

### 4.2. API qoidalari

- `require_auth` → user yuklash  
- `require_org` → org a’zoligi  
- Har brand/source/mention endpoint:  
  `brand.organization_id == token.org_id` (super_admin exception)  
- Register public: `POST /auth/register`  
- Login: `POST /auth/login` (email+password)  
- `GET /auth/me` → user + org + plan + usage summary  
- Invite (keyinroq): `POST /org/members/invite`

### 4.3. Parol

- Argon2id yoki bcrypt  
- Min 8 belgi  
- Password reset (Faza 2): email token

---

## 5. Plan enforcement (yurak)

| Limit | Qayerda tekshiriladi |
|-------|----------------------|
| brands_limit | `POST /brands` |
| seats_limit | invite/register member |
| platforms | source create (IG faqat Growth+ va h.k.) |
| ai_mention_limit | **ai_worker** analysis oldidan + optional API “analyze now” |
| trial_ends_at / subscription.status | global middleware: suspended → 402/403 write; read ixtiyoriy |

**Usage increment:** analysis muvaffaqiyatli yozilganda `usage_monthly.ai_analyses += 1`.

**80% / 100%:** dashboard banner + email/Telegram (keyinroq).

**AI tier by plan (xarajat himoyasi):**

| Plan | Analysis model |
|------|----------------|
| Start / Trial | flash-lite only |
| Growth | flash + Pro faqat high risk |
| Business/Scale | full Pro (hozirgi sifat) |

---

## 6. Workers multi-tenant

Workers global qolishi mumkin, lekin:

1. Brand/source query join org + `subscription.status in (trial, active)`.  
2. Suspended org brandlari skip.  
3. AI worker: org usage < limit.  
4. Fairness (Faza 2): round-robin org yoki plan priority queue.  
5. Alerts: **env global chat o‘rniga** brand/org `staff_telegram_chat_id` (allaqachon qisman brand connection bor — to‘liq per-tenant).

**YouTube API key / Telethon:** hozir shared — SaaS da noisy-neighbor risk; Faza 2 da rate limit per org.

---

## 7. Frontend oqimlari

### 7.1. Public

| Route | Maqsad |
|-------|--------|
| `/` | Landing; CTA **Bepul boshlash** / **Kirish** |
| `/register` | email, parol, org nomi, ixtiyoriy plan |
| `/login` | email + parol |
| `/pricing` yoki `#tariflar` | plan → register?plan= |

### 7.2. App (authed)

| Route | Maqsad |
|-------|--------|
| `/onboarding` | birinchi brand + birinchi source (Brand24 setup) |
| `/umumiy-dashboard` | faqat o‘z org brandlari |
| `/profile` | brandlar + **Plan / Usage** progress |
| `/billing` | joriy plan, upgrade, to‘lov holati |
| `/settings/team` | a’zolar (Growth+) |
| `/super-admin/*` | faqat is_super_admin |

### 7.3. Landing CTA

- Unauth: **Ro‘yxatdan o‘tish** (login emas)  
- Plan card: `href=/register?plan=growth`  
- Auth: Dashboard

---

## 8. Super-admin

**Kim:** `users.is_super_admin=true` (seed: eski env admin).

**Imkoniyatlar (MVP):**

- Org/user ro‘yxati, qidiruv  
- Plan biriktirish / trial uzaytirish  
- Status: active / suspended  
- Usage ko‘rish (AI, cost est.)  
- Impersonate org (audit log)  
- Manual “to‘lov qabul qilindi”

**UI:** `/super-admin` alohida layout.

---

## 9. To‘lov bosqichlari

### Faza A — Manual (tez, UZ bozor)

1. User trial/register.  
2. Upgrade so‘rovi yoki super-admin invoice.  
3. Super-admin `subscription` ni `active` + plan qo‘yadi.  
4. Payme/Click link chat orqali (tashqi).

### Faza B — Self-serve

1. Payme va/yoki Click merchant.  
2. Webhook → subscription active.  
3. Ixtiyoriy Stripe (global USD).

**Tavsiya:** avval Faza A bilan “register + isolation + limit” ishga tushsin; to‘lov avtomat keyin.

---

## 10. Implementatsiya fazalari (PR rejasi)

> Har faza merge → local sinov → prod deploy.  
> **Register ochilmasin** to Faza 2 isolation tayyor bo‘lguncha (aks holda hammasi bir-birini ko‘radi).

### Faza 0 — Kelishuv (1 soat, siz)

- [ ] Trial: 7 yoki 14 kun?  
- [ ] Free AI mention trial: 300 / 500?  
- [ ] Narxlar: UZS asosiy yoki USD?  
- [ ] To‘lov: hozir faqat manualmi?  
- [ ] Mavjud data: bitta internal org?

### Faza 1 — Data + Auth foundation (2–3 kun)

**Backend**

- [ ] Models: users, organizations, members, plans, subscriptions, usage_monthly  
- [ ] Migration / create_all + seed plans + super_admin  
- [ ] password hash, register, login, me (org+plan)  
- [ ] JWT da user_id + org_id + role  
- [ ] Migrate existing brands → default org  
- [ ] Env admin → faqat bootstrap super_admin (keyin optional disable)

**Frontend**

- [ ] `/register`, login email asosida  
- [ ] session storage yangilash (user/org)  
- [ ] Landing CTA → register

**Test:** register ikki user → hali brandlar aralashmasligi Faza 2 da; lekin token farq qiladi.

### Faza 2 — Tenant isolation (majburiy, 2–3 kun) ⚠️

**Backend**

- [ ] `brands.organization_id` NOT NULL  
- [ ] Barcha list/get/patch/delete brand & sources: org filter  
- [ ] Brand name unique per org  
- [ ] Dashboard/stats/mentions endpoints org-safe  
- [ ] Super-admin bypass + audit  

**Frontend**

- [ ] Brand list faqat o‘z org  
- [ ] 403 handling  

**Test:** User A brand yaratadi; User B **ko‘rmasligi** kerak.  
**Shu faza tugaguncha public register prodga chiqarilmasin.**

### Faza 3 — Plan limits + usage (2 kun)

- [ ] Seed plan limits  
- [ ] Enforce brands/platforms/seats  
- [ ] ai_worker quota + usage_monthly  
- [ ] AI model tier by plan  
- [ ] Profile: usage bar 0–100%  
- [ ] Middleware: suspended/trial expired  

### Faza 4 — Super-admin + billing manual (1–2 kun)

- [ ] `/super-admin` UI + API  
- [ ] Assign plan, extend trial, suspend  
- [ ] `/billing` user view  
- [ ] Landing plan deep-link  

### Faza 5 — Onboarding UX (1 kun)

- [ ] Birinchi login → wizard: brand → source  
- [ ] Empty states Brand24 uslubida  

### Faza 6 — Self-serve to‘lov (2–4 kun, alohida)

- [ ] Payme/Click yoki Stripe  
- [ ] Webhooks, invoice history  

### Faza 7 — Hardening (doimiy)

- [ ] Rate limit register/login  
- [ ] Email verify  
- [ ] Worker fairness  
- [ ] Backup, audit log, GDPR delete org  

---

## 11. Fayllar (asosiy o‘zgarishlar)

| Fayl | Ish |
|------|-----|
| `backend/app/models/entities.py` | yangi jadvallar + brand.organization_id |
| `backend/app/services/auth.py` | multi-user tokens |
| `backend/app/services/tenancy.py` | **yangi** org ACL helpers |
| `backend/app/services/billing.py` | **yangi** plan/usage |
| `backend/app/main.py` | register, org routes, ACL barcha brand API |
| `backend/app/workers/ai_worker.py` | quota |
| `frontend/src/pages/Register.jsx` | **yangi** |
| `frontend/src/pages/Login.jsx` | email login |
| `frontend/src/pages/Billing.jsx` | **yangi** |
| `frontend/src/pages/SuperAdmin.jsx` | **yangi** |
| `frontend/src/pages/Landing.jsx` | CTA + plan links |
| `frontend/src/App.jsx` | routes + gates |
| `frontend/src/api/client.js` | session shape |

---

## 12. Xavflar va mitigatsiya

| Xavf | Mitigatsiya |
|------|-------------|
| IDOR / ma’lumot oqishi | Faza 2 to‘liq filter; test suite har endpoint |
| Bitta og‘ir mijoz Vertex yoqadi | hard AI quota + plan tier |
| IG/FB global unique | bir akkaunt = bir org (hujjatlashtirish) |
| Prod telegram token conflict | local worker alohida token |
| Register erta ochilsa | Faza 2 oldin feature flag `PUBLIC_REGISTER=false` |

---

## 13. Vaqt taxmini (1 dasturchi / agent)

| Faza | Taxmin |
|------|--------|
| 1 Auth foundation | 2–3 kun |
| 2 Isolation | 2–3 kun |
| 3 Plans + usage | 2 kun |
| 4 Super-admin + manual billing | 1–2 kun |
| 5 Onboarding | 1 kun |
| **MVP self-serve (to‘lovsiz)** | **~8–11 kun** |
| 6 Real to‘lov | +2–4 kun |

---

## 14. MVP “Brand24-lite” nima degani

**Kiradi:**

- Register / login  
- Org + brand isolation  
- Trial  
- Plan limit (mention AI + brands + platforms)  
- Dashboard to‘liq o‘z ma’lumotida  
- Super-admin plan beradi  
- Landing → register  

**Kirmaydi (MVP dan keyin):**

- Payme avto  
- Email verify  
- Agentlik white-label  
- Unlimited global web crawl  

---

## 15. Keyingi qadam (sizdan)

Quyidagilarni tasdiqlang — keyin **Faza 1 kod** boshlanadi:

1. **Trial:** 7 kun / 14 kun?  
2. **Trial limit:** 300 yoki 500 AI mention?  
3. **To‘lov MVP:** faqat super-admin manual?  
4. **Narx valyutasi:** UZS / USD / ikkalasi?  
5. **Public register:** Faza 2 dan keyin prodmi, yoki avval faqat local?

---

## 16. Qisqa javob savolingizga

> “Super admin tayyormi? Register login qilsam bo‘ladimi?”

**Hali yo‘q.** Hozir bitta admin.  
**Reja tayyor** — Brand24 uslubidagi to‘liq SaaS shu hujjat bo‘yicha quriladi.  
Keyingi ish: siz 15-bo‘limdagi qarorlarni bergach, **Faza 1 implementatsiya**.
