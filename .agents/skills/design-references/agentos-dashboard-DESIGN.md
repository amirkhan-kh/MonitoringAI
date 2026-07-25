---
version: 2
name: AgentOS-Cockpit-design-analysis
description: >
  Pixel-level analysis of an AgentOS-style dark analytics cockpit (reference screenshot).
  Primary visual north star for MonitoringAI product shell redesign: creative minimalism,
  soft glass panels, refined multi-chart density. Structure from the reference; colors are
  HUE-AGNOSTIC (not locked to green). Neutrals are neutral; one brand accent slot works with
  any hue (indigo, cyan, rose, amber, emerald, …).
status: reference-only
do_not_implement_until: user says to begin visual redesign
source_image: user-provided AgentOS dashboard screenshot
color_policy: hue-agnostic-accent + neutral-surfaces
---

# AgentOS Cockpit — Design Reference (MonitoringAI north star)

> **Status:** reference + skill direction only. Do **not** restyle MonitoringAI CSS/JSX
> until the user explicitly starts the redesign phase.
>
> **Color policy (user, 2026-07-25):** do **not** force green/emerald. The reference screenshot
> happened to use green; we keep its **layout, density, and chart craft**, but build a system
> that **fits any accent hue**. Neutrals are pure dark gray (no green cast).

---

## 0. Design Read (one line)

**Reading this as: dark-first AI/ops analytics cockpit; creative-minimal glass shell;
one configurable brand accent (any hue) on neutral near-black surfaces; semantic chart hues
independent of brand; dense but airy bento of refined gauges and sparklines — never
landing-page marketing, never fixed-to-green, never Material purple mesh as default chrome.**

### Dials for this aesthetic (product shell)
| Dial | Value | Why |
|------|-------|-----|
| `DESIGN_VARIANCE` | **4–5** | Ordered cockpit, not artsy chaos |
| `MOTION_INTENSITY` | **3–4** | Soft hover / tab underline only |
| `VISUAL_DENSITY` | **7–8** | Many metrics in one view, still readable |

---

## 1. Pixel-level scan of the reference (structure only)

### 1.A Global stage
- **Outer stage:** deep near-black, slight vignette (in the screenshot green-tinted; **we use neutral**).
- **Faint mirrored UI** behind the main frame (depth / “floating app” motif).
- **Main app frame:** large rounded rectangle (~20–28px outer radius), hairline border
  `rgba(255,255,255,0.06–0.10)`, soft outer glow tinted from **brand accent** (any hue), low opacity.
- **Inner canvas:** one step lighter than stage; **same neutral family** (not hue-locked).

### 1.B Shell anatomy (left → right, top → bottom)
1. **Left sidebar** (~220–260px)
   - Brand row: mark + wordmark + small “+”
   - Primary nav: icon + label; **active = soft filled pill** (accent-soft fill)
   - Badge on Tasks = small accent pill
   - Footer: Settings, Help (de-emphasized)
2. **Top utility bar**
   - Wide **search pill** (dark fill, hairline, muted placeholder)
   - Right: primary CTA solid **accent** (high contrast text on accent)
   - Icon buttons + avatar
3. **Secondary top tabs** — active underline / brighter label
4. **Optional AI search chip** mid-content
5. **Main bento grid** (asymmetric KPI + charts)

### 1.C Card inventory (what makes it “refined” — hue independent)
| Region | Content | Chart language |
|--------|---------|----------------|
| Hero KPI | Big number + **positive delta** | Mini sparkline + semi-gauge |
| KPI trio | Three status metrics | **Thin arc gauges**, distinct **series** hues |
| Mid | Throughput / trend | Smooth **area/line** |
| Mid | Distribution | **Dot matrix / heatmap** + legend chips |
| Bottom | Resource allocation | **Slim progress** bars |
| Bottom | Secondary gauge | % + date chip |

### 1.D Color system — HUE-AGNOSTIC (MonitoringAI policy)

