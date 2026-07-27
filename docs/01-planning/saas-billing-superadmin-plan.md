# MonitoringAI SaaS: tarif, super-admin, multi-user, xarajat barqarorligi

**Sana:** 2026-07-27  
**Maqsad:** Landingdagi “statik” tariflarni real SaaS modelga aylantirish; Vertex xarajatini barqaror qilish; O‘zbekiston bozorida sotiladigan paketlar; super-admin + oddiy foydalanuvchi (register/login).

---

## 0. Hozirgi holat (diagnostika)

| Qism | Hozir | Muammo |
|------|--------|--------|
| Auth | Bitta `.env` admin (`admin_username` / `admin_password`) + HMAC token | Multi-tenant yo‘q; register yo‘q |
| Brand / data | `brands` global, `owner_id` yo‘q | Barcha brandlar bitta “admin”ga tegishli |
| Tarif | Faqat `Landing.jsx` da hardcode | API/DB/enforcement yo‘q |
| To‘lov | Yo‘q | Daromad avtomatlashtirilmagan |
| AI cost | 2-stage (gate flash-lite + analysis Pro), cycle limit | Tenant bo‘yicha kvota/metering yo‘q |
| Super admin | Yo‘q | Foydalanuvchi/plan/usage boshqaruvi yo‘q |

**Xulosa:** Mahsulot texnik jihatdan ishlaydi, lekin **SaaS iqtisodiyoti va multi-user qatlami** hali yo‘q. Landing narxlari marketing taxmini.

---

## 1. Vertex / Gemini real xarajat hisobi

### 1.1. Loyihadagi pipeline

1. **Gate** — `gemini-2.5-flash-lite` (arzon): brendga aloqadormi?  
2. **Analysis** — `gemini-2.5-pro` (qimmat): sentiment, risk, summary (faqat relevant).  
3. Worker: `ai_max_per_cycle=200`, `ai_concurrency=3`, cycle ~60s.

### 1.2. Model narxlari (2026, taxminiy public list)

| Model | Input / 1M tok | Output / 1M tok |
|-------|----------------|-----------------|
| Gemini 2.5 Flash-Lite | ~$0.10 | ~$0.40 |
| Gemini 2.5 Pro | ~$1.25 | ~$10.00 |

### 1.3. Bitta mention taxmini

| Bosqich | Input | Output | Cost (taxmin) |
|---------|-------|--------|----------------|
| Gate (har mention) | ~400–800 tok | ~20–50 tok | **~$0.0001** |
| Full analysis (faqat relevant) | ~800–2000 tok | ~200–400 tok | **~$0.003–0.008** |

**O‘rtacha aralash (gate pass rate 30–50% relevant deb olsak):**

- Faqat gate + 40% full analysis ≈ **$0.0015–0.004 / mention**  
- Landingdagi `VERTEX_COST_PER_MENTION = 0.025` (**2.5¢**) — **haqiqiy costdan ~5–15× balandroq** (buffer + foyda + infra).

### 1.4. Landing vs real vs tavsiya qilinadigan “sell price”

| | $/mention | 2k/oy | 6k/oy | 15k/oy | 40k/oy |
|--|-----------|-------|-------|--------|--------|
| Real Vertex (taxmin) | 0.002–0.004 | $4–8 | $12–24 | $30–60 | $80–160 |
| Landing “Vertex line” | 0.025 | $50 | $150 | $375 | $1,000 |
| Tavsiya sell AI margin | **0.008–0.012** | $16–24 | $48–72 | $120–180 | $320–480 |

**Infra base (server, Telegram, YouTube quota, Meta, support):** O‘zbekiston uchun **$25–40/oy** real, lekin sotuvda **baza $49–79** qilib foyda olinadi (global Brand24 $149+ dan arzonroq bo‘lishi kerak).

### 1.5. Muhim xulosa

- `$0.025/mention` **xarajat emas** — bu **yuqori markup**; mijozga “Vertex haqiqiy narxi” deb yozish **noto‘g‘ri / ishonchsiz**.  
- Landing matnini o‘zgartirish:  
  - ❌ “Vertex ~$X + baza $70”  
  - ✅ “Oyiga N ta AI tahlil · barcha platformalar · Telegram alert”  
  - Ichki: cost = metered; tashqi: **paket narxi** (oddiiy, UZS ham).

---

## 2. Global raqobatchilar (solishtirish)

