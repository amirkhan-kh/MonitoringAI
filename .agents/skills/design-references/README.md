# Design references (vendored + project north star)

Bu papkadagi `*-DESIGN.md` fayllar — MonitoringAI redizayni uchun **konkret token tizimi
namunalari**. Ular agent dizayn ishlaganda "qanday ko'rinishga intilamiz" degan savolga
aniq javob beradi.

## Ustuvorlik (2026-07-25)

| Ustunlik | Fayl | Nima uchun |
|----------|------|------------|
| **1 — PRIMARY (product shell)** | `agentos-dashboard-DESIGN.md` | AgentOS screenshot **tuzilmasi** + **hue-agnostic** rang: neytral dark gray ladder, bitta almashtiriladigan accent (yashil majburiy emas). |
| 2 | `raycast-DESIGN.md` | Near-black surface ladder, hairline, radius intizomi. |
| 3 | `stripe-DESIGN.md` | KPI: katta raqam + delta + tabular-nums. |
| 4 | `vercel-DESIGN.md` | Marketing light minimal (Landing/legal yordamchi). |

## Qisqa xulosa — AgentOS (PRIMARY)

- Dark **neytral** sirt zinalari (yashil cast yo‘q — har qanday accentga mos).
- Chrome uchun **bitta accent token** (indigo/cyan/rose/amber/emerald/… — tanlov erkin).
- Soft holatlar = accent + opacity/`color-mix` → barcha ranglarga mos.
- Multi-rang faqat chart seriyalarida; platforma ranglari faqat data.
- Panel = raised + hairline; KPI = katta raqam + delta + mini-chart.
- Dial’lar: variance 4–5, motion 3–4, density 7–8.

## Manba va litsenziya

- `raycast` / `vercel` / `stripe`: https://github.com/VoltAgent/awesome-design-md (MIT), 2026-07-24.
- `agentos-dashboard-DESIGN.md`: foydalanuvchi screenshotidan **original tahlil** (2026-07-25).
  Bu fayllar **referens** — ijro etiladigan kod emas.

## Qanday ishlatiladi

1. `docs/01-planning/design-direction-agentos-cockpit.md` — joriy yo‘nalish brifi.
2. `docs/01-planning/dizayn-tizimi.md` — v3 draft tokenlar (**kodga hali yozilmagan**).
3. `.agents/skills/design-taste-frontend/SKILL.md` — anti-slop + **Dashboard / AgentOS** bo‘limi.
4. **UI o‘zgartirishni boshlama** — foydalanuvchi qo‘shimcha brif beradi va ochiq buyruq beradi.

Bularni ko‘r-ko‘rona nusxalamang. MonitoringAI brendi (ma’lumot, platformalar, o‘zbekcha
matn ma’nosi) saqlanadi; AgentOS dan **tamoyil va estetik intizom** olinadi.