#### Principle
```
Neutrals  = fixed neutral gray ladder (no green/blue/purple cast)
Accent    = ONE brand hue, fully swappable (token slot)
Charts    = independent semantic + series palette (not forced = accent)
Positive  = may equal accent OR a dedicated success token (document which)
```

#### Neutrals (neutral gray-black — NOT green-black, NOT blue-black)
| Role | Approx hex | Notes |
|------|------------|--------|
| Stage / deepest | `#060608` | Page behind frame |
| Canvas | `#0c0c0e` | Main app bg |
| Surface | `#121214` | Sidebar, recessed |
| Surface raised | `#18181b` | Cards / panels |
| Surface hover | `#1f1f23` | Nav active base + accent-soft mix |
| Hairline | `rgba(255,255,255,0.07)` | Card borders |
| Hairline strong | `rgba(255,255,255,0.12)` | Focus / active |
| Text primary | `#f4f4f5` | Headlines, KPI |
| Text secondary | `#a1a1aa` | Labels, nav idle |
| Text muted | `#71717a` | Captions, axes |

These neutrals work with **indigo, cyan, rose, amber, emerald, violet, orange** without looking “wrong.”

#### Accent (one brand hue — examples, not a lock-in)
Pick **one** at implementation time (or theme preset). All chrome derives from it:

| Token | Derivation | Use |
|-------|------------|-----|
| `--accent` | brand hue mid | CTA, active, links, focus ring |
| `--accent-hover` | lighter / higher L | Hover |
| `--accent-soft` | accent @ 12–16% opacity | Nav active fill, badge bg |
| `--accent-on` | white or near-black by contrast | Text on solid accent |
| `--glow-frame` | accent @ ~8% | Optional shell glow |

**Example presets (any one, not all at once):**
| Preset | `--accent` (example) |
|--------|----------------------|
| Indigo (MonitoringAI legacy-friendly) | `#6366f1` |
| Cyan | `#22d3ee` |
| Rose | `#f43f5e` |
| Amber | `#f59e0b` |
| Emerald (screenshot only) | `#34d399` |
| Violet | `#8b5cf6` |

#### Semantic (stable meaning — not “whatever the accent is”)
| Token | Role | Rule |
|-------|------|------|
| `--positive` | good / up / ok | Prefer dedicated green success **or** accent if accent is green; always WCAG |
| `--negative` | bad / down / risk high | Coral/rose family — **do not** steal from brand accent unless accent is already risk-red |
| `--warning` | caution | Amber family |
| `--neutral` | flat / unknown | Muted gray |

#### Chart series (multi-hue, independent of brand accent)
| Token | Role |
|-------|------|
| `--chart-1` … `--chart-4` | Distinct series (can include accent as series 1, but not required) |
| `--chart-danger` | Failures only |
| `--chart-track` / `--chart-grid` | Dim white-alpha tracks |

Platform IDs (`--telegram`, `--youtube`, …) stay **data identity colors**, never chrome.

**Critical rules:**
1. **One** accent for all chrome (CTA, nav active, focus). Never per-card random accents.
2. Neutrals **never** tint toward the accent (no green-black, no indigo-black cast on canvas).
3. Chart multi-color is for **series only**.
4. Soft fills always `color-mix` / alpha of accent so **any hue** still looks glass-soft.

### 1.E Typography
- Geometric sans; KPI large + **tabular-nums**.
- Card titles 12–13px muted.
- No decorative serif.

### 1.F Shape & elevation
- Frame ~24px, cards ~14–16px, controls ~10px.
- Depth = surface ladder + hairline + optional inner highlight.
- Frame glow uses **accent alpha**, not a fixed green.

### 1.G Chart craft (hue independent)
1. Thin strokes (2–3px).
2. Dim grid/axes.
3. Dim tracks under gauges.
4. Delta next to KPI (semantic color + sign).
5. One hero number per card.
6. No 3D / chartjunk / rainbow card backgrounds.

### 1.H Motion
- 150–220ms hover/tabs; no perpetual glow fields.