| Mahsulot | Kirish narxi (taxmin) | Nima beradi | MonitoringAI farqi |
|----------|----------------------|--------------|-------------------|
| Brand24 | ~$149–199/oy | Ko‘p manba, AI assistant | Qimmat UZ SMB uchun |
| Mention | ~$40–599 | Simple tracking | Chala AI risk |
| YouScan | ~$499+ | Visual listening | Enterprise |
| Meltwater | $7000+/yil | Enterprise media | UZ bozoriga mos emas |

**O‘zbekiston bozori:**

- Asosiy kanallar: **Telegram, Instagram, YouTube** (Facebook ikkinchi).  
- Xaridorlar: e-com (Uzum va boshqalar), bank/fintech, oziq-ovqat, pharma, agentliklar, davlat PR.  
- To‘lov: **so‘m**, Payme/Click/Uzcard; USD faktura agentliklarga.  
- Qaror: oylik **1–5 mln so‘m** diapazoni “jiddiy SaaS”, lekin $1000/oy deyarli yo‘q (Scale faqat agentlik/korporativ).

**Pozitsiya:** “O‘zbek + RU matnni tushunadigan, Telegram-first, AI risk alert” — global tool arzonroq va mahalliyroq alternativ.

---

## 3. Tavsiya etilgan tarif modeli (O‘zbekiston)

### 3.1. Narxlash printsipi

1. **Hard limit = AI-tahlil qilingan mention / oy** (asosiy unit).  
2. **Soft features** = platforma, brend soni, seat, SLA, export.  
3. **Overage** = limitdan keyin yoki to‘xtatish, yoki +paket (50% margin).  
4. **Trial** = 7–14 kun yoki 300 free AI mention (karta ixtiyoriy keyinroq).  
5. Narx: **USD + UZS** (kurs bo‘yicha yoki fixed UZS).

### 3.2. Paketlar (tavsiya — landingni shu bilan almashtirish)

> Ichki cost buffer ~3–5× real Vertex; base infra yashirin.

| Plan | Narx (tavsiya) | AI mention/oy | Brend | Seats | Platformalar | Asosiy “sotadigan” imkoniyatlar |
|------|----------------|---------------|-------|-------|--------------|----------------------------------|
| **Start** | **$49** (~600–700k so‘m) yoki **599 000 so‘m** | 2 000 | 1 | 1 | **TG + IG** (YT optional add-on) | AI kayfiyat, email support, asosiy dashboard |
| **Growth** ★ | **$99** (~1.2–1.4 mln so‘m) | 8 000 | 2 | 3 | **TG + IG + YT** | Tezkor Telegram staff alert, risk+tavsiya, signal inbox |
| **Business** | **$249** | 25 000 | 5 | 10 | **Barcha (+ FB)** | Multi-brand, ustuvor inbox, 15 daq SLA nudge, CSV export, white-label report |
| **Scale** | **$599** yoki custom | 80 000 | 20 | 25 | Barcha + API | Agentlik multi-client, prioritet queue, dedicated onboarding, custom retention |

**Eski landing:** Start $120 / Growth $220 / Business $445 / Scale $1070 — UZ SMB uchun **baland**; conversion past bo‘ladi.  
**Yangi:** pastroq entry + aniq “nima uchun Growth” = asosiy daromad (good-better-best).

### 3.3. Har bir plandagi feature list (sotuv uchun — 5–7 bullet)

**Start** (kichik do‘kon, bloger brendi):
- Telegram + Instagram monitoring  
- 1 brend profili  
- AI kayfiyat (ijobiy/salbiy/neytral)  
- Dashboard + oxirgi mentionlar  
- Email qo‘llab-quvvatlash (48 soat)  
- 2 000 AI tahlil / oy  

**Growth** (Tavsiya — PR / o‘sayotgan brend):
- Start + **YouTube**  
- **Telegram alert** xodimlar guruhiga (reply / close)  
- Risk darajasi + AI tavsiya matni  
- Signal inbox (ustuvor salbiy)  
- 2 brend · 3 foydalanuvchi  
- 8 000 AI tahlil / oy  
- Tezroq support (24 soat)  

**Business** (agentlik / o‘rta kompaniya):
- Barcha platformalar (FB qo‘shiladi)  
- 5 brend · 10 seat  
- Ustuvor AI navbat (past planlardan oldin)  
- SLA eslatma (15–30 daq)  
- Haftalik AI hisobot (PDF/Telegram)  
- Export CSV · mention saqlash 12 oy  
- 25 000 AI tahlil / oy  

