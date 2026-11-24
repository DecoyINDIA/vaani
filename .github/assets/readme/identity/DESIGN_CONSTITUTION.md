# Vaani Design Constitution: Warm Intelligence
**Visual Identity, Design Tokens & Architectural Specification for the Vaani Repository**
*Authored by Creative Director & Design System Architect (`@director`)*

---

## 1. The Core Philosophy: "Warm Intelligence"

Most AI technology projects adopt a cold, sterile aesthetic: harsh pure black (`#000000`), clinical blue (`#0066FF`), or synthetic purple-magenta gradients that feel distant, impersonal, and disconnected from human life.

**Vaani takes the opposite path.**

Vaani is the AI front office employee for Indian small and medium businesses—neighborhood clinics, salons, coaching institutes, pathology labs, and boutique studios. In these spaces, relationships are built on trust, warmth, eye contact, and spoken words.

**Warm Intelligence** fuses two distinct worlds:
1. **The Human Warmth of Indian Craftsmanship:** The tactile tone of handmade cream paper (*Warm Canvas* `#FBF9F5`), deep evergreen forest ink (*Deep Spruce* `#183F35`), natural earthenware (*Terracotta* `#D97736`), and sacred brass temple bells (*Temple Gold* `#B37E28`).
2. **The Precision Rigor of Enterprise Software:** Sub-second p50 latency, deterministic scope guards, atomic 120-second distributed slot leases, and strict India DPDP Act 2025 compliance.

```
       [ Cold Sterile Tech ]                   [ Warm Intelligence ]
       Pure Black (#000000)        ──►         Deep Spruce Ink (#183F35)
       Neon Electric Blue          ──►         Emerald Jade (#1D6D56)
       Synthetic Purple Mesh       ──►         Terracotta Earthenware (#D97736)
       White Glare (#FFFFFF)       ──►         Warm Paper Canvas (#FBF9F5)
       Monolingual English         ──►         Devanagari (वा) + Odia (ବା) + Hinglish
```

---

## 2. The Brand Emblem: Sacred Geometry & Acoustic Resonance

The Vaani brand mark is not a generic robot icon or chat bubble. It is an **asymmetrical temple-leaf squircle** bearing the sacred Devanagari glyph **'वा'** (*Vaa*), signifying *Vaani*—speech, voice, utterance, and the vibration of Saraswati's veena.

### 2.1 Geometric Construction
The emblem utilizes diagonal corner asymmetry to evoke both an open speech bubble and traditional Indian architectural niches (*jharokhas*):
- **Top-Left Corner:** Radius `26px` (Generous curve, welcoming ingress)
- **Top-Right Corner:** Radius `8px` (Engineered precision corner)
- **Bottom-Right Corner:** Radius `26px` (Echoing the welcoming curve)
- **Bottom-Left Corner:** Radius `8px` (Engineered anchor corner)
- **Acoustic Aura:** Concentric resonance arcs radiating from the right flank at `50%` opacity in Temple Gold (`#B37E28`), representing inbound voice/SIP audio waves.
- **Auspicious Bindu:** A single golden dot (`cx=44, cy=18, r=2.5`) positioned above the glyph, anchoring dignity and focus.

### 2.2 Vernacular Sisterhood: Devanagari 'वा' & Odia 'ବା'
India's linguistic richness cannot be reduced to Hindi alone. In Eastern India (Odisha and surrounding belts), Vaani speaks fluent Odia. The design system includes a co-equal brand glyph featuring the Odia **'ବା'** (*Ba/Va*), rendered with identical mathematical geometry and finish.

Assets:
- Primary Devanagari Emblem: [brand-glyph.svg](brand-glyph.svg)
- Vernacular Odia Emblem: [brand-glyph-odia.svg](brand-glyph-odia.svg)
- Full Identity Lockup: [logo-full.svg](logo-full.svg)
- Dark Spruce Slab Lockup: [logo-dark-spruce.svg](logo-dark-spruce.svg)

---

## 3. Color Token Architecture

All colors are mathematically specified and checked against WCAG AA / AAA accessibility standards on both Warm Canvas (`#FBF9F5`) and Deep Spruce (`#183F35`).

