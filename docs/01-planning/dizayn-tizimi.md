# MonitoringAI dizayn tizimi (v3 draft — AgentOS cockpit, hue-agnostic)

> **v3 status: DRAFT / NOT YET APPLIED TO CODE.**  
> Amalga oshirish faqat foydalanuvchi “dizaynni boshlaymiz” deganda.
>
> Referens: `.agents/skills/design-references/agentos-dashboard-DESIGN.md`  
> Yo‘nalish: `docs/01-planning/design-direction-agentos-cockpit.md`

---

## 1. Falsafa

**Dark neutral analytics cockpit — bitta almashtiriladigan accent (istalgan hue), glass+hairline
chuqurlik, nafis chartlar; yashilga qulflanmaydi; har karta = KPI + bitta o‘qiladigan vizual.**

---

## 2. Ranglar (draft)

### Neytrallar (fixed — hech qanday accent cast yo‘q)
- `--stage`, `--bg`, `--surface`, `--surface-raised`, `--surface-hover`
- `--border`, `--border-strong` (white alpha)
- `--text`, `--text-muted`, `--text-subtle`

### Chrome accent (bitta hue — swappable)
- `--accent` — brend hue (indigo / cyan / rose / amber / emerald / … — **tanlov erkin**)
- `--accent-hover`, `--accent-soft` (`color-mix` / opacity), `--accent-on`, `--glow-frame`
- Soft fill va CTA shu tokenlardan — shuning uchun **har qanday rang** moslashadi

### Semantic
- `--positive`, `--negative`, `--warning`, `--neutral` (+ soft)
- Har doim rang + so‘z + ikonka

### Chart (data)
- `--chart-1`…`--chart-4`, `--chart-danger`, `--chart-track`, `--chart-grid`
- Platforma: `--telegram`, `--youtube`, `--instagram`, `--facebook` (faqat data)

### Taqiqlanadi
- Mahsulotni yashilga qulflash
- Neytrallarni accent rangiga bo‘yash (green-black canvas va h.k.)
- Har kartada boshqa accent
- Pure `#000` / pure `#fff` asosiy sirt (ixtiyoriy soft ladder)

---

## 3. Shakl

| Token | Draft |
|-------|-------|
| `--radius-shell` | ~24px |
| `--radius-card` | ~16px |
| `--radius-control` | ~10px |
| `--radius-pill` | full |

Spacing 4/8; chuqurlik = ladder + hairline; KPI `tabular-nums`.

---

## 4. Patternlar

| Maqsad | Pattern |
|--------|---------|
| Sidebar active | Soft pill = `--accent-soft` |
| CTA | Solid `--accent` + `--accent-on` |
| Panel | Raised + hairline |
| KPI | Big num + delta + mini chart |
| Chart | Thin stroke, dim track |

---

## 5–7. Chart / motion / tema

- Chart nafis qoidalari saqlanadi; seriya ranglari chrome dan mustaqil.
- Motion 150–220ms; `prefers-reduced-motion`.
- Dark signature; light juft tokenlar; bo‘lim invert yo‘q.

---

## 8. Kod holati

v2 CSS hali ishlaydi. v3 faqat hujjatda.

---

## 9. Agent

- Dizayn buyrug‘isiz UI o‘zgartirma.
- Accent tanlovi ochiq bo‘lsa — neytral + bitta accent slot; **yashil majburiy emas**.
