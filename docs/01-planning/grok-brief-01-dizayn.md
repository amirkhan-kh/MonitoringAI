# Grok brifi #01 — MonitoringAI UI/UX redizayn (creative-minimalist, dark-first)

> Bu brif [[grok-ish-oqimi]] qoidalariga muvofiq yozilgan. **Claude rejalashtirdi va tekshiradi,
> Grok bajaradi.** Grokda loyiha xotirasi YO'Q — shuning uchun bu brif o'zini-o'zi to'liq
> tushuntiradi. Har fazadan keyin Grok TO'XTAB, diff'ni tekshiruvga qaytaradi.

---

## 0. DESIGN READ (bir qatorda)

**"Bu — brendni ijtimoiy tarmoqlarda kuzatuvchi SaaS *operatsion dashboard*, kun bo'yi ishlatiladi;
til — Linear/Raycast/Vercel uslubidagi dark-first minimalizm; poydevor — semantik dual-theme token
tizimi + shadcn/Radix patternlari + o'lchovli (restrained) Motion."**

Bu **landing sahifa yoki portfolio EMAS** — bu ma'lumot zich dashboard. Shuning uchun `taste-skill`ning
anti-slop *tamoyillari* (rang/tipografiya/motion intizomi, holatlar, WCAG) to'liq qo'llaniladi, lekin
uning "hero/landing" *maketlash qoidalari* faqat `Landing.jsx` sahifasiga tegishli.

### Dial'lar (dashboard uchun sozlangan)
- `DESIGN_VARIANCE: 5` — o'ylangan, tartibli; badiiy xaos emas (bu ish quroli).
- `MOTION_INTENSITY: 4` — maqsadli, qisqa spring micro-interaction; hech qачон bezak uchun emas.
- `VISUAL_DENSITY: 6` — dashboard uchun **zichlik — bu afzallik**; bir ko'rinishda 5–9 asosiy element.

---

## 1. MAQSAD va OLTIN QOIDA

**Maqsad:** hozirgi "sodda/tekis" interfeysni **creative-minimalist, zamonaviy, hayratlanarli**
UI/UX ga aylantirish — foydalanuvchi "vouv, juda go'zal va tushunarli" desin. Go'zallik + mutlaq
qulaylik + aniqlik birga.

**OLTIN QOIDA (buzilishi = ish rad etiladi):** bu **faqat vizual/UX qatlam** redizayni.
Loyiha *logikasi*, ma'lumot oqimi, API kontrakti, biznes-mantiq, endpointlar, auth,
o'zbekcha matn *ma'nosi* — HAMMASI o'zgarishsiz qoladi. Sen faqat ko'rinishni (CSS + JSX markup)
qayta ishlaysan. Batafsil "TEGILMAYDIGAN" bo'limiga qara (§6).

---

## 2. QOTIRILGAN QARORLAR (foydalanuvchi tasdiqladi)

1. **Dark-first + light toggle.** Asosiy "signature" tajriba — dark. Light rejim ham TO'LIQ
   ishlaydi. Foydalanuvchi toggle bilan almashtiradi; tanlov `localStorage`da saqlanadi;
   birinchi tashrifda `prefers-color-scheme`ga qarab boshlanadi.
2. **Fazma-faz, yuqori ta'sirdan.** Avval poydevor + eng ko'p ko'riladigan ekranlar, so'ng
   tekshiruv, keyin qolganlari (§5).

---

## 3. HOZIRGI HOLAT (Grok bilishi shart)

- **Stack:** React 18 + Vite, qo'lda yozilgan (no router — `App.jsx` sahifalarni switch qiladi;
  no state lib; **custom SVG chartlar**). Bitta katta `frontend/src/styles.css` (~6485 satr) —
  kuchli, lekin light-only token tizimi. UI matni o'zbekcha (`src/locales.js` + `src/i18n.js`).
- **Auth REAL:** login/token oqimi `src/api/client.js` orqali (localStorage `monitoring_admin_session`,
  Bearer token, 401 → /login). Buni sindirmaslik hayotiy muhim.
