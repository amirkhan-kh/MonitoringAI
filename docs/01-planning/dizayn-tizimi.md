# MonitoringAI dizayn tizimi (v2 — reference-dashboard sintezi)

> Bu — **majburiy** dizayn qo'llanmasi. UI'ga har qanday yangi qo'shimcha (yangi sahifa,
> karta, chart, modal, tugma) **aynan shu tokenlar va patternlar** asosida qilinadi —
> har piksel. Ad-hoc rang/o'lcham/soya YOZMANG; hamma narsa token orqali.
> Manba estetikasi: Coursue (#2), Twisty (#3), Financial (#4), Stakert (#5),
> Phoenix (#6), Codenome (#7), nixito (#8) dashboardlari.

## 1. Falsafa (bir jumla)
**Yumshoq, shishasimon (glass), binafsha-urg'uli, gradient-boyitilgan, ma'lumot-zich
dashboard — dark va light'da ham ko'zни quvnatadigan, LEKIN rangbarang emas.** Bitta accent
(indigo/violet); gradient faqat signature lahzalarda; chuqurlik = glass + nozik border + yumshoq glow.

## 2. Ranglar (faqat token, hex yozmang)
- **Accent (bitta):** `--accent` (light `#6366f1`, dark `#7c83ff`), `--accent-hover`, `--accent-soft`.
- **Signature gradient (kam ishlatiladi):** `--gradient-hero`, `--gradient-violet`, `--brand-gradient`
  — faqat: logo, Landing hero, asosiy CTA, promo/upgrade karta, bitta "hero" stat.
- **Sirtlar:** `--bg`, `--surface`, `--surface-raised`, `--surface-soft`; glass uchun
  `--glass-bg`, `--glass-bg-strong`, `--glass-border`, `--glass-hairline`, `--glass-highlight`.
- **Matn:** `--text`, `--text-muted`, `--text-subtle`. Past-kontrast kulrang matn **taqiqlanadi**
  (WCAG AA: matn 4.5:1, UI/chart 3:1).
- **Sentiment/risk (barqaror ma'no, hech qачон kategoriya rangi emas):** `--positive`, `--neutral`,
  `--negative`, `--warning` (+ `-soft` variantlari). Har doim **rang + so'z + ikonka** birga.
- **Platforma identifikatsiyasi (faqat chart/badge):** `--telegram`, `--youtube`, `--instagram`,
  `--facebook`, `--signal`.

## 3. Shakl / bo'shliq / chuqurlik
- **Radius:** `--radius-sm 10` (control), `--radius-md 14` (list qator, kichik karta),
  `--radius-lg 20` (panel/karta), `--radius-xl 26` (hero), `--radius-pill`. SHAPE LOCK — aralashtirmang.
- **Spacing:** 4/8 shkala — `--space-1..8`. Ixtiyoriy px yozmang.
- **Chuqurlik:** `--shadow` (yumshoq ambient), `--shadow-soft`, `--shadow-float` (suzuvchi:
  modal/popover/tooltip), `--glow-accent`/`--glow-soft` (signature accent nuri). Dark'da pure-black
  emas, yumshoq.
- **Type shkala:** `--text-xs..2xl`. Ierarxiya o'lcham EMAS, og'irlik+rang bilan. Raqamlarga
  `font-variant-numeric: tabular-nums` (KPI, chart o'qi).

## 4. Komponent patternlari (mavjud klasslarni ishlating)
| Maqsad | Klass / komponent | Izoh |
|---|---|---|
| Panel / karta | `.panel` | Glass + blur + hairline + radius-lg. Barcha asosiy kartalar. |
| KPI / metrika | `.statCard` | Gradient tint (`nth-child` 1–4), glass, hover glow. Katta tabular raqam. |
| List qatori | `.sourceCard` / `.mentionItem` | Solid (perf: blur yo'q), radius-md, hover lift. |
| Gradient hero / promo | `.gradientHero` | Signature gradient + ichki sheen. Landing/upgrade. |
| Ikonka chip | `.iconChip` | Tinted kvadrat + accent ikonka (refs #2/#3). |
| Chart | `<MentionTrendChart>` / `<PlatformTrendChart>` | Recharts, gradient area (#8 uslubi). |
| Chart shell/tooltip | `.chartShell`, `.rechartsTooltip` | Barcha chartlar shu theming'ga bo'ysunadi. |
| Sidebar toggle | hamburger `Menu` ↔ `X` | `.sidebarToggleIcon` animatsiya. |
| Theme toggle | `Sun` ↔ `MoonStar` | `.themeToggleIcon` pop-in animatsiya. |

## 5. Ikonkalar
- Kutubxona: **lucide-react** (bitta oila). Oddiy/bo'sh ikonка qo'ymang — mazmunли tanlang.
- `strokeWidth` standart (lucide default). Ikonkalar tinted `.iconChip` ichida yoki accent rangda.

## 6. Chartlar (Recharts — custom SVG YOZMANG)
- Trend/vaqt qatori → `MentionTrendChart` (total = gradient area, platformalar = ingichka chiziq)
  yoki `PlatformTrendChart` (bitta gradient area).
- Yangi chart turi kerak bo'lsa: Recharts ishlating, ranglarni **CSS o'zgaruvchisi** orqali bering
  (`stroke="var(--chart-line)"`, gradient `stopColor="var(--chart-area-from)"`) — shunda dark/light
  avtomatik moslashadi. Grid `--chart-grid`, o'q `--chart-axis`, tooltip `.rechartsTooltip`.
- Chart turlari g'oyaga mos: area (trend), donut/radial (ulush), horizontal bar (reyting),
  konsentrik halqa (nested total). Pie'ni vaqt qatori uchun ishlatmang. 3D/chartjunk taqiqlanadi.

## 7. Motion
- CSS-first: `--duration-fast 160 / base 220 / slow 300`, `--ease-smooth`. Hech narsa >320ms.
- Motion (`motion/react`) faqat: Landing reveal, hero, maxsus mikro-interaksiya.
- Har animatsiya oqlanadi (ierarxiya/feedback/state). `prefers-reduced-motion` hurmat qilinadi.

## 8. Tema
- Dual-theme: `data-theme="dark|light"` (`src/theme.js`). Dark = signature, light to'liq qo'llab.
- Har token ikkala temada aniqlangan bo'lishi SHART. Bo'lim o'rtasida tema invert bo'lmaydi.

## 9. Qat'iy YO'Q
- Rangbarang/garish UI, ko'p rangli AI-mesh gradient fon, har kartada boshqa accent.
- Past-kontrast matn, faqat-rang bilan sentiment, custom SVG chart, aralash radius, >320ms animatsiya.
- Logika o'zgartirish (API/endpoint/maydon nomi/data oqimi/locale kalit) — bu dizayn qatlami.

---
**Amalda:** yangi UI qo'shganda → mos `.panel/.statCard/.gradientHero` + tokenlar + Recharts +
lucide ikonka + `prefers-reduced-motion`. Shubha bo'lsa — shu hujjatga qayting.