### 1.I What this is NOT
- Not locked to emerald/green product branding.
- Not light-first Stripe marketing as the app shell.
- Not AI-purple mesh as default chrome.
- Not equal three marketing feature cards.
- Not skeuomorphic metal gauges.

---

## 2. Mapping → MonitoringAI product surfaces

| Reference pattern | MonitoringAI target |
|-------------------|---------------------|
| Floating frame | `.appShell` (optional) |
| Sidebar active pill | `.navItem.active` with **accent-soft** |
| Primary CTA | `.button.primary` → solid **accent** |
| Hero KPI | Dashboard totals / open risk |
| Arc gauges | Sentiment / risk / coverage |
| Area line | Mention trend (Recharts) |
| Heatmap | Platform activity / risk matrix |
| Progress | Source health / quota |

**Preserve:** routes, API, auth, i18n meaning.

---

## 3. Token proposal (hue-agnostic draft)

```css
/* Neutrals — fixed, no accent cast */
--stage: #060608;
--bg: #0c0c0e;
--surface: #121214;
--surface-raised: #18181b;
--surface-hover: #1f1f23;
--border: rgba(255, 255, 255, 0.08);
--border-strong: rgba(255, 255, 255, 0.14);
--text: #f4f4f5;
--text-muted: #a1a1aa;
--text-subtle: #71717a;

/* Brand accent — ONE hue; swap this block only */
--accent: #6366f1;              /* example: indigo; replace freely */
--accent-hover: color-mix(in oklab, var(--accent) 85%, white);
--accent-soft: color-mix(in oklab, var(--accent) 16%, transparent);
--accent-on: #ffffff;           /* recompute if accent is light */
--glow-frame: 0 0 80px color-mix(in oklab, var(--accent) 12%, transparent);

/* Semantic */
--positive: #22c55e;
--negative: #f43f5e;
--warning: #f59e0b;
--neutral: #71717a;

/* Charts — series, not chrome */
--chart-1: var(--accent);       /* optional: series1 = brand */
--chart-2: #22d3ee;
--chart-3: #fbbf24;
--chart-4: #a78bfa;
--chart-danger: var(--negative);
--chart-track: rgba(255, 255, 255, 0.08);
--chart-grid: rgba(255, 255, 255, 0.05);

--radius-shell: 24px;
--radius-card: 16px;
--radius-control: 10px;
```

Light mode: invert neutrals; keep the **same accent hex**; recompute `--accent-on` for contrast.

---

## 4. Do / Don't

### Do
- Neutral gray-black ladder that works with **any** accent.
- One accent token for all chrome; soft states via alpha/`color-mix`.
- KPI = big number + delta + one chart.
- Thin chart strokes; dim tracks.
- Sidebar active = accent-soft pill.
- Document chosen accent preset when implementation starts.

### Don't
- Lock product to green because the reference screenshot was green.
- Tint neutrals toward accent (green-black, blue-black canvas).
- Different accent per card.
- Fat neon strokes / rainbow panel fills.
- Start CSS rewrite without user green-light.

---

## 5. Relation to other references

| File | Role |
|------|------|
| **This file** | PRIMARY cockpit structure + **hue-agnostic color policy** |
| `raycast-DESIGN.md` | Near-black discipline, hairlines |
| `stripe-DESIGN.md` | KPI anatomy |
| `vercel-DESIGN.md` | Marketing light helper only |

---

## 6. Pre-flight (implementation phase)

- [ ] Design Read = cockpit, not landing
- [ ] Dials ~ 5 / 4 / 7–8
- [ ] Neutrals are **neutral** (no green cast)
- [ ] Single **swappable** accent for chrome
- [ ] Chart series independent of locking product to one “screenshot green”
- [ ] WCAG AA on text and on accent CTA (`--accent-on`)
- [ ] Dual theme both defined
- [ ] No API / route / i18n meaning changes
- [ ] User approved start of redesign

**End of reference.**
