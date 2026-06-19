# Microsoft Design Guidelines — Claims Casino Automation Suite

## Fluent Design System Principles

### 1. Light
- Elevation through subtle shadows and translucent surfaces
- Acrylic / Mica materials for depth without clutter
- Use `QGraphicsBlurEffect` sparingly for depth hints

### 2. Depth
- Z-axis hierarchy: chrome < content < commands < overlays
- Implement via layered backgrounds (darker = deeper)
- Sidebar: deepest layer | Content: mid layer | Modals/Overlays: top layer

### 3. Motion
- Smooth transitions (300ms ease-out) for page/state changes
- Avoid jarring instantaneous switches
- `QPropertyAnimation` on opacity/position for modals and panels

### 4. Material
- Use semi-transparent backgrounds (`rgba`) for surfaces
- Glass effect: `background: rgba(255,255,255,0.03)` with subtle border
- No pure blacks — deepest surface: `#0d0d14`

### 5. Scale
- Consistent padding grid: 4px base unit
- Button padding: 8px 18px (2u / 4.5u)
- Group content padding: 10px (2.5u)
- Section margins: 16px (4u)

## Design Tokens

### Colors
| Token | Hex | Usage |
|-------|-----|-------|
| `--surface-deepest` | `#0a0a0f` | Main background |
| `--surface-deep` | `#0d0d14` | Sidebar, title bar |
| `--surface-mid` | `rgba(255,255,255,0.015)` | Group boxes |
| `--surface-elevated` | `rgba(255,255,255,0.04)` | Buttons default |
| `--surface-hover` | `rgba(255,255,255,0.08)` | Button hover |
| `--accent` | `#FFD700` | Gold accent |
| `--accent-gradient` | `linear 135deg #FFD700 → #F59E0B` | Gold buttons |
| `--text-primary` | `#e8e8ed` | Primary text |
| `--text-secondary` | `#888` | Secondary / muted |
| `--text-disabled` | `#555` | Disabled state |
| `--border-subtle` | `rgba(255,255,255,0.05)` | Borders |
| `--border-input` | `rgba(255,255,255,0.08)` | Input fields |
| `--success` | `#059669` | Success |
| `--danger` | `#dc2626` | Danger |
| `--warning` | `#eab308` | Warning |

### Typography
- Headings: 20px / 700 weight / `#f0f0f5`
- Body: 13px / 500 weight / `#ccc`
- Muted: 11px / 500 weight / `#888`
- Code/logs: Consolas / `'Courier New'` / monospace / 12px

### Spacing Scale (4px base)
| Multiplier | Pixels | Usage |
|------------|--------|-------|
| 1u | 4px | Tight inner gaps |
| 2u | 8px | Button padding, input padding |
| 3u | 12px | Layout spacing, sidebar button v-padding |
| 4u | 16px | Section margins |
| 5u | 20px | Section title margins |
| 6u | 24px | Outer dialog margins |

## Component Specs

### Title Bar (56px)
- Background: `#0d0d14` (flush with sidebar)
- Logo: 36x36px centered in 40x40px container
- Brand text: "CLAIMS CASINO" 18px / 700 / `#FFD700`
- Window controls: 40x32px, transparent bg, hover `#333`
- Close hover: `#dc2626`

### Sidebar (200px)
- Background: `#0d0d14`
- Nav items: 12px vertical padding, 20px horizontal
- Active state: gold left border (2px) + `rgba(255,215,0,0.05)` bg
- Hover: `rgba(255,255,255,0.02)` bg
- Settings pinned to bottom, separated by 1px line `rgba(255,255,255,0.05)`

### Group Box
- Background: `rgba(255,255,255,0.015)` — barely-there glass
- Border: 1px `rgba(255,255,255,0.05)` — 8px radius
- Title: 11px / 500 / `#888` — positioned in margin area
- Content padding: 10px top, 10px sides, 8px bottom

### Buttons
- Default: `rgba(255,255,255,0.04)` bg + 1px `rgba(255,255,255,0.06)` border
- Hover: `rgba(255,255,255,0.08)` bg + gold-tinted border
- Padding: 8px 18px
- Border radius: 8px
- Gold variant: gradient gold → amber, `#0a0a0f` text
- Success: `#059669` flat
- Danger: `#dc2626` flat

### Tables
- Background: `rgba(255,255,255,0.02)` — very subtle
- Header: dark `rgba(0,0,0,0.3)` + gold bottom border 1px
- Cell padding: 6px 8px
- Selected row: `rgba(255,215,0,0.06)` bg

### Inputs
- Background: `rgba(255,255,255,0.03)`
- Border: 1px `rgba(255,255,255,0.08)` — 6px radius
- Focus: gold border
- Padding: 8px 12px

### Status Bar (24px)
- Background: `rgba(0,0,0,0.4)`
- Text: `#666` / 12px
- Top border: 1px `rgba(255,255,255,0.03)`

## Scrollbar Design
- Width: 6px
- Handle: `rgba(255,255,255,0.08)` / 3px radius
- Hover: `rgba(255,255,255,0.15)`
- No buttons (add-line/sub-line: height 0)

## Layout Structure
```
┌──────────────────────────────────────────────┐
│ Title Bar (56px)         #0d0d14             │
├────────┬─────────────────────────────────────┤
│        │                                     │
│ Sidebar│  Content Area                       │
│ 200px  │  margins: 16px                      │
│ #0d0d14│  spacing: 12px                      │
│        │                                     │
│        │                                     │
├────────┴─────────────────────────────────────┤
│ Status Bar (24px)       rgba(0,0,0,0.4)      │
└──────────────────────────────────────────────┘
```
