# BRAINY — OFFICIAL LOGO ASSET USAGE & BRAND APPLICATION GUIDE

This directory contains the finalized, approved official Brainy logo assets and technical exports.

> [!IMPORTANT]
> The logo design is approved and immutable. Do not redraw, regenerate, or approximate the logo.

---

## 1. Master Logo Assets

Located directly in `logos/`:

| Filename | Dimensions | Description | Primary Application |
|---|---|---|---|
| `brainy_primary_black_logo.png` | 1000 × 1090 | Black symbol on white background | Standalone mark on light surfaces, print, documents. |
| `brainy_white_logo_on_black.png` | 933 × 1090 | White symbol on solid black container | Standalone mark on dark surfaces, dark-mode heroes. |
| `brainy_app_icon.png` | 1024 × 1024 | Squircle launcher icon with circuitry | Application launcher, profile avatars, PWA icons. |
| `brainy_horizontal_wordmark.png` | 1200 × 400 | Full brand lockup (symbol + "Brainy" text) | GitHub README, public landing pages, presentations. |
| `brainy_symbol_only.png` | 800 × 800 | Compact isolated brain-circuit symbol | Navigation bar avatar, assistant message avatar, favicon base. |
| `brainy_32px_preview.png` | 32 × 32 | Pixel-aligned low-resolution preview | Legibility reference at tiny display sizes. |

---

## 2. Technical Exports

Located in `logos/technical_exports/`:

- `favicon.ico`: Multi-resolution icon container (16x16, 32x32, 48x48) for legacy web browsers.
- `favicon-16x16.png`, `favicon-32x32.png`, `favicon-48x48.png`: High-DPI browser tab icons.
- `brainy_app_icon_180.png`: Apple touch icon for iOS Home Screen.
- `brainy_app_icon_192.png`: Android PWA home-screen icon.
- `brainy_app_icon_512.png`: Android splash screen and high-resolution PWA asset.
- `brainy_app_icon_1024.png`: Full-resolution master app store icon.

---

## 3. Web Delivery & Component Integration

In the web frontend (`components/brand/BrainyLogo.tsx`), the active web assets are served from `/brand/`:
- `variant="wordmark"`: High-efficiency precision-fitted desktop lockup (`/brand/brainy-web-desktop.png`).
- `variant="mobile-wordmark"`: Compact mobile lockup (`/brand/brainy-web-mobile.png`).
- `variant="symbol"`: Compact standalone symbol (`/brand/brainy-symbol-opt.png`).
- `variant="app-icon"`: Official squircle launcher icon (`/brand/brainy-app-icon.png`).
- `variant="light-symbol"`: Primary black symbol for light containers (`/brand/brainy-primary-black-logo.png`).
- `variant="dark-symbol"`: White symbol for dark containers (`/brand/brainy-white-logo-on-black.png`).

---

## 4. Usage Rules & Prohibitions

1. **Never alter proportions:** Maintain the exact aspect ratio of each lockup.
2. **Never place black symbol on dark background:** Use `brainy_white_logo_on_black.png` or `dark-symbol` instead.
3. **Never crop the circuitry terminals:** Always preserve the complete bounding box of the brain symbol.
4. **Never approximate with CSS or text monograms:** Always use `<BrainyLogo />` or the approved image assets.
