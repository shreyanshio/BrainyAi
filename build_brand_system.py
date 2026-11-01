"""
Brainy Complete Brand Identity System & Production Asset Builder
Generates the complete logo family, rasterized icons, UI mockups, and guidelines PDF.
"""

import os
import sys
import math
from pathlib import Path
import pymupdf
from PIL import Image, ImageDraw, ImageFont, ImageFilter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(r"C:\Users\Shrey\Desktop\BrainyAi\Brainy-Brand-Identity")
DIRS = {
    "primary": BASE_DIR / "01-Primary-Logos",
    "wordmarks": BASE_DIR / "02-Wordmarks",
    "symbols": BASE_DIR / "03-Symbols",
    "icons": BASE_DIR / "04-App-Icons",
    "favicons": BASE_DIR / "05-Favicons",
    "github": BASE_DIR / "06-GitHub-Branding",
    "applications": BASE_DIR / "07-Brand-Applications",
    "guidelines": BASE_DIR / "08-Brand-Guidelines",
}

for d in DIRS.values():
    d.mkdir(parents=True, exist_ok=True)

print("Created folder hierarchy:", BASE_DIR)

# ── VECTOR GEOMETRY ENGINE ──

def get_symbol_svg(fg_color="#000000", bg_color=None, size=512, stroke_w=20):
    bg_rect = f'<rect width="{size}" height="{size}" fill="{bg_color}"/>' if bg_color else ""
    hole_color = bg_color or ("#ffffff" if fg_color == "#000000" else "#000000")
    
    # Precise terminals
    terminals = [
        (134, 154, 14),
        (186, 126, 12),
        (116, 256, 15),
        (176, 226, 12),
        (142, 342, 14),
        (196, 386, 12),
    ]
    term_svg = ""
    for cx, cy, r in terminals:
        term_svg += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fg_color}" />\n'
        term_svg += f'<circle cx="{cx}" cy="{cy}" r="{r*0.4:.1f}" fill="{hole_color}" />\n'

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="{size}" height="{size}">
{bg_rect}
<g stroke="{fg_color}" stroke-width="{stroke_w}" stroke-linecap="round" stroke-linejoin="round" fill="none">
    <!-- CENTRAL SPINAL & SYNAPTIC CONNECTOR AXIS -->
    <path d="M 256 90 L 256 128 M 256 156 L 256 356 M 256 384 L 256 422" stroke-width="{stroke_w*0.8:.1f}" stroke-dasharray="1 1" opacity="0.3"/>
    
    <!-- LEFT HALF: ARTIFICIAL INTELLIGENCE (CIRCUITS & GEOMETRY) -->
    <!-- Outer Circuit Profile -->
    <path d="M 246 88 L 190 88 L 136 142 L 98 214 L 98 298 L 134 370 L 190 424 L 246 424" />
             
    <!-- Circuit Subsystem 1: Upper / Frontal -->
    <path d="M 246 140 L 195 140 L 186 128" />
    <path d="M 246 178 L 170 178 L 136 156" />
    
    <!-- Circuit Subsystem 2: Core / Temporal -->
    <path d="M 246 226 L 190 226 L 178 228" />
    <path d="M 246 256 L 160 256 L 120 256" />
    <path d="M 246 286 L 180 286 L 155 315 L 144 338" />
    
    <!-- Circuit Subsystem 3: Lower / Occipital -->
    <path d="M 246 336 L 205 336 L 175 366" />
    <path d="M 246 372 L 210 372 L 198 384" />

    <!-- RIGHT HALF: HUMAN INTELLIGENCE (ORGANIC CEREBRAL PATHWAYS) -->
    <!-- Outer Organic Brain Contour -->
    <path d="M 266 88 C 330 86, 384 116, 404 164 C 418 196, 418 228, 406 256 C 422 284, 420 324, 400 356 C 380 392, 336 426, 266 424" />
             
    <!-- Upper Cerebral Lobe Convolution -->
    <path d="M 266 140 C 310 138, 346 156, 350 188 C 354 214, 326 226, 296 216 C 278 210, 268 196, 268 184" />
             
    <!-- Mid Cerebral Lobe Convolution -->
    <path d="M 266 256 C 316 254, 362 268, 366 300 C 370 330, 332 344, 298 334 C 278 328, 268 316, 268 304" />
             
    <!-- Lower Cerebellar Convolution -->
    <path d="M 266 372 C 310 374, 340 382, 342 400 C 344 414, 320 422, 288 416" />
             
    <!-- Inter-hemispheric bridging elements -->
    <path d="M 246 140 C 256 140, 256 140, 266 140" stroke-width="{stroke_w*0.75:.1f}"/>
    <path d="M 246 256 C 256 256, 256 256, 266 256" stroke-width="{stroke_w*0.75:.1f}"/>
    <path d="M 246 372 C 256 372, 256 372, 266 372" stroke-width="{stroke_w*0.75:.1f}"/>
</g>
<!-- TERMINAL NODES -->
{term_svg}
</svg>'''


def get_micro_mark_svg(fg_color="#000000", bg_color=None, size=64):
    bg_rect = f'<rect width="{size}" height="{size}" fill="{bg_color}"/>' if bg_color else ""
    sw = 42
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="{size}" height="{size}">
{bg_rect}
<g stroke="{fg_color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" fill="none">
    <path d="M 238 96 L 160 96 L 108 170 L 108 342 L 160 416 L 238 416" />
    <path d="M 238 256 L 150 256" />
    <path d="M 274 96 C 364 94, 404 146, 404 256 C 404 366, 364 418, 274 416" />
    <path d="M 274 256 C 330 256, 344 286, 330 324 C 316 350, 280 350, 274 340" />
</g>
<circle cx="120" cy="170" r="30" fill="{fg_color}" />
<circle cx="120" cy="256" r="30" fill="{fg_color}" />
<circle cx="120" cy="342" r="30" fill="{fg_color}" />
</svg>'''