**Scale** (tarmoq / agentliklar):
- 20+ brend, 25 seat  
- API / webhook mijoz tizimiga  
- Maxsus kalit so‘z / raqobatchi to‘plamlari  
- Prioritet support + onboarding  
- 80 000 AI yoki custom  
- Maxsus shartnoma, invoice  

### 3.4. Nima “upsell” qiladi (daromad strategiyasi)

| Trigger | Harakat |
|---------|---------|
| Limit 80% | Banner: “Growth ga o‘ting” yoki “+2 000 mention paket” |
| 2-brend kerak | Growth majburiy |
| Staff Telegram alert | Growth+ |
| FB / ko‘p manba | Business |
| Agentlik 10+ brend | Scale sales call |
| Trial tugashi | 1-click Start (eng arzon) |

**Asosiy daromad:** Growth + Business (80/20).  
Scale — high-touch sales, landing CTA “Bog‘lanish”.

---

## 4. Yuqori mention / brand active bo‘lsa — xarajat boshqaruvi

### 4.1. Ha — limit **AI-tahlil qilingan mention** ga bog‘lanadi

Sabab: sizning asosiy o‘zgaruvchan xarajatingiz Vertex.  
Ingest (xom mention saqlash) arzonroq; **analysis** qimmat.

### 4.2. 3 qavatli himoya

1. **Plan hard quota**  
   - `usage.ai_analyses_month` >= `plan.ai_mention_limit` → yangi full analysis to‘xtaydi.  
   - Gate ixtiyoriy davom etishi mumkin (arzon) yoki ham to‘xtaydi.  

2. **Soft throttle**  
   - 80% → ogohlantirish (dashboard + email/TG).  
   - 100% → faqat **yuqori risk keyword** / manual “priority analyze” (Business+).  

3. **Overage policy** (tanlov, super-admin sozlaydi):  
   - A) Hard stop (Start default)  
   - B) Auto top-up paket (Growth/Business opt-in)  
   - C) Pay-as-you-go $0.01–0.015 / extra mention (margin saqlanadi)  

### 4.3. Cost optimizatsiya (texnik, foyda)

| Texnika | Ta’sir |
|---------|--------|
| Gate flash-lite majburiy | 50–70% Pro chaqiruvini yo‘qotadi |
| Spam / ignore_terms oldindan filter | AI chaqirmaslik |
| Past plan: faqat flash analysis, Pro faqat high-risk (Business+) | 5–10× arzonroq |
| Source monitoring_mode: brand_matches_only default | shovqin kamayadi |
| AI cycle + concurrency cap per tenant | burst himoyasi |
| Batching qisqa kommentlar | token kamayadi |
| Profile smart-fill Pro ni kam chaqirish (cache) | one-shot cost |

**Tavsiya default AI siyosati:**

| Plan | Gate | Full model |
|------|------|------------|
| Start | flash-lite | flash-lite (Pro yo‘q) |
| Growth | flash-lite | flash + Pro faqat risk≥0.6 |
| Business/Scale | flash-lite | Pro analysis (hozirgi sifat) |

Bu Start/Growth marjasini keskin yaxshilaydi.

---

## 5. Super admin + multi-user arxitektura

### 5.1. Rollar

| Rol | Kim | Huquq |
|-----|-----|--------|
| `super_admin` | Aviora jamoasi | Barcha tenantlar, plan, usage, feature flags, impersonate, billing override |
| `org_owner` | Mijoz egasi | Org sozlamalari, billing, a’zolar, brandlar |
| `org_admin` | Mijoz admin | Brand/source, seats (billing yo‘q) |
| `org_member` | Xodim | Dashboard, signal, o‘z brandlari (read/write policy) |
| `org_viewer` | Faqat ko‘rish | Read-only |

### 5.2. Yangi jadvallar (qisqa)

```
users (id, email, password_hash, name, role_global?, status, created_at)
organizations (id, name, plan_id, status, trial_ends_at, owner_user_id)
organization_members (org_id, user_id, role)
plans (id, code, name, price_usd, price_uzs, ai_limit, brands_limit, seats, features JSONB)
subscriptions (org_id, plan_id, status, current_period_start/end, payment_provider)
usage_monthly (org_id, year_month, ai_analyses, mentions_ingested, tokens_in, tokens_out, cost_est_usd)
brands.organization_id  -- FK qo‘shiladi (tenant isolation)
```

