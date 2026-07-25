# Dizayn yo‘nalishi — AgentOS cockpit (MonitoringAI)

> **Holat:** faqat yo‘nalish va skill. **UI/CSS o‘zgartirish HALI BOSHLANGAN EMAS.**

**Sana:** 2026-07-25 (rang siyosati yangilandi)  
**Referens tuzilmasi:** AgentOS dashboard screenshot  
**To‘liq tahlil:** `.agents/skills/design-references/agentos-dashboard-DESIGN.md`

---

## 1. Design Read

Mahsulot shell **AgentOS uslubidagi dark analytics cockpit** tuzilmasi:

- suzuvchi frame, soft pill sidebar, bento KPI’lar
- yumshoq glass panel + 1px hairline
- zich lekin nafis chartlar (ingichka stroke, dim track)

### Rang siyosati (foydalanuvchi: yashilga qulflanmasin)

| Qatlam | Qoida |
|--------|--------|
| **Neytrallar** | Sof dark gray ladder — **yashil/ko‘k/binafsha cast yo‘q** |
| **Accent** | **Bitta** brend hue — **istalgan** rang (indigo, cyan, rose, amber, emerald, …) |
| **Soft holatlar** | `accent` + opacity / `color-mix` — har qanday hue da ishlaydi |
| **Chart** | Seriya ranglari alohida; chrome bilan aralashtirilmaydi |
| **Screenshot yashili** | Faqat namunadagi bir accent misoli — **mahsulot majburiyati emas** |

---

## 2. Dial’lar

| Dial | Qiymat |
|------|--------|
| DESIGN_VARIANCE | 4–5 |
| MOTION_INTENSITY | 3–4 |
| VISUAL_DENSITY | 7–8 |

---

## 3. Majburiy o‘qish

1. `agentos-dashboard-DESIGN.md` — tuzilma + **hue-agnostic** rang
2. `raycast-DESIGN.md` — near-black + hairline
3. `stripe-DESIGN.md` — KPI
4. `design-taste-frontend/SKILL.md`
5. `dizayn-tizimi.md` — v3 draft

---

## 4. Saqlanadi

- API, auth, marshrutlar, matn ma’nosi, dual-theme g‘oyasi

---

## 5. Keyingi qadamlar

1. Foydalanuvchi qo‘shimchalari (shu jumladan **qaysi accent hue** tanlash ixtiyoriy)
2. Tokenlar → shell → chart → sahifalar (**ochiq buyruqdan keyin**)

**Hozircha pixel UI o‘zgarmasin.**