def get_wordmark_svg(fg_color="#000000", bg_color=None, width=420, height=120):
    bg_rect = f'<rect width="{width}" height="{height}" fill="{bg_color}"/>' if bg_color else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 120" width="{width}" height="{height}">
{bg_rect}
<g fill="{fg_color}">
    <!-- 'b' -->
    <path d="M 24 16 L 38 16 L 38 44 C 44 38, 52 35, 62 35 C 78 35, 91 48, 91 68 C 91 88, 78 101, 62 101 C 52 101, 44 98, 38 92 L 38 100 L 24 100 Z M 38 68 C 38 80, 46 88, 57 88 C 68 88, 77 79, 77 68 C 77 57, 68 48, 57 48 C 46 48, 38 56, 38 68 Z"/>

    <!-- 'r' -->
    <path d="M 106 37 L 120 37 L 120 49 C 125 41, 134 36, 145 36 C 149 36, 153 37, 156 39 L 151 52 C 148 50, 144 50, 141 50 C 131 50, 120 57, 120 70 L 120 100 L 106 100 Z"/>

    <!-- 'a' -->
    <path d="M 218 37 L 232 37 L 232 94 C 232 98, 234 100, 238 100 C 240 100, 243 99, 245 98 L 247 109 C 243 111, 238 112, 233 112 C 223 112, 218 106, 218 97 L 218 89 C 212 96, 203 101, 191 101 C 176 101, 165 90, 165 74 C 165 58, 178 48, 200 48 L 218 48 L 218 46 C 218 39, 212 34, 203 34 C 195 34, 188 37, 184 43 L 174 35 C 181 26, 192 22, 204 22 C 213 22, 218 24, 218 37 Z M 218 59 L 202 59 C 188 59, 179 65, 179 74 C 179 83, 186 89, 195 89 C 206 89, 218 81, 218 70 Z"/>

    <!-- 'i' -->
    <path d="M 264 37 L 278 37 L 278 100 L 264 100 Z M 264 21 C 264 16, 268 12, 271 12 C 275 12, 278 16, 278 21 C 278 25, 275 29, 271 29 C 268 29, 264 25, 264 21 Z"/>

    <!-- 'n' -->
    <path d="M 298 37 L 312 37 L 312 47 C 318 40, 328 35, 340 35 C 356 35, 366 45, 366 63 L 366 100 L 352 100 L 352 66 C 352 54, 345 47, 334 47 C 324 47, 312 55, 312 68 L 312 100 L 298 100 Z"/>

    <!-- 'y' -->
    <path d="M 378 37 L 393 37 L 406 74 L 419 37 L 434 37 L 414 88 L 410 99 C 404 114, 396 122, 381 122 C 376 122, 372 121, 368 119 L 372 108 C 375 109, 378 110, 381 110 C 389 110, 394 105, 398 96 L 378 37 Z"/>
</g>
</svg>'''


def get_horizontal_lockup_svg(fg_color="#000000", bg_color=None, width=760, height=180):
    bg_rect = f'<rect width="{width}" height="{height}" fill="{bg_color}"/>' if bg_color else ""
    
    sym_svg = get_symbol_svg(fg_color=fg_color, bg_color=None, size=130, stroke_w=22)
    start_tag = sym_svg.find('<g stroke=')
    end_tag = sym_svg.rfind('</svg>')
    inner_sym = sym_svg[start_tag:end_tag]

    wm_svg = get_wordmark_svg(fg_color=fg_color, bg_color=None, width=420, height=120)
    start_wm = wm_svg.find('<g fill=')
    end_wm = wm_svg.rfind('</svg>')
    inner_wm = wm_svg[start_wm:end_wm]

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 180" width="{width}" height="{height}">
{bg_rect}
<g transform="translate(32, 25) scale(0.254)">
    {inner_sym}
</g>
<g transform="translate(195, 30) scale(1.18)">
    {inner_wm}
</g>
</svg>'''


def get_app_icon_svg(bg_color="#000000", fg_color="#ffffff", size=1024, radius=224):
    """Square app icon with smooth continuous squircle corner radius."""
    sym_svg = get_symbol_svg(fg_color=fg_color, bg_color=None, size=620, stroke_w=24)
    start_tag = sym_svg.find('<g stroke=')
    end_tag = sym_svg.rfind('</svg>')
    inner_sym = sym_svg[start_tag:end_tag]
    
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">
<rect width="{size}" height="{size}" rx="{radius}" ry="{radius}" fill="{bg_color}"/>
<g transform="translate(202, 202) scale(1.0)">
    {inner_sym}