- **Prod:** SPA `/api` ga murojaat qiladi; static nginx orqali beriladi.
- **Font:** Inter, `frontend/index.html`da Google Fonts `<link>` orqali (prod'da yaxshi emas → self-host).
- **Joriy tokenlar (light-only, `:root`da):** `--bg #f7f8fc`, `--surface #fff`, `--ink #111827`,
  `--muted #7b8494`; accent'lar tarqoq: `--teal #342e89` (aslida to'q indigo, nomi chalg'ituvchi),
  `--blue #27c5dc` (cyan), `--violet #ff5bbd` (pink), `--amber #f7b731`, `--red #f05b72`;
  brend gradient = indigo→pink→cyan (135deg); fon radial "glow"lar bilan gradient-og'ir.
  Radius 8/12/16; skeleton loader'lar bor. Platforma ranglari: telegram/youtube/instagram/facebook.
- **Kuzatilgan muammolar:** app light / Landing dark (nomuvofiqlik); komponentlar tekis va templated;
  Landing = generic hero + 3×2 "icon+matn" karta grid (vizual yo'q, motion yo'q); accent palitra
  tarqoq; fon gradient-og'ir ("AI glow" xavfi).

---

## 4. REFERENS MATERIALLAR (ish boshlashdan OLDIN o'qi)

1. `.agents/skills/design-taste-frontend/SKILL.md` — anti-slop tamoyillari (§4 Design Engineering
   Directives, §4.5 Interactive States, §4.2 Color, §4.1 Typography). Landing uchun to'liq; dashboard
   uchun faqat tamoyillar.
2. `.agents/skills/design-references/raycast-DESIGN.md` — **dark-first chuqurlik** (surface ladder,
   hairline border, radius, kam accent). Bizning dark shell'imizning asosiy ilhomi.
3. `.agents/skills/design-references/vercel-DESIGN.md` — border+token minimalizmi.
4. `.agents/skills/design-references/stripe-DESIGN.md` — KPI/metrika kartasi anatomiyasi.
5. Chart/vizualizatsiya qilishdan OLDIN — `dataviz` skill'ini yukla (rang, o'q, kontrast qoidalari).

---

## 5. GLOBAL DIZAYN TIZIMI (poydevor — Faza 1 ning yuragi)

Bu tizim bir marta quriladi va hamma joyda ishlatiladi. **Hech narsani ad-hoc yozma — token orqali.**

### 5.1 Dual-theme semantik token tizimi
Joriy `:root`dagi *xom* ranglarni **semantik** tokenlarга aylantir va HAR IKKALA tema uchun aniqla.
Semantik nom (rol), xom rang emas:
```css
:root {                     /* LIGHT — hozirgidan evolyutsiya */
  --bg: …; --surface: …; --surface-raised: …; --border: …; --border-strong: …;
  --text: …; --text-muted: …; --text-subtle: …;
  --accent: #6366f1;        /* BITTA asosiy accent — indigo (index.html theme-color bilan mos) */
  --accent-hover: …; --accent-contrast: #fff;
  /* sentiment/risk — §5.4 */
}
:root[data-theme="dark"] {  /* DARK — signature; Raycast-uslub surface ladder */
  --bg: #0a0b0d; --surface: #121316; --surface-raised: #17181c;
  --border: #23252b; --border-strong: #2e3138;
  --text: #f2f3f5; --text-muted: #a2a7b0; --text-subtle: #6b7280;
  --accent: #7c83ff; …       /* dark'da accent biroz yorqinroq (kontrast uchun) */
}
```
- **Chuqurlik = elevation + hairline border**, PURE-BLACK shadow emas. Kartalar = raised surface + 1px
  border. Faqat *suzuvchi* narsalar (Cmd-K overlay, toast, popover) yumshoq ko'p qatlamli shadow oladi.
  Shadow rangi fon rangiga tinting qilinadi.