### 3.1 Primary Brand Matrix

| Token Name | Hex Code | RGB | Role & Meaning | Contrast (vs Canvas) |
| :--- | :--- | :--- | :--- | :--- |
| `canvas.warm` | `#FBF9F5` | `251, 249, 245` | Base paper ground; soft, human, reduces optical fatigue | N/A (Ground) |
| `canvas.surface` | `#FFFFFF` | `255, 255, 255` | Elevated card surfaces and crisp message bubbles | 1.05:1 |
| `canvas.subtle` | `#F4EFE8` | `244, 239, 232` | Recessed containers, table row alternating tint | 1.12:1 |
| `ink.primary` | `#183F35` | `24, 63, 53` | Deep Spruce; authoritative headings and high-contrast body | **13.2:1 (AAA)** |
| `ink.secondary` | `#485C54` | `72, 92, 84` | Earthy forest; supporting text and feature descriptions | **5.4:1 (AA)** |
| `ink.muted` | `#788A82` | `120, 138, 130` | Slate-spruce; timestamps, captions, disabled states | 3.2:1 (Large text) |
| `brand.jade` | `#1D6D56` | `29, 109, 86` | Emerald Jade; primary interactive CTAs, verified badges | **5.8:1 (AA)** |
| `brand.subtle` | `#EAF3EF` | `234, 243, 239` | Subtle jade wash for selected chips and active tabs | Tint |
| `accent.terracotta` | `#D97736` | `217, 119, 54` | Terracotta; recovered revenue, urgency, 120s timer | **3.8:1 (Graphic)** |
| `accent.gold` | `#B37E28` | `179, 126, 40` | Temple Gold; morning brief highlights, trust seals | **4.2:1 (Graphic)** |

### 3.2 Channel & Ecosystem Tokens

| Token Name | Hex Code | Role in System |
| :--- | :--- | :--- |
| `whatsapp.dark` | `#075E54` | WhatsApp phone mockup top header and status bar |
| `whatsapp.green` | `#25D366` | WhatsApp brand icon, online pulse beacon, confirmation CTA |
| `whatsapp.light_bubble` | `#DCF8C6` | Outgoing patient/customer message bubble |
| `whatsapp.white_bubble` | `#FFFFFF` | Incoming Vaani assistant message bubble |
| `semantic.success` | `#207E56` | Confirmed bookings, passing tests, active leases |
| `semantic.danger` | `#A43A31` | Double-booking aborts, cancellations, urgent staff handoff |

Visual Reference: [palette-matrix.svg](palette-matrix.svg)

---

## 4. Typography & Vernacular System

The typographic stack balances Latin geometric readability with authentic Indic font rendering across operating systems.

```css
/* Primary Sans Stack */
--font-sans: "Plus Jakarta Sans", Aptos, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans Devanagari", "Noto Sans Oriya", sans-serif;

/* Monospace Engineering Stack */
--font-mono: "JetBrains Mono", "Cascadia Code", "SFMono-Regular", Consolas, monospace;

/* Sacred Glyph Stack */
--font-glyph: "Noto Sans Devanagari", "Rozha One", "Anek Devanagari", serif;
```

### 4.1 Type Hierarchy & Sizing Scale

| Scale | Size / Line Height | Weight | Letter Spacing | Target Usage |
| :--- | :--- | :--- | :--- | :--- |
| **Hero Display** | `48px / 56px` | 800 (Extrabold) | `-0.035em` | Hero titles, emotional promises |
| **H1 Display** | `32px / 40px` | 800 (Extrabold) | `-0.03em` | Primary section headers |
| **H2 Section** | `22px / 28px` | 700 (Bold) | `-0.02em` | Subsections, card deck headers |
| **H3 Subsection** | `17px / 24px` | 600 (Semibold) | `-0.01em` | Feature names, message senders |
| **Body Primary** | `14.5px / 22px` | 400 (Regular) | `0` | Explanatory text, docs, chat copy |
| **Caption / Label** | `12px / 16px` | 500 (Medium) | `+0.01em` | Timestamps, metadata, micro-tags |
| **Code / Hash** | `11.5px / 16px` | 500 (Mono) | `0` | Lock keys, DPDP hashes, TTL values |