</g>
</svg>'''


# ── RASTERIZATION HELPERS ──

def render_svg_to_png(svg_string, out_path, width=None, height=None, dpi=150):
    """Renders raw SVG string directly to a transparent PNG using PyMuPDF."""
    doc = pymupdf.open(stream=svg_string.encode('utf-8'), filetype='svg')
    page = doc[0]
    
    # Calculate scale matrix if target width/height requested
    if width and height:
        rect = page.rect
        scale_x = width / rect.width
        scale_y = height / rect.height
        matrix = pymupdf.Matrix(scale_x, scale_y)
        pix = page.get_pixmap(matrix=matrix, alpha=True)
    else:
        pix = page.get_pixmap(dpi=dpi, alpha=True)
        
    pix.save(str(out_path))
    doc.close()
    return out_path


# ── 1. GENERATE PRIMARY LOGOS ──
print("Generating 01-Primary-Logos...")
p_black_svg = get_symbol_svg(fg_color="#000000")
p_white_svg = get_symbol_svg(fg_color="#ffffff")

(DIRS["primary"] / "brainy-primary-black.svg").write_text(p_black_svg, encoding="utf-8")
(DIRS["primary"] / "brainy-primary-white.svg").write_text(p_white_svg, encoding="utf-8")
render_svg_to_png(p_black_svg, DIRS["primary"] / "brainy-primary-black.png", width=1024, height=1024)
render_svg_to_png(p_white_svg, DIRS["primary"] / "brainy-primary-white.png", width=1024, height=1024)


# ── 2. GENERATE WORDMARKS & HORIZONTAL LOCKUPS ──
print("Generating 02-Wordmarks...")
wm_black_svg = get_wordmark_svg(fg_color="#000000")
wm_white_svg = get_wordmark_svg(fg_color="#ffffff")
lockup_black_svg = get_horizontal_lockup_svg(fg_color="#000000")
lockup_white_svg = get_horizontal_lockup_svg(fg_color="#ffffff")

(DIRS["wordmarks"] / "brainy-wordmark-black.svg").write_text(wm_black_svg, encoding="utf-8")
(DIRS["wordmarks"] / "brainy-wordmark-white.svg").write_text(wm_white_svg, encoding="utf-8")
(DIRS["wordmarks"] / "brainy-horizontal-lockup.svg").write_text(lockup_black_svg, encoding="utf-8")
(DIRS["wordmarks"] / "brainy-horizontal-lockup-white.svg").write_text(lockup_white_svg, encoding="utf-8")


# ── 3. GENERATE SYMBOLS & MICRO-MARK ──
print("Generating 03-Symbols...")
sym_black_svg = get_symbol_svg(fg_color="#000000")
sym_white_svg = get_symbol_svg(fg_color="#ffffff")
micro_svg = get_micro_mark_svg(fg_color="#000000")

(DIRS["symbols"] / "brainy-symbol.svg").write_text(sym_black_svg, encoding="utf-8")
(DIRS["symbols"] / "brainy-symbol-white.svg").write_text(sym_white_svg, encoding="utf-8")
(DIRS["symbols"] / "brainy-micro-mark.svg").write_text(micro_svg, encoding="utf-8")


# ── 4. GENERATE APP ICONS ──
print("Generating 04-App-Icons...")
app_icon_svg = get_app_icon_svg(bg_color="#09090b", fg_color="#ffffff", size=1024, radius=224)
for sz in [1024, 512, 192, 180]:
    render_svg_to_png(app_icon_svg, DIRS["icons"] / f"brainy-app-icon-{sz}.png", width=sz, height=sz)


# ── 5. GENERATE FAVICONS & ICO ──
print("Generating 05-Favicons...")
fav_images = []
for sz in [16, 32, 48]:
    out_png = DIRS["favicons"] / f"favicon-{sz}x{sz}.png"
    render_svg_to_png(micro_svg, out_png, width=sz, height=sz)
    fav_images.append(Image.open(out_png))

# Save multi-size favicon.ico
fav_images[0].save(
    str(DIRS["favicons"] / "favicon.ico"),
    format="ICO",
    sizes=[(16, 16), (32, 32), (48, 48)],
    append_images=fav_images[1:]
)


# ── 6. GITHUB BRANDING ASSETS ──
print("Generating 06-GitHub-Branding...")
# A. GitHub Avatar (500x500 squircle)
avatar_svg = get_app_icon_svg(bg_color="#09090b", fg_color="#ffffff", size=500, radius=110)
render_svg_to_png(avatar_svg, DIRS["github"] / "brainy-github-avatar.png", width=500, height=500)

# B. GitHub README Header (1200x380)
header_img = Image.new("RGBA", (1200, 380), "#ffffff")
draw = ImageDraw.Draw(header_img)

# Border outline
draw.rectangle([(1, 1), (1198, 378)], outline="#e4e4e7", width=2)
# Load horizontal lockup
render_svg_to_png(lockup_black_svg, BASE_DIR / "temp_lockup_header.png", width=540, height=128)
lockup_img = Image.open(BASE_DIR / "temp_lockup_header.png")
header_img.paste(lockup_img, (330, 60), lockup_img)
lockup_img.close()
(BASE_DIR / "temp_lockup_header.png").unlink()

# Subheading & Badges text
try:
    font_sub = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 20)
    font_tag = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 15)
    font_bold = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 15)
except Exception:
    font_sub = font_tag = font_bold = ImageFont.load_default()

draw.text((600, 215), "Human Intelligence + Artificial Intelligence", fill="#52525b", font=font_sub, anchor="mm")
draw.text((600, 245), "The Intelligent Multi-Provider Study & AI Learning Platform", fill="#71717a", font=font_tag, anchor="mm")

# Sleek Minimalist Badges
badges = [
    ("Python 3.12", "#000000", "#ffffff"),
    ("Next.js 16", "#000000", "#ffffff"),
    ("Groq Speed Layer", "#18181b", "#ffffff"),
    ("Gemini Intelligence", "#18181b", "#ffffff"),
    ("Strict Zero Budget", "#27272a", "#ffffff"),
    ("Tests: 213 Passing", "#09090b", "#4ade80"),
]
bx = 160
by = 295
for text, bg, fg in badges:
    w = len(text) * 8 + 24
    draw.rounded_rectangle([(bx, by), (bx + w, by + 30)], radius=6, fill=bg)
    draw.text((bx + w // 2, by + 15), text, fill=fg, font=font_bold, anchor="mm")
    bx += w + 14

header_img.save(DIRS["github"] / "brainy-readme-header.png")

# C. GitHub Repository Social Preview (1280x640)
preview_img = Image.new("RGBA", (1280, 640), "#09090b")
pdraw = ImageDraw.Draw(preview_img)

# Subtle technical grid lines
for gx in range(0, 1280, 40):
    pdraw.line([(gx, 0), (gx, 640)], fill="#18181b", width=1)
for gy in range(0, 640, 40):
    pdraw.line([(0, gy), (1280, gy)], fill="#18181b", width=1)

# Large white horizontal lockup in center
render_svg_to_png(lockup_white_svg, BASE_DIR / "temp_social_lockup.png", width=620, height=147)
s_lockup = Image.open(BASE_DIR / "temp_social_lockup.png")
preview_img.paste(s_lockup, (330, 210), s_lockup)
s_lockup.close()
(BASE_DIR / "temp_social_lockup.png").unlink()

pdraw.rounded_rectangle([(510, 150), (770, 182)], radius=16, fill="#1c1917", outline="#292524", width=1)
pdraw.text((640, 166), "AI-POWERED EDUCATION PLATFORM", fill="#d4d4d8", font=font_tag, anchor="mm")

pdraw.text((640, 395), "Intelligent Multi-Provider AI Architecture", fill="#f4f4f5", font=font_sub, anchor="mm")
pdraw.text((640, 430), "Groq Instant Response • Google Gemini Reasoning • Local Mathematics Engine", fill="#71717a", font=font_tag, anchor="mm")

# Bottom metadata bar
pdraw.line([(240, 500), (1040, 500)], fill="#27272a", width=1)
pdraw.text((360, 535), "Zero Inference Cost", fill="#a1a1aa", font=font_tag, anchor="mm")
pdraw.text((640, 535), "Automated Local Proofs", fill="#a1a1aa", font=font_tag, anchor="mm")
pdraw.text((920, 535), "Multi-Platform Study Bot", fill="#a1a1aa", font=font_tag, anchor="mm")

preview_img.save(DIRS["github"] / "brainy-repository-preview.png")


# ── 7. BRAND APPLICATIONS & MOCKUPS ──
print("Generating 07-Brand-Applications...")

# 7.1 Website Preview Mockup (1440x900)
web_img = Image.new("RGBA", (1440, 900), "#ffffff")
wdraw = ImageDraw.Draw(web_img)
# Browser top Chrome
wdraw.rectangle([(0, 0), (1440, 48)], fill="#f4f4f5")
wdraw.line([(0, 48), (1440, 48)], fill="#e4e4e7", width=1)
# Browser window dots
wdraw.ellipse([(20, 18), (32, 30)], fill="#ef4444")
wdraw.ellipse([(40, 18), (52, 30)], fill="#eab308")
wdraw.ellipse([(60, 18), (72, 30)], fill="#22c55e")
# URL pill
wdraw.rounded_rectangle([(320, 10), (1120, 38)], radius=6, fill="#ffffff", outline="#e4e4e7")
wdraw.text((720, 24), "https://brainy.ai", fill="#71717a", font=font_tag, anchor="mm")

# Navbar
render_svg_to_png(lockup_black_svg, BASE_DIR / "temp_web_nav.png", width=160, height=38)
wnav = Image.open(BASE_DIR / "temp_web_nav.png")
web_img.paste(wnav, (80, 75), wnav)
wnav.close()
(BASE_DIR / "temp_web_nav.png").unlink()

wdraw.text((450, 94), "Product", fill="#27272a", font=font_bold)
wdraw.text((540, 94), "Architecture", fill="#52525b", font=font_tag)
wdraw.text((660, 94), "Math Engine", fill="#52525b", font=font_tag)
wdraw.text((780, 94), "PDF Studio", fill="#52525b", font=font_tag)
wdraw.text((890, 94), "Docs", fill="#52525b", font=font_tag)

wdraw.rounded_rectangle([(1220, 80), (1360, 114)], radius=8, fill="#09090b")
wdraw.text((1290, 97), "Get Started", fill="#ffffff", font=font_bold, anchor="mm")

# Hero Section
try:
    font_hero = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 52)
    font_sub_hero = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 22)
except Exception:
    font_hero = font_bold
    font_sub_hero = font_sub

wdraw.text((720, 240), "Human Intelligence meets", fill="#09090b", font=font_hero, anchor="mm")
wdraw.text((720, 305), "Artificial Intelligence.", fill="#09090b", font=font_hero, anchor="mm")
wdraw.text((720, 375), "The high-speed educational assistant powered by intelligent model routing.", fill="#52525b", font=font_sub_hero, anchor="mm")

# Hero Buttons
wdraw.rounded_rectangle([(520, 430), (680, 480)], radius=8, fill="#09090b")
wdraw.text((600, 455), "Start Learning Free", fill="#ffffff", font=font_bold, anchor="mm")
wdraw.rounded_rectangle([(700, 430), (860, 480)], radius=8, fill="#f4f4f5", outline="#e4e4e7")
wdraw.text((780, 455), "View Architecture", fill="#18181b", font=font_bold, anchor="mm")

# Interactive Chat Card Mockup
wdraw.rounded_rectangle([(240, 540), (1200, 860)], radius=14, fill="#ffffff", outline="#e4e4e7", width=2)
# Card header
wdraw.rounded_rectangle([(241, 541), (1199, 595)], radius=12, fill="#fafafa")
wdraw.text((270, 568), "Brainy Study Workspace — Active Session", fill="#52525b", font=font_bold, anchor="lm")
wdraw.rounded_rectangle([(1020, 555), (1170, 582)], radius=6, fill="#ecfdf5", outline="#a7f3d0")
wdraw.text((1095, 568), "✓ Groq Speed: 84ms", fill="#065f46", font=font_tag, anchor="mm")

# Message mockup
wdraw.rounded_rectangle([(280, 620), (740, 665)], radius=8, fill="#f4f4f5")
wdraw.text((300, 642), "Explain the integration of 3x^2 dx step by step.", fill="#18181b", font=font_tag, anchor="lm")

wdraw.rounded_rectangle([(280, 685), (1160, 830)], radius=8, fill="#f8fafc", outline="#e2e8f0")
wdraw.text((300, 715), "Local MathsEngine Computation (Zero API Inference):", fill="#0f172a", font=font_bold, anchor="lm")
wdraw.text((300, 750), "Applying standard power rule: ∫ 3x² dx = 3 * (x³ / 3) + C = x³ + C", fill="#334155", font=font_tag, anchor="lm")
wdraw.text((300, 785), "Verification: d/dx [x³ + C] = 3x² (Symbolic check passed ✓)", fill="#059669", font=font_tag, anchor="lm")

web_img.save(DIRS["applications"] / "website-preview.png")


# 7.2 Dashboard Preview Mockup (1440x900 Dark Mode)
dash_img = Image.new("RGBA", (1440, 900), "#09090b")
ddraw = ImageDraw.Draw(dash_img)

# Left Sidebar
ddraw.rectangle([(0, 0), (280, 900)], fill="#121214")
ddraw.line([(280, 0), (280, 900)], fill="#27272a", width=1)

# Sidebar brand lockup
render_svg_to_png(lockup_white_svg, BASE_DIR / "temp_dash_nav.png", width=180, height=42)
dnav = Image.open(BASE_DIR / "temp_dash_nav.png")
dash_img.paste(dnav, (30, 30), dnav)
dnav.close()
(BASE_DIR / "temp_dash_nav.png").unlink()

# Sidebar items
sitems = [
    ("⚡ Quick Study Chat", True),
    ("📄 PDF Study Studio", False),
    ("📐 Maths Engine", False),
    ("🔬 Code & Science", False),
    ("📊 Provider Telemetry", False),
    ("⚙️ Settings", False),
]
sy = 120
for label, active in sitems:
    if active:
        ddraw.rounded_rectangle([(18, sy), (262, sy + 44)], radius=8, fill="#27272a")
        ddraw.text((35, sy + 22), label, fill="#ffffff", font=font_bold, anchor="lm")
    else:
        ddraw.text((35, sy + 22), label, fill="#a1a1aa", font=font_tag, anchor="lm")
    sy += 54

# Main Workspace
ddraw.text((320, 50), "Calculus & Algorithmic Complexity", fill="#ffffff", font=font_sub)
ddraw.rounded_rectangle([(1180, 36), (1400, 72)], radius=8, fill="#18181b", outline="#27272a")
ddraw.text((1290, 54), "Model: Gemini 3.8 Flash", fill="#38bdf8", font=font_tag, anchor="mm")

# Active reasoning box
ddraw.rounded_rectangle([(320, 110), (1400, 830)], radius=12, fill="#121214", outline="#27272a", width=1)
# Thinking badge
ddraw.rounded_rectangle([(350, 140), (510, 170)], radius=6, fill="#1e1b4b", outline="#3730a3")
ddraw.text((430, 155), "Thinking Level: HIGH", fill="#c7d2fe", font=font_tag, anchor="mm")

ddraw.text((350, 210), "User Query:", fill="#71717a", font=font_tag)
ddraw.text((350, 240), "Prove that the square root of 2 is irrational and analyze its algebraic closure.", fill="#f4f4f5", font=font_bold)

ddraw.line([(350, 280), (1370, 280)], fill="#27272a", width=1)

ddraw.text((350, 310), "Step 1: Classical Proof by Contradiction (Euclid)", fill="#e4e4e7", font=font_bold)
ddraw.text((350, 345), "Assume √2 is rational, meaning there exist coprime integers p and q such that:", fill="#a1a1aa", font=font_tag)
ddraw.text((370, 380), "p / q = √2  ==>  p² / q² = 2  ==>  p² = 2q²", fill="#38bdf8", font=font_tag)
ddraw.text((350, 420), "Since p² is even, p must also be even. Thus p = 2k for some integer k.", fill="#a1a1aa", font=font_tag)
ddraw.text((350, 455), "Substituting p: (2k)² = 2q²  ==>  4k² = 2q²  ==>  q² = 2k²", fill="#38bdf8", font=font_tag)
ddraw.text((350, 495), "Therefore q² is even, which forces q to be even. This contradicts our assumption that p and q are coprime.", fill="#a1a1aa", font=font_tag)
ddraw.text((350, 530), "Conclusion: √2 is strictly irrational. (Q.E.D.)", fill="#4ade80", font=font_bold)

dash_img.save(DIRS["applications"] / "dashboard-preview.png")


# 7.3 Mobile Preview Mockup (800x1200)
mob_img = Image.new("RGBA", (800, 1200), "#09090b")
mdraw = ImageDraw.Draw(mob_img)

# Phone frame
mdraw.rounded_rectangle([(100, 40), (700, 1160)], radius=50, fill="#18181b", outline="#27272a", width=4)
mdraw.rounded_rectangle([(120, 60), (680, 1140)], radius=40, fill="#000000")

# Notch / Dynamic Island
mdraw.rounded_rectangle([(320, 80), (480, 110)], radius=15, fill="#18181b")

# Mobile Header with Lockup
render_svg_to_png(lockup_white_svg, BASE_DIR / "temp_mob_nav.png", width=180, height=42)
mnav = Image.open(BASE_DIR / "temp_mob_nav.png")
mob_img.paste(mnav, (150, 140), mnav)
mnav.close()
(BASE_DIR / "temp_mob_nav.png").unlink()

mdraw.ellipse([(610, 142), (645, 177)], fill="#27272a")
mdraw.text((627, 160), "S", fill="#ffffff", font=font_bold, anchor="mm")

# Greeting
mdraw.text((150, 220), "Hello, Shreyansh", fill="#ffffff", font=font_sub)
mdraw.text((150, 255), "What concept would you like to master today?", fill="#71717a", font=font_tag)

# Quick Action Cards
cards = [
    ("⚡ Instant Speed Chat", "Groq Llama 3.1 8B • <100ms", "#18181b"),
    ("📐 Symbolic Math Solver", "Local SymPy Engine • $0 Cost", "#18181b"),
    ("🔬 Deep Reasoning", "Gemini 3.8 Flash • High Thinking", "#18181b"),
    ("📄 PDF Study Studio", "Multi-file Summarizer & Quizzes", "#18181b"),
]
cy = 310
for title, subtitle, bg in cards:
    mdraw.rounded_rectangle([(150, cy), (650, cy + 90)], radius=14, fill=bg, outline="#27272a", width=1)
    mdraw.text((175, cy + 30), title, fill="#ffffff", font=font_bold)
    mdraw.text((175, cy + 58), subtitle, fill="#a1a1aa", font=font_tag)
    cy += 110

# Bottom Nav
mdraw.line([(120, 1050), (680, 1050)], fill="#18181b", width=1)
mdraw.text((200, 1085), "Chat", fill="#ffffff", font=font_bold, anchor="mm")
mdraw.text((330, 1085), "Studio", fill="#71717a", font=font_tag, anchor="mm")
mdraw.text((470, 1085), "Math", fill="#71717a", font=font_tag, anchor="mm")
mdraw.text((600, 1085), "Profile", fill="#71717a", font=font_tag, anchor="mm")

mob_img.save(DIRS["applications"] / "mobile-preview.png")


# 7.4 Documentation Preview Mockup (1200x800)
doc_img = Image.new("RGBA", (1200, 800), "#ffffff")
cdraw = ImageDraw.Draw(doc_img)

# Header
cdraw.rectangle([(0, 0), (1200, 64)], fill="#ffffff")
cdraw.line([(0, 64), (1200, 64)], fill="#e4e4e7", width=1)
render_svg_to_png(lockup_black_svg, BASE_DIR / "temp_doc_nav.png", width=150, height=35)
cnav = Image.open(BASE_DIR / "temp_doc_nav.png")
doc_img.paste(cnav, (50, 15), cnav)
cnav.close()
(BASE_DIR / "temp_doc_nav.png").unlink()

cdraw.text((220, 32), "/ Documentation / Architecture", fill="#71717a", font=font_tag, anchor="lm")

# Doc Content
cdraw.text((80, 110), "Intelligent Provider Routing Architecture", fill="#09090b", font=font_sub)
cdraw.text((80, 150), "Brainy's central routing engine dispatches incoming prompts based on deterministic task complexity.", fill="#52525b", font=font_tag)

# Code Block Mockup
cdraw.rounded_rectangle([(80, 200), (1120, 540)], radius=10, fill="#09090b")
cdraw.rectangle([(80, 200), (1120, 240)], fill="#18181b")
cdraw.text((105, 220), "ai_routing/policy.py", fill="#a1a1aa", font=font_tag, anchor="lm")

code_lines = [
    "def get_routing_candidates(task: TaskType, complexity: TaskComplexity) -> List[Candidate]:",
    "    if complexity == TaskComplexity.FAST:",
    "        # Groq Instant Layer: Speed first for chit-chat and greetings",
    "        return [('groq', 'llama-3.1-8b-instant'), ('cerebras', 'llama3.1-8b')]",
    "",
    "    if task in CODING_TASKS or task in MATH_TASKS:",
    "        # Gemini Intelligence Layer: Deep reasoning and scientific precision",
    "        return [('gemini', 'gemini-3.8-flash'), ('gemini', 'gemini-3.6-flash')]",
    "",
    "    if task in PDF_STUDY_TASKS:",
    "        # Strict non-Gemini privacy invariant for student document processing",
    "        return filter_eligible(candidates, disallow_gemini=True)",
]
code_y = 260
for cl in code_lines:
    color = "#4ade80" if "def " in cl or "return " in cl else ("#71717a" if "#" in cl else "#f4f4f5")
    cdraw.text((105, code_y), cl, fill=color, font=font_tag)
    code_y += 26

doc_img.save(DIRS["applications"] / "documentation-preview.png")


# 7.5 Presentation Preview Mockup (1280x720)
pres_img = Image.new("RGBA", (1280, 720), "#09090b")
pdraw = ImageDraw.Draw(pres_img)

# Dark gradient accents
pdraw.line([(0, 715), (1280, 715)], fill="#27272a", width=5)

render_svg_to_png(lockup_white_svg, BASE_DIR / "temp_pres_nav.png", width=500, height=118)
pnav = Image.open(BASE_DIR / "temp_pres_nav.png")
pres_img.paste(pnav, (390, 240), pnav)
pnav.close()
(BASE_DIR / "temp_pres_nav.png").unlink()

pdraw.text((640, 400), "Master Creative Direction & Technical Architecture", fill="#f4f4f5", font=font_sub, anchor="mm")
pdraw.text((640, 440), "Dual-Layer Intelligence • Zero-Budget Policy • Production-Ready Platform", fill="#71717a", font=font_tag, anchor="mm")
pdraw.text((640, 640), "CONFIDENTIAL • BRAINY AI PLATFORM 2026", fill="#3f3f46", font=font_tag, anchor="mm")

pres_img.save(DIRS["applications"] / "presentation-preview.png")


# ── 8. MASTER BRAND GUIDELINES & OVERVIEW BOARD ──
print("Generating 08-Brand-Guidelines...")

# A. Brand Overview Board Image (1600x1200)
board = Image.new("RGBA", (1600, 1200), "#ffffff")
bdraw = ImageDraw.Draw(board)

# Header
bdraw.rectangle([(0, 0), (1600, 100)], fill="#09090b")
bdraw.text((60, 50), "BRAINY — BRAND IDENTITY SYSTEM & LOGO APPLICATION GUIDE", fill="#ffffff", font=font_bold, anchor="lm")
bdraw.text((1540, 50), "v2.0 • MONOCHROME", fill="#71717a", font=font_tag, anchor="rm")

# Section 1: Master Symbol
bdraw.text((60, 140), "01. CORE SYMBOL ANATOMY", fill="#09090b", font=font_bold)
render_svg_to_png(p_black_svg, BASE_DIR / "temp_board_sym.png", width=220, height=220)
bsym = Image.open(BASE_DIR / "temp_board_sym.png")
board.paste(bsym, (60, 170), bsym)
bsym.close()
(BASE_DIR / "temp_board_sym.png").unlink()

bdraw.text((320, 200), "Left Hemisphere: Artificial Intelligence", fill="#09090b", font=font_bold)
bdraw.text((320, 225), "• Orthogonal & 45-degree electronic circuit connections", fill="#52525b", font=font_tag)
bdraw.text((320, 245), "• Circular terminal connection pads", fill="#52525b", font=font_tag)
bdraw.text((320, 265), "• Clean technical geometry communicating computational precision", fill="#52525b", font=font_tag)

bdraw.text((320, 310), "Right Hemisphere: Human Intelligence", fill="#09090b", font=font_bold)
bdraw.text((320, 335), "• Organic, flowing cerebral sulci and gyral convolutions", fill="#52525b", font=font_tag)
bdraw.text((320, 355), "• Natural human curvature expressing learning and understanding", fill="#52525b", font=font_tag)
bdraw.text((320, 375), "• Harmonious central synaptic bridging across the longitudinal fissure", fill="#52525b", font=font_tag)

# Section 2: Logo Variations & Lockup
bdraw.line([(60, 420), (1540, 420)], fill="#e4e4e7", width=1)
bdraw.text((60, 450), "02. LOGO FAMILY & LOCKUP VARIANTS", fill="#09090b", font=font_bold)

render_svg_to_png(lockup_black_svg, BASE_DIR / "temp_board_lockup.png", width=380, height=90)
blockup = Image.open(BASE_DIR / "temp_board_lockup.png")
board.paste(blockup, (60, 490), blockup)
blockup.close()
(BASE_DIR / "temp_board_lockup.png").unlink()

bdraw.rounded_rectangle([(520, 480), (960, 590)], radius=8, fill="#09090b")
render_svg_to_png(lockup_white_svg, BASE_DIR / "temp_board_lockup_w.png", width=380, height=90)
blockup_w = Image.open(BASE_DIR / "temp_board_lockup_w.png")
board.paste(blockup_w, (550, 490), blockup_w)
blockup_w.close()
(BASE_DIR / "temp_board_lockup_w.png").unlink()

# App Icon preview
render_svg_to_png(app_icon_svg, BASE_DIR / "temp_board_app.png", width=110, height=110)
bapp = Image.open(BASE_DIR / "temp_board_app.png")
board.paste(bapp, (1040, 480), bapp)
bapp.close()
(BASE_DIR / "temp_board_app.png").unlink()
bdraw.text((1180, 520), "App Icon (1024 / 512 / 192)", fill="#09090b", font=font_bold)
bdraw.text((1180, 545), "Continuous squircle with optical centering", fill="#52525b", font=font_tag)

# Section 3: Color Palette & Swatches
bdraw.line([(60, 620), (1540, 620)], fill="#e4e4e7", width=1)
bdraw.text((60, 650), "03. MONOCHROME COLOR SYSTEM", fill="#09090b", font=font_bold)

swatches = [
    ("Pure Black", "#000000", "#ffffff"),
    ("Near Black", "#09090b", "#ffffff"),
    ("Dark Charcoal", "#18181b", "#ffffff"),
    ("Medium Grey", "#71717a", "#ffffff"),
    ("Border Grey", "#e4e4e7", "#000000"),
    ("Off-White", "#fafafa", "#000000"),
    ("Pure White", "#ffffff", "#000000"),
]
sx = 60
for name, hex_code, fg in swatches:
    bdraw.rounded_rectangle([(sx, 690), (sx + 190, 770)], radius=8, fill=hex_code, outline="#d4d4d8", width=1)
    bdraw.text((sx + 15, 715), name, fill=fg, font=font_bold)
    bdraw.text((sx + 15, 740), hex_code, fill=fg, font=font_tag)
    sx += 215

# Section 4: Do's and Don'ts
bdraw.line([(60, 810), (1540, 810)], fill="#e4e4e7", width=1)
bdraw.text((60, 840), "04. DESIGN INTEGRITY RULES & MISUSE GUARDS", fill="#09090b", font=font_bold)

rules = [
    ("✓ ALWAYS use vector SVG for web & interface headers", "#059669"),
    ("✓ ALWAYS maintain generous clear space around the lockup", "#059669"),
    ("✓ ALWAYS use pure black on light, pure white on dark", "#059669"),
    ("✗ NEVER stretch, warp, or alter the symbol proportions", "#dc2626"),
    ("✗ NEVER apply gradients, drop shadows, or glow effects", "#dc2626"),
    ("✗ NEVER cram the wordmark inside tiny favicon slots", "#dc2626"),
]
rx = 60
ry = 880
for rule, color in rules:
    bdraw.text((rx, ry), rule, fill=color, font=font_bold)
    ry += 38
    if ry > 960:
        ry = 880
        rx = 800

board.save(DIRS["guidelines"] / "brainy-brand-overview.png")


# ── B. MASTER BRAND GUIDELINES PDF (6 PAGES) ──
print("Compiling 08-Brand-Guidelines/brainy-brand-guidelines.pdf...")

pdf_doc = pymupdf.open()
PAGE_W, PAGE_H = 595, 842  # A4

def draw_pdf_header(page, title):
    page.draw_rect(pymupdf.Rect(0, 0, PAGE_W, 55), color=None, fill=(0.04, 0.04, 0.05))
    page.insert_text((40, 35), "BRAINY — BRAND IDENTITY GUIDELINES", fontsize=11, color=(1, 1, 1), fontname="helv")
    page.insert_text((PAGE_W - 140, 35), title.upper(), fontsize=10, color=(0.6, 0.6, 0.6), fontname="helv")
    page.draw_line((0, PAGE_H - 40), (PAGE_W, PAGE_H - 40), color=(0.9, 0.9, 0.9), width=1)
    page.insert_text((40, PAGE_H - 22), "Confidential • Official Brand Direction 2026", fontsize=8, color=(0.5, 0.5, 0.5), fontname="helv")

# PAGE 1: COVER
p1 = pdf_doc.new_page(width=PAGE_W, height=PAGE_H)
p1.draw_rect(pymupdf.Rect(0, 0, PAGE_W, PAGE_H), color=None, fill=(0.04, 0.04, 0.05))
# Center white lockup
p1.insert_image(pymupdf.Rect(147, 260, 447, 340), filename=str(DIRS["github"] / "brainy-repository-preview.png"))
p1.insert_textbox(pymupdf.Rect(40, 430, PAGE_W - 40, 465), "BRAND IDENTITY SYSTEM & LOGO APPLICATION GUIDE", fontsize=15, color=(1, 1, 1), fontname="helv", align=pymupdf.TEXT_ALIGN_CENTER)
p1.insert_textbox(pymupdf.Rect(40, 470, PAGE_W - 40, 500), "Master Creative Direction & Production Asset Manual", fontsize=11, color=(0.7, 0.7, 0.7), fontname="helv", align=pymupdf.TEXT_ALIGN_CENTER)
p1.insert_textbox(pymupdf.Rect(40, 510, PAGE_W - 40, 540), "Human Intelligence + Artificial Intelligence = Brainy", fontsize=10, color=(0.4, 0.8, 0.5), fontname="helv", align=pymupdf.TEXT_ALIGN_CENTER)
p1.insert_textbox(pymupdf.Rect(40, 750, PAGE_W - 40, 780), "Version 2.0 • Production Release • Premium Monochrome Direction", fontsize=9, color=(0.4, 0.4, 0.4), fontname="helv", align=pymupdf.TEXT_ALIGN_CENTER)

# PAGE 2: BRAND PHILOSOPHY & SYMBOL ANATOMY
p2 = pdf_doc.new_page(width=PAGE_W, height=PAGE_H)
draw_pdf_header(p2, "Philosophy & Anatomy")
p2.insert_text((40, 95), "1. Core Philosophy: The Duality of Intelligence", fontsize=16, fontname="helv")
p2.insert_textbox(
    pymupdf.Rect(40, 115, PAGE_W - 40, 200),
    "Brainy represents the intersection of two fundamental forms of intelligence:\n\n"
    "• Human Intelligence: critical thinking, deep conceptual understanding, intuition, and creativity.\n"
    "• Artificial Intelligence: computational speed, machine learning, algorithmic precision, and memory.\n\n"
    "The brand visual identity encapsulates this synthesis into a single, iconic master symbol without "
    "relying on generic AI clichés (such as robot heads, glowing neon networks, or 3D gradients).",
    fontsize=10, fontname="helv"
)
p2.insert_image(pymupdf.Rect(40, 220, 240, 420), filename=str(DIRS["primary"] / "brainy-primary-black.png"))
p2.insert_textbox(
    pymupdf.Rect(260, 230, PAGE_W - 40, 440),
    "Left Hemisphere — Artificial Intelligence:\n"
    "Composed of minimal, intentional orthogonal and 45-degree circuit traces with circular terminal pads. "
    "Communicates engineering discipline, machine reasoning, and verified logic.\n\n"
    "Right Hemisphere — Human Intelligence:\n"
    "Abstract, organic cerebral convolutions echoing natural human brain structure. Controlled continuous curves "
    "express warmth, active thinking, and human agency.\n\n"
    "Central Synaptic Connector:\n"
    "An integrated central longitudinal axis connects the two halves with balanced negative space, signifying "
    "seamless collaboration between human intuition and machine assistance.",
    fontsize=9.5, fontname="helv"
)

# PAGE 3: LOGO FAMILY & SPECIFICATIONS
p3 = pdf_doc.new_page(width=PAGE_W, height=PAGE_H)
draw_pdf_header(p3, "Logo Family")
p3.insert_text((40, 95), "2. Official Logo Variations", fontsize=16, fontname="helv")

p3.insert_text((40, 130), "A. Horizontal Brand Lockup (Primary Identifier)", fontsize=12, fontname="helv")
p3.insert_image(pymupdf.Rect(40, 145, 340, 215), filename=str(DIRS["applications"] / "website-preview.png"))

p3.insert_text((40, 245), "B. Standalone Symbol & Micro-Mark", fontsize=12, fontname="helv")
p3.insert_image(pymupdf.Rect(40, 260, 140, 360), filename=str(DIRS["primary"] / "brainy-primary-black.png"))
p3.insert_textbox(
    pymupdf.Rect(160, 275, PAGE_W - 40, 380),
    "Use the standalone symbol for app loading screens, watermarks, avatars, and UI locations where "
    "the wordmark is already prominent.\n\n"
    "The Micro-Mark (brainy-micro-mark.svg) features boosted optical stroke weights and simplified geometry "
    "engineered specifically for 16px to 32px favicon and badge clarity.",
    fontsize=9.5, fontname="helv"
)

p3.insert_text((40, 395), "C. Dedicated Application Icon (Squircle)", fontsize=12, fontname="helv")
p3.insert_image(pymupdf.Rect(40, 415, 140, 515), filename=str(DIRS["icons"] / "brainy-app-icon-512.png"))
p3.insert_textbox(
    pymupdf.Rect(160, 425, PAGE_W - 40, 530),
    "Asset: brainy-app-icon-1024.png / 512 / 192 / 180\n"
    "Dark charcoal background (#09090b) with smooth continuous squircle curvature (radius 22%).\n"
    "Optically centered white symbol. Strictly no text inside the application icon.",
    fontsize=9.5, fontname="helv"
)

# PAGE 4: TYPOGRAPHY & COLOR SYSTEM
p4 = pdf_doc.new_page(width=PAGE_W, height=PAGE_H)
draw_pdf_header(p4, "Typography & Color")
p4.insert_text((40, 95), "3. Monochrome Palette & Typographic System", fontsize=16, fontname="helv")

p4.insert_textbox(
    pymupdf.Rect(40, 120, PAGE_W - 40, 240),
    "Core Monochrome Colors:\n"
    "• Pure Black (#000000): Primary logo on light backgrounds, primary high-contrast headlines.\n"
    "• Pure White (#FFFFFF): Reverse logo on dark backgrounds, cards, and modal canvas.\n"
    "• Near Black (#09090B): Application background for dark mode, desktop icon containers.\n"
    "• Dark Charcoal (#18181B): Sidebar containers, elevated card surfaces, code blocks.\n"
    "• Muted Zinc (#71717A): Secondary text, timestamps, captions, and inactive icons.\n"
    "• Light Border (#E4E4E7): Subtle 1px structural dividing lines in light mode.",
    fontsize=9.5, fontname="helv"
)

p4.insert_text((40, 260), "Official Typography Hierarchy:", fontsize=12, fontname="helv")
p4.insert_textbox(
    pymupdf.Rect(40, 280, PAGE_W - 40, 440),
    "• Brand Wordmark: Bespoke geometric lowercase 'brainy' (vectorized in SVG).\n"
    "• Interface & Headings: Inter, Segoe UI, or SF Pro Display (Clean modern grotesque sans-serif).\n"
    "• Code & Mathematical Formulas: JetBrains Mono or Fira Code (Monospace precision).\n"
    "• Mathematical Typesetting: KaTeX / LaTeX typesetting for symbolic verified proofs.",
    fontsize=9.5, fontname="helv"
)

# PAGE 5: APPLICATION MATRIX
p5 = pdf_doc.new_page(width=PAGE_W, height=PAGE_H)
draw_pdf_header(p5, "Application Matrix")
p5.insert_text((40, 95), "4. Official Logo Application Matrix", fontsize=16, fontname="helv")

matrix_data = [
    ("Website Navigation / Header", "brainy-horizontal-lockup.svg"),
    ("Website Footer", "brainy-horizontal-lockup.svg or symbol-only"),
    ("GitHub README Header", "brainy-readme-header.png"),
    ("GitHub Social Preview Card", "brainy-repository-preview.png (1280x640)"),
    ("GitHub Organization Avatar", "brainy-github-avatar.png (500x500)"),
    ("Website Favicon & Browser Tabs", "favicon.ico / brainy-micro-mark.svg"),
    ("Mobile Application Launcher", "brainy-app-icon-1024.png / 512 / 192"),
    ("Desktop Application Shortcut", "brainy-app-icon-512.png"),
    ("Application Dashboard", "Horizontal lockup in navbar"),
    ("Application Sidebar (Collapsed)", "brainy-symbol.svg"),
    ("Technical Documentation", "Horizontal lockup in header, wordmark in footer"),
    ("Executive Presentation Deck", "Horizontal lockup on title, symbol on footer"),
    ("Dark Interface & Backgrounds", "Corresponding white variant (*-white.svg)"),
]

my = 135
p5.insert_text((40, my), "TOUCHPOINT / CONTEXT", fontsize=9, color=(0.3, 0.3, 0.3), fontname="helv")
p5.insert_text((260, my), "RECOMMENDED OFFICIAL ASSET", fontsize=9, color=(0.3, 0.3, 0.3), fontname="helv")
p5.draw_line((40, my + 6), (PAGE_W - 40, my + 6), color=(0.8, 0.8, 0.8), width=1)
my += 22

for context, asset in matrix_data:
    p5.insert_text((40, my), context, fontsize=8.5, fontname="helv")
    p5.insert_text((260, my), asset, fontsize=8.5, color=(0.1, 0.3, 0.8), fontname="helv")
    my += 20

# PAGE 6: MISUSE & DESIGN INTEGRITY
p6 = pdf_doc.new_page(width=PAGE_W, height=PAGE_H)
draw_pdf_header(p6, "Integrity Rules")
p6.insert_text((40, 95), "5. Design Integrity & Strict Negative Rules", fontsize=16, fontname="helv")

p6.insert_textbox(
    pymupdf.Rect(40, 125, PAGE_W - 40, 480),
    "To maintain brand prestige, professional credibility, and visual consistency, all developers, "
    "designers, and contributors must adhere to these mandatory restrictions:\n\n"
    "• DO NOT stretch, skew, rotate, or alter the optical aspect ratio of the symbol or wordmark.\n"
    "• DO NOT introduce gradients, neon glows, drop shadows, or 3D skeuomorphic treatments.\n"
    "• DO NOT swap or re-arrange the symbol halves (Left is always AI Circuitry; Right is always Organic Brain).\n"
    "• DO NOT crowd the logo with arbitrary text, slogans, or unsupported feature badges.\n"
    "• DO NOT place the black logo on dark backgrounds or the white logo on light backgrounds.\n"
    "• DO NOT compress the full horizontal wordmark into tiny app icon or favicon spaces.\n"
    "• DO NOT substitute unofficial fonts or alter the lowercase styling of 'brainy'.\n"
    "• ALWAYS respect the minimum clear space rule (equal to the height of the lowercase 'b').\n"
    "• ALWAYS export in native vector SVG for scalable web and software applications.",
    fontsize=9.5, fontname="helv"
)
p6.insert_image(pymupdf.Rect(40, 420, PAGE_W - 40, 740), filename=str(DIRS["guidelines"] / "brainy-brand-overview.png"))

pdf_doc.save(str(DIRS["guidelines"] / "brainy-brand-guidelines.pdf"))
pdf_doc.close()

print("Brand Identity Generation Complete!")