- **Brend gradient (indigo→pink→cyan) faqat SIGNATURE lahzalar uchun:** logo mark, Landing hero,
  asosiy CTA. UI bo'ylab sepilmaydi. Boshqa hamma joyda BITTA accent (indigo).
- Fondagi "AI glow" radial gradientlarni kamaytir — dark'da atmosferani near-black + juda nozik
  bitta accent nafas bilan ber, ko'p rangli mesh emas.

### 5.2 Tipografiya
- **Inter Variable'ni self-host qil** (`@font-face` + `font-display: swap`), `index.html`dagi Google
  Fonts `<link>`ni olib tashla. Ixtiyoriy: raqam/texnik yorliqlar uchun bitta mono (Geist Mono /
  JetBrains Mono).
- **Modulyar shkala:** 12/14/16/20/28/40 (yoki shunga yaqin), token orqali.
- **Ierarxiya — o'lcham EMAS, balki og'irlik+rang bilan** (Refactoring UI tamoyili). Katta raqam/sarlavhaga
  tight tracking (~ -0.01…-0.02em).
- **`font-variant-numeric: tabular-nums`** — BARCHA KPI, chart o'qi, raqamli qiymatlarga (ma'lumot
  yangilanganda raqamlar sakramasin).

### 5.3 Bo'shliq / radius / shakl
- **4/8px spacing shkala**, token orqali; ixtiyoriy qiymat yo'q.
- **Radius:** 2–3 pog'ona (masalan 8 / 12 / 999px pill). SHAPE LOCK: sahifa bo'ylab bitta radius tizimi
  (taste-skill §4.4). Aralash tizim faqat hujjatlashtirilgan qoida bilan.

### 5.4 Sentiment / risk — semantik va REDUNDANT kodlash
- Sabit semantik ranglar, HAR chartda BIR XIL: `--positive` (yashil/teal), `--neutral` (slate),
  `--negative` (amber→red). Risk darajalari uchun alohida pog'onali shkala.
- **Hech qачон faqat rang bilan emas** (WCAG + rang-ko'rlik): har sentiment/risk = rang + **so'z** +
  **ikonka/shakl**. Masalan sentiment chip = rangli fon + "Ijobiy" + ikonka. Rang *ma'nosi* barqaror
  (qizil = yomon HAMMA joyda, hech qачон shunchaki "kategoriya" emas).

### 5.5 Motion tizimi
- **CSS-first:** micro-interaction'lar (hover lift, chip state, row hover, tab o'tishi) `transition` +
  `@keyframes` bilan — kodbaza allaqачон CSS-og'ir. Uzunlik: tugma 160–220ms, karta/panel 220–320ms.
  Hech narsa ~320ms dan uzun emas.
- **Motion (`motion/react`) faqat kerak joyda:** Landing hero `whileInView` reveal, va agar Cmd-K
  palitrasi qo'shilsa — spring o'tish. `package.json`ni tekshir, yo'q bo'lsa install buyrug'ini
  ko'rsat. Har bir animatsiya BIR jumlada oqlanishi kerak (motion must be motivated). Bezak uchun
  animatsiya = fail.
- **`prefers-reduced-motion: reduce`** — barcha animatsiyani o'chir/kamaytir. Majburiy.

### 5.6 Holatlar (to'liq sikl — taste-skill §4.5)
- **Loading:** skeleton (yakuniy maketning shakliga mos) — spinner emas. (Ba'zilari bor, hammasini qamra.)
- **Empty:** chiroyli tuzilgan bo'sh holat + "qanday to'ldirish" bo'yicha bitta aniq keyingi qadam.
- **Error:** aniq, kontekstli (inline/toast).
- **Focus:** aniq `:focus-visible` ring (2px accent, offset) — HAR interaktiv elementda; klaviatura bilan
  to'liq yurish mumkin (kun bo'yi ishlatiladigan tool).
- **Tactile:** `:active`da `translateY(1px)` yoki `scale(0.98)`.

---

## 6. TEGILMAYDIGAN (qat'iy chegara — "logikani buzma")