### 5.3. Super-admin UI (minimal MVP)

Route: `/super-admin` (faqat `super_admin`).

- Foydalanuvchilar / org ro‘yxati  
- Plan biriktirish / trial uzaytirish  
- Usage (AI count, taxminiy cost)  
- Org to‘xtatish / ban  
- Feature flags  
- “Login as org” (impersonate, audit log)

### 5.4. Public auth oqimi

```
Landing → Register (email+parol+org nomi) → email verify (ixtiyoriy P1) 
  → Trial Start plan → Dashboard (bo‘sh, onboarding)
Landing → Login → Dashboard
Super admin: alohida yoki bir xil login + role check
```

Mavjud `.env` admin → birinchi `super_admin` user ga migrate.

### 5.5. Tenant isolation (majburiy)

Har API: `org_id` JWT da; barcha brand/source/mention querylari `organization_id` filter.  
Workers: brand → org → plan quota tekshiruvi analysis oldidan.

---

## 6. To‘lov (O‘zbekiston)

**Faza 1 (tez):**  
- Manual: super-admin plan beradi (invoice / Payme link chatda).  
- Register → trial → “Tarifni tanlash” → “To‘lov qilindi” super-admin tasdiqlaydi.

**Faza 2:**  
- Payme / Click merchant API.  
- Status webhook → `subscription.active`.

**Faza 3:**  
- Auto-renew, invoice PDF, UZS/USD.

---

## 7. Bosqichma-bosqich implementatsiya (PR rejasi)

### PR1 — Foundation (1–2 kun)
- `users`, `organizations`, `plans`, `usage_monthly`  
- Password hash (bcrypt/argon2)  
- Register / login / JWT (`sub=user_id`, `org_id`, `role`)  
- Super-admin seed  
- Brandga `organization_id` (mavjud data → default org)

### PR2 — Enforcement (1–2 kun)
- Plan limits: brands, seats, platforms, AI quota  
- AI worker: quota check + usage increment  
- Dashboard banner 80%/100%  
- Start plan: Pro o‘rniga flash analysis (cost)

### PR3 — Super-admin UI + Plan UI
- `/super-admin`  
- Profile: joriy plan, usage progress bar  
- Landing: yangi narxlar + feature list (DB yoki config)  
- CTA: Register with `?plan=growth`

### PR4 — Billing soft
- Manual activate / extend  
- Overage policy flags  
- Audit log

### PR5 — Payme/Click
- Real to‘lov

**Hozir kod yozish tartibi:** PR1 → PR2 → PR3 (daromad va barqarorlik uchun minimal to‘liq zanjir).

---

## 8. Landing matn / CTA o‘zgarishlari (qisqa)

- “Dashboard” tugmasi o‘rniga unauth: **“7 kun bepul”** / **“Ro‘yxatdan o‘tish”**.  
- Growth **Tavsiya** saqlanadi.  
- Narx ostida: “oyiga N ta AI tahlil · M brend”.  
- “Vertex $0.025” matnini olib tashlash.  
- Contact: Scale va maxsus.

---

## 9. Muvaffaqiyat mezonlari

| Metrika | Maqsad |
|---------|--------|
| Gross margin (AI+infra) | ≥ 60% o‘rtacha |
| Trial → paid | ≥ 15% (UZ B2B) |
| Growth share of paid | ≥ 50% |
| AI cost spike | tenant hard limit ishlaydi |
| Super-admin | 0 daqiqa SSH bilan plan o‘zgartirish |

---

## 10. Keyingi amal

1. Ushbu hujjatni tasdiqlash (narxlar UZS/USD, trial kunlari).  
2. PR1 implementatsiyasini boshlash.  
3. Landing `PLANS` ni yangi raqamlar + feature keys bilan yangilash (hatto billing oldin ham marketing to‘g‘ri bo‘lsin).

**Qaror kerak bo‘lgan savollar (qisqa):**
- Narx valyutasi: asosan **UZS**mi yoki **USD**?  
- Trial: **7** yoki **14** kun?  
- To‘lov: hozir **manual super-admin** yetadimi yoki darhol Payme?  
- Mavjud bitta admin + brandlar: bitta “Aviora internal” org sifatida qoladimi?
