# Grok bilan ish oqimi (Reja + Tekshiruv)

Bu hujjat MonitoringAI loyihasida ikki AI agent bilan xavfsiz ishlash tartibini
belgilaydi: **Claude reja tuzadi va tekshiradi**, **Grok kod yozadi**.
Maqsad — kodlar ustma-ust chiqib ketishi, chalkashlik va regressiyani oldini olish.

---

## Rollar

| Rol            | Kim   | Nima qiladi                                             |
| -------------- | ----- | ------------------------------------------------------- |
| Rejalashtiruvchi | Claude | Aniq, o'zini-o'zi tushuntiradigan reja yozadi (quyidagi shablon) |
| Bajaruvchi     | Grok  | Faqat rejadagi qadamlarni bajaradi, kod yozadi          |
| Tekshiruvchi   | Claude | Grok tugatgach `git diff` ni tekshiradi, regressiyani ilg'aydi |

**Oltin qoida:** bitta vazifa ustida bir vaqtda faqat BITTA agent kod yozadi.
Claude hech qachon Grok bilan baravar faylni tahrirlamaydi.

---

## Sikl (har vazifa uchun)

1. **Reja** — Claude'dan reja so'raysiz. Claude quyidagi shablonni to'ldiradi va
   `docs/01-planning/` ichiga fayl qilib yozadi.
2. **Branch** — Grok yangi branch ochadi: `git checkout -b feat/<qisqa-nom>`.
3. **Bajarish** — Grok faqat rejadagi fayllar va qadamlarga tegadi. Kichik commitlar.
4. **Diff qaytarish** — Grok tugatgach, siz `git diff main...HEAD` natijasini Claude'ga
   ko'rsatasiz.
5. **Tekshiruv** — Claude loyiha xotirasi bilan tekshiradi: rejaga mos keldimi,
   eski tuzatishni buzmadimi, prod deploy'ga zid emasmi.
6. **Tuzatish yoki merge** — kamchilik bo'lsa Claude aniq tuzatish ko'rsatmasini
   beradi (yana Grok bajaradi). Toza bo'lsa — `main` ga merge.

---

## Grok uchun majburiy cheklovlar (rejaga har doim qo'shiladi)

- Faqat rejada sanab o'tilgan fayllarga teg. Boshqasiga tegish kerak bo'lsa — TO'XTA,
  sababini yoz.
- Mavjud funksiya nomlari, uslub va papka strukturasini o'zgartirma.
- Prod konfiguratsiyasi, secretlar, deploy skriptlariga TEGMA (`13.140.176.98`).
- Ishlayotgan modullarni (Instagram webhook, YouTube quota, Telegram) buzma.
- Har qadamdan keyin "bu qadam tayyorligining mezoni" bajarilganini tekshir.
- Migratsiya/DB sxemasiga tegsa — alohida commit va izoh.

---

## REJA SHABLONI (Claude to'ldiradi, Grok bajaradi)

```markdown
# Vazifa: <nom>

## Maqsad (1-2 gap)
<nima uchun, foydalanuvchiga nima beradi>

## Tegiladigan fayllar (faqat shular)
- path/to/file1 — <nima o'zgaradi>
- path/to/file2 — <nima o'zgaradi>

## TEGILMAYDIGAN joylar
- <ishlayotgan modul / prod config / secret>

## Qadamlar (tartib bilan)
1. <aniq amal — qaysi fayl, qaysi funksiya, nima qo'shiladi/o'zgaradi>
2. ...

## Tayyorlik mezoni (Definition of Done)
- [ ] <tekshirib bo'ladigan aniq natija, masalan: "endpoint 200 qaytaradi">
- [ ] Mavjud testlar o'tadi
- [ ] Yangi kod mavjud uslubga mos

## Test qilish
<qanday qo'lda yoki avtomatik sinaladi>

## Git
- Branch: feat/<nom>
- Commitlar kichik va mazmunli
```

---

## Nega bu chalkashlikni oldini oladi

- **Yagona manba:** reja repo ichida, og'zaki uzatishda ma'lumot yo'qolmaydi.
- **Bitta yozuvchi:** ustma-ust yozish jismonan mumkin emas.
- **Diff tekshiruvi:** Claude'da loyiha xotirasi bor — regressiyani ilg'aydi.
- **Branch izolyatsiyasi:** har vazifa alohida, `main` doim toza.