- ❌ `backend/` — umuman tegma.
- ❌ `frontend/src/api/client.js` — bu logika (auth token, fetch, SSE). Tegma. (Faqat u chaqiradigan
  vizual komponentlar o'zgaradi.)
- ❌ **API endpoint yo'llari, so'rov/javob maydon nomlari** — o'zgartirma (masalan `risk_score`,
  `sentiment`, `brand_id`). UI ularni ko'rsatadi, qayta nomlamaydi.
- ❌ **Ma'lumot oqimi va state shakli** — `useState`/`useEffect`/`fetch`/SSE mantig'i, event handler'lar
  o'zgarmaydi. Faqat markup + className.
- ❌ **Komponentlararo prop kontraktlari** — agar bir prop nomini o'zgartirsang, uni CHAQIRUVCHI hamma
  joyni ham yangilashing shart (aks holda tegma).
- ❌ `src/locales.js` / `i18n.js` **kalitlarini** qayta nomlama yoki o'chirma. Yangi kalit QO'SH mumkin.
  O'zbekcha matn *ma'nosi* saqlanadi (faqat aniq yaxshilanish bo'lsa va ma'no to'g'ri qolsa — so'zni
  sayqallash mumkin).
- ❌ `src/navigation.js` route kalitlari, auth gate mantig'i (`App.jsx`dagi `isAuthed()`), deploy
  konfiguratsiyasi, secretlar.
- ❌ Prod/deploy fayllari (`docker-compose*.yml`, `deploy/`, `.env*`).

**Ruxsat (TEGILADI):** `frontend/index.html`, `frontend/src/styles.css`, `frontend/src/**/*.jsx`
(faqat markup/className/struktura), yangi `frontend/src/theme.js` (theme toggle), self-host font
fayllari, `package.json`ga faqat kelishilgan kutubxona (Motion) — o'rnatish buyrug'ini ko'rsatib.

---

## 7. FAZALAR

### FAZA 1 — Poydevor + yuqori ta'sirli ekranlar  → keyin TO'XTA, tekshiruv
**Tegiladigan fayllar:**
- `frontend/src/styles.css` — §5 global token tizimi (dual-theme, tipografiya, spacing, elevation,
  sentiment, motion, holatlar). Bu ildiz o'zgarishi HAMMA sahifaga ta'sir qiladi — shuning uchun
  additive va ehtiyotkor.