Visual Reference: [typography-spec.svg](typography-spec.svg)

---

## 5. Shape, Elevation & Geometry Rules

1. **Radii Tokens:**
   - `4px`: Micro code chips, status badges
   - `8px`: Inner interactive slot buttons (`5:00 PM`, `5:30 PM`)
   - `12px`: WhatsApp chat bubbles, feature callout tiles
   - `16px`: Primary cards, architecture boxes, hero container frames
   - `24px`: Mobile phone simulator wrapper
   - `9999px`: Fully rounded pill buttons and navigation chips
   - `Asymmetric 26px / 8px`: Vaani brand mark and signature tiles

2. **Borders & Rules:**
   - Always 1px or 1.5px hairline rules.
   - Light backgrounds: `rgba(24, 63, 53, 0.10)` (Spruce tint prevents harsh black wireframes).
   - Dark spruce backgrounds: `rgba(255, 255, 255, 0.12)` with optional golden highlight `rgba(179, 126, 40, 0.35)`.

3. **Shadows & Elevation:**
   - Card ambient: `0 4px 20px -2px rgba(24, 63, 53, 0.08)`
   - Floating popover: `0 12px 32px -4px rgba(24, 63, 53, 0.12)`
   - Brand glow: `0 8px 24px -2px rgba(29, 109, 86, 0.25)`

---

## 6. Motion & Animation Standards for SVG

All animated SVG assets produced across the repository (`.github/assets/readme/hero/` and `.github/assets/readme/features/`) must adhere to these rules:

1. **Self-Contained Viewport:** Every SVG must declare an explicit `viewBox`, `width`, and `height`, and render consistently regardless of host page zoom.
2. **Accessible Reduced-Motion Media Query:**
   ```css
   @media (prefers-reduced-motion: reduce) {
     .animated-node { animation: none !important; opacity: 1 !important; transform: none !important; }
   }
   ```
3. **Optimized Loop Cycles:**
   - Standard feature loop: `12s` to `16s` infinite cycle with smooth easing (`cubic-bezier(0.16, 1, 0.3, 1)` or `ease-out`).
   - 120s Hold Timer: Represented by an active SVG stroke-dashoffset countdown or high-tempo hold pulse.
4. **File Size Budget:**
   - Feature SVGs: `< 150 KB`
   - Hero animated banner: `< 350 KB`

---

## 7. Directives for Peer Agents

- **To `@animator` (Motion Designer & SVG Creative Technologist):**
  - Use `canvas.warm` (`#FBF9F5`) or self-contained `linearGradient` from `brand.jade_deep` (`#0E2822`) to `ink.primary` (`#183F35`) for dark hero surfaces.
  - Implement the 2-Tap Slot Picker buttons with `brand.jade_subtle` (`#EAF3EF`) background and `brand.jade` (`#1D6D56`) borders.
  - Highlight the 120s Atomic Hold timer in `accent.terracotta` (`#D97736`).
  - Style the 08:00 AM Morning Brief with `accent.gold` (`#B37E28`) accents.
- **To `@architect` (Technical Illustrator & Systems Architect):**
  - Use `brand.jade` (`#1D6D56`) for successful paths, LangGraph state nodes, and healthy leases.
  - Use `accent.terracotta` (`#D97736`) for the 120s atomic distributed hold sequence and race condition gates.
  - Use `ink.primary` (`#183F35`) for state machine containers and actor lifelines.
  - Label all cryptographic hashes and schemas in `JetBrains Mono` with system fallbacks.
- **To `@curator` (Editorial Copywriter & Product Truth Auditor):**
  - Reference the newly generated identity SVGs in Act I and headers:
    - Logo full: `logo-full.svg`
    - Palette specimen: `palette-matrix.svg`
    - Typography specimen: `typography-spec.svg`
    - Trust seal: `brand-seal.svg`
  - Maintain the "Warm Intelligence" editorial voice throughout README.md: dignified, authoritative, culturally resonant, and technically indisputable.

---
*Created under the Vaani Design System initiative. Proprietary. Developed by Xolver / Subham Jena.*
