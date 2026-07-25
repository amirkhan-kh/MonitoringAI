# ECharts migratsiya — MonitoringAI chartlar

> **Holat:** Recharts olib tashlandi; asosiy trend chartlar **Apache ECharts** ga ko‘chirildi.  
> Keyingi chart turlari: foydalanuvchi **nom bilan** aytadi → shu nom bo‘yicha ECharts series/type tanlanadi.

## 1. Litsenziya

| | |
|--|--|
| **Apache ECharts** | Apache License 2.0 — **tekin** (tijoriy ham) |
| **Rasmiy sayt** | https://echarts.apache.org/en/index.html |
| **React wrapper** | `echarts-for-react` |

## 2. Hozirgi chartlar (kod)

| UI joyi | React export | ECharts turi (hozir) | Data prop |
|---------|--------------|----------------------|-----------|
| Umumiy dashboard — «Platform ulushi» | `PlatformShareChart` | `pictorialBar` peaks + logo | platform totals |
| Umumiy dashboard — trend (agar kerak) | `MentionTrendChart` | `line` + area gradient | `rows[]` |
| Dashboard — platform kartalar (TG/YT/IG/FB) | `PlatformTrendChart` | `line` + area gradient | `rows[]` + `series` |
| Umumiy dashboard — AI ishonchlilik / AI qamrov | `PercentGauge` | `gauge` (yarim doira) | `value` 0–1 yoki 0–100 |
| Platform insights — Production / Mention | raqam + meter | (gauge emas) | counts / ratio |
| Platform insights — AI qamrov | `PercentGauge` | `gauge` | coverage |
| Platform insights — Zanjir | `PipelineGauge` | `gauge` + step list | `steps[]`, `activeCount` |
| Wrapper (Dashboard) | `DashboardLineChart` | → MentionTrendChart | `analytics.trend` |
| Wrapper | `SinglePlatformChart` / `PlatformChartCard` | → PlatformTrendChart | `analytics.trend` |

**Fayl:** `frontend/src/components/TrendChart.jsx`  
**Data shakli (o‘zgarmaydi):**
```js
rows = [
  { label|bucket, total, telegram, youtube, instagram, facebook },
  ...
]
```

## 3. Keyingi chartlar (siz nom aytasiz)

Siz har bir joy uchun chart **turini** aytasiz, masalan:

| Sizning nomi (misol) | ECharts `series.type` |
|----------------------|------------------------|
| Area wave / trend | `line` + `areaStyle` |
| Bar / ustun | `bar` |
| Stacked bar | `bar` + `stack` |
| Smooth line | `line` + `smooth: true` |
| Gauge / yarim doira | `gauge` |
| Donut / pie | `pie` |
| Heatmap | `heatmap` |
| Scatter | `scatter` |
| Radar | `radar` |

**Qanday yozasiz:**  
«Dashboard Brand harakati — *smooth area*»  
«Telegram stats — *bar*»  
→ shu nomdagi komponent `TrendChart.jsx` (yoki yangi fayl) da ECharts option ga o‘tkaziladi.

## 4. Real-time / webhook bilan ishlaydimi?

**Ha — dinamik ishlaydi.** Chart kutubxonasi ma’lumotni qayerdan kelishini bilmaydi.

Oqim (mavjud arxitektura):

```
Webhook / poller / worker
  → backend DB + (ixtiyoriy) realtime event
  → frontend SSE: endpoints.eventsStream()  (/api/events)
  → sahifa shouldRefresh → loadDashboard / loadAnalytics
  → React state yangilanadi (analytics.trend, mentions, …)
  → TrendChart yangi `rows` prop oladi
  → ECharts option qayta hisoblanadi → chizma yangilanadi
```

| Manba | Chart yangilanishi |
|-------|---------------------|
| Instagram/Facebook Meta webhook | Mention → AI → analytics qayta yuklansa — **ha** |
| Telegram live / poller | SSE + refetch — **ha** |
| YouTube sync worker | SSE + refetch — **ha** |
| Faqat bir marta fetch, SSE yo‘q | Faqat refresh/period o‘zgaganda |

**Muhim:** real-time = React state yangilanishi. ECharts ham, Recharts ham shu prop o‘zgarishiga bog‘liq. Migratsiya real-time ni buzmaydi.

SSE debounced (sahifalarda timer) — sparklarda bir zumda, lekin yuzlab eventda spam yo‘q.

## 5. Tema (dark / light)

`useChartColors()` CSS tokenlarni o‘qiydi (`--chart-*`, platform ranglari) va `data-theme` o‘zgarganda qayta o‘qiydi. ECharts `option` shu ranglardan yig‘iladi.

## 6. Qilingan ishlar

- [x] `echarts` + `echarts-for-react` o‘rnatildi  
- [x] `recharts` olib tashlandi  
- [x] `MentionTrendChart` / `PlatformTrendChart` ECharts ga  
- [x] Export nomlari saqlandi → Dashboard o‘zgartirishsiz ishlaydi  
- [ ] Foydalanuvchi aytgan keyingi chart turlari (nom bo‘yicha)

## 7. Sizning navbatdagi buyruq formati

```
1) Umumiy dashboard — Brand harakati → smooth area (hozirgi)
2) Platform kartalar → thin area
3) … yangi joy → gauge / bar / donut …
```

Shundan keyin har birini alohida ECharts type ga o‘tkazamiz.