- Yangi `frontend/src/theme.js` + `frontend/index.html` (self-host font, theme init, `<link>` olib
  tashlash, `data-theme` boshlang'ich).
- `frontend/src/components/Sidebar.jsx` + topbar/`PageHeader.jsx` — **shell** (navigatsiya, logo,
  theme toggle, foydalanuvchi/chiqish). Butun app ramkasi.
- `frontend/src/pages/Landing.jsx` — **front door**. Bu yerda taste-skill TO'LIQ qo'llaniladi: hero'ga
  real vizual/kompozitsiya (faqat matn+gradient blob emas), generic 3×2 karta grid'ini rhythmli
  bento/aралash maketga aylantir, `whileInView` reveal. Dark tema (Landing allaqачон dark).
- `frontend/src/pages/Dashboard.jsx` (+ `StatsBar.jsx`, `MonitoringInsights.jsx`, `RecentMentions.jsx`,
  custom SVG chart bloklari) — **Stripe-uslub KPI qatori** (katta raqam + trend delta + tabular
  sparkline + bitta muted yorliq), Linear-uslub siqilgan qatorlar, elevation+hairline kartalar,
  sabit semantik chart ranglari.

**Faza 1 Tayyorlik mezoni (DoD):**
- [ ] Dark VA light — ikkalasi ham to'liq ishlaydi; toggle + localStorage + `prefers-color-scheme` init.
- [ ] Barcha matn WCAG AA (4.5:1), UI/chart elementlari 3:1. Past-kontrast "estetik kulrang" yo'q.
- [ ] Sentiment/risk redundant kodlangan (rang + so'z + ikonka).
- [ ] `prefers-reduced-motion` hurmat qilinadi; animatsiya ≤320ms.
- [ ] Mavjud oqimlar ISHLAYDI: login, sahifa almashish, ma'lumot yuklanishi, real-time yangilanish,
      source qo'shish/o'chirish modallari — hech biri sinmagan.
- [ ] `npm run build` xatosiz; konsولда error yo'q.
- [ ] Boshqa (hali redizayn qilinmagan) sahifalar yangi tokenlarni meros olib ham SINMAGAN ko'rinadi.

→ **TO'XTA. `git diff main...HEAD` ni Claude'ga qaytar.** Claude tekshiradi, keyin Faza 2.

### FAZA 2 — Qolgan ekranlar (Faza 1 tasdiqlanganidan keyin)
`TelegramMonitoring.jsx`, `YoutubeMonitoring.jsx`, `InstagramMonitoring.jsx`, `FacebookMonitoring.jsx`,
`SignalInbox.jsx`, `SourceBoard.jsx`, `SourceForm.jsx`, `SmartSelect.jsx`, `TelegramConnectionForm.jsx`,
`BotFatherGuideModal.jsx`, `DeleteSourceModal.jsx`, `Profile.jsx`, `Login.jsx`, `Legal.jsx`,
`BrandIcons.jsx`. Faza 1 token tizimi va patternlarini qo'lla. Ixtiyoriy: Linear-uslub `Cmd-K` palitra.
DoD — Faza 1 bilan bir xil, har sahifa uchun.

---

## 8. GROK UCHUN MAJBURIY CHEKLOVLAR

- Har fazani **alohida branch**da bajar: `feat/redesign-phase-1`, so'ng `feat/redesign-phase-2`.
- Kichik, mazmunli commitlar. Har fazadan keyin TO'XTA va diff'ni qaytar (§7).
- Faqat §6da ruxsat berilgan fayllarga teg. Boshqasi kerak bo'lsa — TO'XTA, sababini yoz.
- Kutubxona qo'shishdan oldin `package.json`ni tekshir, `npm install` buyrug'ini ko'rsat.
- **Ish boshlashdan oldin AUDIT:** §4 referenslarni o'qi, keyin kod bo'ylab yur (komponent → ekran
  xaritasi), so'ng bir qatorli "Design Read" ni tasdiqlab yoz, keyin yoz. Default estetikaga sakrama.
- Custom SVG chartlarni qayta yozganда — hisob-kitob/ma'lumot mantig'ini emas, faqat vizualni (rang,
  o'q, grid, label, radius) o'zgartir.
- Ship'dan oldin **COPY SELF-AUDIT** (taste-skill §4.9): har ko'rinadigan o'zbekcha satrni qayta o'qi —
  grammatik xato, noaniq, "AI-cute" matnni tuzat yoki oddiy funksional gapga almashtir.

---

## 9. PRE-FLIGHT CHECKLIST (har faza ship'idan oldin)
- [ ] Bitta accent butun sahifada (indigo); gradient faqat signature lahzalarda.
- [ ] Bitta radius tizimi; bitta tema (dark yoki light) — bo'lim o'rtasida invert bo'lmaydi.
- [ ] Tugma matni bitta qatorda, kontrast AA; empty/loading/error/focus holatlari bor.
- [ ] `tabular-nums` barcha raqamlarda; skeleton yakuniy maketga mos.
- [ ] Motion oqlangan va ≤320ms; `prefers-reduced-motion` ishlaydi.
- [ ] Mavjud funksionallik sinmagan (§7 DoD); build toza.

---

**Qisqa formula:** dark-first semantik tokenlar → elevation+hairline chuqurlik (Raycast/Vercel) →
Stripe-uslub KPI qatori (tabular sparkline) → Linear-uslub siqilgan qatorlar → qisqa CSS/spring
micro-interaction → redundant WCAG-AA sentiment/risk. Logika daxlsiz, o'zbekcha matn saqlangan,
fazma-faz, har fazadan keyin tekshiruv.
