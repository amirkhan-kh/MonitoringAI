# Design references (vendored)

Bu papkadagi `*-DESIGN.md` fayllar — MonitoringAI redizayni uchun **konkret token tizimi
namunalari**. Ular Grok/Claude dizayn ishlaganda "qanday ko'rinishga intilamiz" degan
savolga aniq javob beradi (surface ladder, hairline border, radius, accent intizomi,
tipografiya).

## Fayllar va nega olindi
- `raycast-DESIGN.md` — **dark-first chuqurlik** namunasi. Pure near-black kanvas, surface
  ladder (#07080a → #0d0d0d → #101111), 6–10px radius, 1px hairline border, kam va nuqtali
  accent. MonitoringAI'ning dark-first shell'i uchun asosiy ilhom.
- `vercel-DESIGN.md` — **minimalist border+token** namunasi. Kartalarni shadow emas, 1px
  border bilan ajratish; bitta neutral kulrang shkala + bitta accent.
- `stripe-DESIGN.md` — **KPI/metrika kartasi va dashboard shell** namunasi. Katta raqam +
  trend delta + tabular-figure; dashboard qismida dark shell'ga o'tish.

## Manba va litsenziya
Manba: https://github.com/VoltAgent/awesome-design-md (MIT). 2026-07-24 da olindi.
Bu fayllar **referens** (o'qib ilhom olish uchun), ijro etiladigan kod emas.

## Qanday ishlatiladi
Dizayn brifidagi ([[../../../docs/01-planning/grok-brief-01-dizayn.md]]) yo'nalish bilan
birga o'qing. Bularni ko'r-ko'rona nusxalamang — MonitoringAI'ning o'z brend identifikatsiyasi
(indigo→pink→cyan gradient) saqlanadi, bu fayllardan faqat *tamoyil* (chuqurlik, intizom,
tipografiya) olinadi.
