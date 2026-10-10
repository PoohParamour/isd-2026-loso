"""สร้างกราฟสำหรับสไลด์ S4, S7, S8, S9, S11, S12, S13, S14 และ B4, B5 (ตัวเลขมาจาก model/reports/ ตามที่ระบุใน footnote ของแต่ละกราฟ)

ขั้นตอน:
    python3 make_charts.py          # สร้างไฟล์ .html (SVG) ข้างสคริปต์
    # เรนเดอร์เป็น PNG 3200x1800 ด้วย Chrome (ภาษาไทยแสดงถูกต้อง) ตัวอย่างสำหรับ macOS:
    for n in s04_routes s07_deskew s08_tuning s09_cer s11_split s12_accuracy s13_stages s14_weak b04_phone b05_overfit; do
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --hide-scrollbars \
        --force-device-scale-factor=2 --window-size=1600,900 --virtual-time-budget=6000 \
        --screenshot="$n.png" "file://$PWD/$n.html"
    done
ฟอนต์ IBM Plex Sans Thai โหลดจาก Google Fonts (ถ้าออฟไลน์จะใช้ฟอนต์ไทยของระบบแทน)
"""
import html, os
OUT = os.path.dirname(os.path.abspath(__file__))
GREEN, ORANGE, RED, DARK, CREAM, GRAY, LGRAY = "#3E8D67", "#F47721", "#ED0A13", "#292825", "#F8F7F5", "#716F6A", "#E7E4DE"
FONT = "'IBM Plex Sans Thai','Sarabun','Thonburi','Noto Sans Thai',sans-serif"
W, H = 1600, 900
def esc(t): return html.escape(str(t))

def title_block(title, subtitle):
    if len(title) <= 50:
        return (f'<text x="70" y="92" font-size="44" font-weight="700">{esc(title)}</text>'
                f'<text x="70" y="140" font-size="26" style="fill:{GRAY}">{esc(subtitle)}</text>')
    words = title.split(" "); best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        d = abs(len(a) - len(b))
        if best is None or d < best[0]: best = (d, a, b)
    _, a, b = best
    return (f'<text x="70" y="78" font-size="40" font-weight="700">{esc(a)}</text>'
            f'<text x="70" y="126" font-size="40" font-weight="700">{esc(b)}</text>'
            f'<text x="70" y="172" font-size="25" style="fill:{GRAY}">{esc(subtitle)}</text>')

def page(name, title, subtitle, body, source):
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@400;600;700&display=swap');
html,body{{margin:0;padding:0;background:{CREAM};}} text{{font-family:{FONT};fill:{DARK};paint-order:stroke;stroke:{CREAM};stroke-width:7px;stroke-linejoin:round;}}
</style></head><body><svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs><pattern id="hatch" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="14" height="14" fill="{RED}"/><rect width="7" height="14" fill="#fff" opacity=".45"/></pattern>
<pattern id="hatchg" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="14" height="14" fill="#9A978F"/><rect width="7" height="14" fill="#fff" opacity=".45"/></pattern></defs>
<rect width="{W}" height="{H}" fill="{CREAM}"/>
{title_block(title, subtitle)}
{body}
<text x="70" y="{H-34}" font-size="21" style="fill:{GRAY}">{esc(source)}</text></svg></body></html>"""
    open(os.path.join(OUT, name + ".html"), "w").write(doc)

def hbars(items, x0, y0, label_w, bar_w, row_h, vmax, fmt, target=None, font=29, gap=0.34, unit_note=None):
    s = ""
    n = len(items)
    plot_h = n * row_h
    if target is not None:
        tx = x0 + label_w + bar_w * target / vmax
        s += f'<line x1="{tx}" y1="{y0-14}" x2="{tx}" y2="{y0+plot_h}" stroke="{RED}" stroke-width="3" stroke-dasharray="10 8"/>'
        s += f'<text x="{tx}" y="{y0-22}" font-size="23" text-anchor="middle" style="fill:{RED}">เป้า {target:g}%</text>'
    for i, it in enumerate(items):
        label, val, color = it[0], it[1], it[2]
        note = it[3] if len(it) > 3 else ""
        y = y0 + i * row_h
        bh = row_h * (1 - gap)
        by = y + (row_h - bh) / 2
        bw = max(2, bar_w * min(val, vmax) / vmax)
        s += f'<text x="{x0+label_w-18}" y="{by+bh/2+10}" font-size="{font}" text-anchor="end">{esc(label)}</text>'
        s += f'<rect x="{x0+label_w}" y="{by}" width="{bw}" height="{bh}" rx="6" fill="{color}"/>'
        s += f'<text x="{x0+label_w+bw+14}" y="{by+bh/2+10}" font-size="{font}" font-weight="700">{esc(fmt(val))}</text>'
        if note: s += f'<text x="{x0+label_w+bw+14}" y="{by+bh/2+10+30}" font-size="21" style="fill:{GRAY}">{esc(note)}</text>'
    return s

def legend(items, x, y, step=330):
    s = ""
    for i, (c, t) in enumerate(items):
        fill = c if c.startswith("url") else c
        s += f'<rect x="{x+i*step}" y="{y-20}" width="26" height="26" rx="5" fill="{fill}"/><text x="{x+i*step+38}" y="{y+1}" font-size="24">{esc(t)}</text>'
    return s

pct = lambda v: f"{v:.2f}%"

# S4 — routes (two panels)
b = '<text x="70" y="215" font-size="30" font-weight="600">ความแม่นยำ (Exact field %)</text>'
b += hbars([("Hybrid (ใช้จริง)", 98.26, GREEN), ("OCR ล้วน", 41.91, RED), ("Local VLM*", 1.33, "url(#hatch)")], 40, 250, 270, 380, 150, 100, pct, font=28)
b += '<text x="860" y="215" font-size="30" font-weight="600">เวลาเฉลี่ยต่อฉบับ (วินาที)</text>'
# time panel with a broken bar for VLM
rows = [("Hybrid (ใช้จริง)", 0.43, GREEN, "0.43 วินาที"), ("OCR ล้วน", 3.23, RED, "3.23 วินาที"), ("Local VLM*", 121.1, "url(#hatch)", "121.1 วินาที")]
cap = 12.0; bw_full = 250; x0 = 1110; y0 = 250
for i, (lab, v, col, txt) in enumerate(rows):
    y = y0 + i * 150; bh = 150 * 0.66; by = y + (150 - bh) / 2
    w = bw_full * min(v, cap) / cap
    b += f'<text x="{x0-18}" y="{by+bh/2+10}" font-size="28" text-anchor="end">{esc(lab)}</text>'
    b += f'<rect x="{x0}" y="{by}" width="{w}" height="{bh}" rx="6" fill="{col}"/>'
    if v > cap:
        bx = x0 + w - 60
        b += f'<polygon points="{bx},{by-6} {bx+26},{by-6} {bx+10},{by+bh+6} {bx-16},{by+bh+6}" fill="{CREAM}"/>'
    b += f'<text x="{x0+w+14}" y="{by+bh/2+10}" font-size="28" font-weight="700">{esc(txt)}</text>'
b += f'<text x="860" y="725" font-size="22" style="fill:{GRAY}">แกนตัดที่ 12 วินาที (แท่ง VLM ยาวกว่านี้มาก)</text>'
b += f'<text x="70" y="760" font-size="23" style="fill:{GRAY}">* Hybrid และ OCR ล้วนวัดบน PDF ชุดเดียวกัน 8 ฉบับ · Local VLM วัดบนภาพ PNG 4 ฉบับ (สำเร็จ 1/4 ฉบับ, ถูก 1/75 ฟิลด์) ไม่ใช่ชุดเดียวกัน</text>'
page("s04_routes", "เลือก Hybrid เพราะแม่นถึง 98% และเร็วกว่า OCR ล้วนราว 7 เท่า", "เปรียบเทียบเส้นทางการอ่านข้อความ", b, "ที่มา: model/reports/route-comparison-dev.json, vlm-dev.json")

# S7 — deskew grouped bars
cats = [("หมุน / ปรับสว่าง", 61.80, 74.80), ("perspective", 56.22, 60.37), ("noise", 94.58, 94.58), ("เบลอ / คอนทราสต์ต่ำ", 57.18, 57.18), ("JPEG / มืด", 61.80, 61.80)]
x0, y0, rowh, bw = 70, 245, 100, 780
b = ""
tx = x0 + 400 + bw * 91 / 100
b += f'<line x1="{tx}" y1="{y0-20}" x2="{tx}" y2="{y0+len(cats)*rowh+10}" stroke="{RED}" stroke-width="3" stroke-dasharray="10 8"/><text x="{tx}" y="{y0-28}" font-size="23" text-anchor="middle" style="fill:{RED}">เป้า 91%</text>'
for i, (lab, a, c) in enumerate(cats):
    y = y0 + i * rowh
    b += f'<text x="{x0+380}" y="{y+52}" font-size="28" text-anchor="end">{esc(lab)}</text>'
    b += f'<rect x="{x0+400}" y="{y+8}" width="{bw*a/100}" height="34" rx="5" fill="#9A978F"/><text x="{x0+400+bw*a/100+12}" y="{y+34}" font-size="24" style="fill:{GRAY}">{a:.2f}%</text>'
    b += f'<rect x="{x0+400}" y="{y+48}" width="{bw*c/100}" height="34" rx="5" fill="{ORANGE}"/><text x="{x0+400+bw*c/100+12}" y="{y+74}" font-size="24" font-weight="700">{c:.2f}%</text>'
    if c - a > 0.01: b += f'<text x="{x0+400+bw*c/100+150}" y="{y+74}" font-size="26" font-weight="700" style="fill:{GREEN}">+{c-a:.1f} จุด</text>'
b += legend([("#9A978F", "ก่อนเพิ่ม deskew"), (ORANGE, "หลังเพิ่ม deskew")], 70, 800, 360)
page("s07_deskew", "เพิ่ม deskew แล้วภาพหมุน/สว่างแม่นขึ้น 61.8% → 74.8%", "ภาพ augmented 60 ภาพ (กลุ่มละ 12 ภาพ) เทียบปิด/เปิดขั้นแก้เอียง · ความเสียหายอื่นไม่เปลี่ยน", b, "ที่มา: model/reports/augmented-dev-no-deskew-full-20261004.json, augmented-dev-deskew-full-20261004.json · แลกกับเวลาสูงสุด 28.9 → 44.3 วินาที/ภาพ")

# S8 — tuning progression
items = [("ค่าเริ่มต้น", 54.31, "#9A978F", "681/1254"), ("เลือก profile ตามรูปแบบ", 64.43, ORANGE, "808/1254 · จาก 144 runs"), ("+ cell OCR เฉพาะแถวที่ parse ไม่ได้", 66.35, GREEN, "832/1254"), ("(ทดลอง) cell OCR แทนทุกแถว", 63.80, "url(#hatchg)", "800/1254 · ไม่ใช้ เพราะคะแนนลด")]
b = hbars(items, 40, 235, 620, 700, 140, 100, pct, font=28, gap=0.40)
page("s08_tuning", "เลือกค่าแยกตามรูปแบบเอกสาร ภาพ dev แม่นขึ้น 54% → 66%", "ภาพ PNG dev 12 ฉบับ ช่วงเลือกวิธีปรับภาพ/โหมด Tesseract และ cell OCR (ไม่ใช่คะแนนสุดท้ายของระบบ)", b, "ที่มา: model/reports/image-original-dev.json, image-original-dev-profiled.json, image-original-dev-cell-aware-gated.json, image-original-dev-cell-aware.json")

# S9 — CER
items = [("Tesseract ที่ติดตั้ง", 8.83, "#9A978F"), ("weights จากภาพรุ่นก่อน", 7.86, "#9A978F"), ("รุ่นที่ฝึกใหม่ (300 iterations)", 2.31, GREEN)]
b = hbars(items, 40, 255, 560, 640, 170, 10, lambda v: f"{v:.2f}%", font=30, gap=0.38)
b += f'<text x="70" y="810" font-size="24" style="fill:{GRAY}">ยิ่งต่ำยิ่งดี · วัดบน 109 บรรทัด validation ของเอกสารชุดเดียวกัน (2 คน × 3 มุม) ไม่ใช่เอกสารใหม่</text>'
page("s09_cer", "ฝึก Tesseract เพิ่ม ลดอัตราผิดต่อตัวอักษร (CER) จาก 8.83% เหลือ 2.31%", "Fine-tune LSTM ภาษาอังกฤษ · lr 0.0001 · เลือก 300 iterations จาก 4 ชุดค่า", b, "ที่มา: model/reports/phone-training-summary-20261007.json, model/data/phone_ocr/training.json")

# S11 — split
total = 48; segs = [("dev 35 ฉบับ (ปรับระบบ)", 35, ORANGE), ("test 12 ฉบับ (วัดผล)", 12, GREEN), ("ไม่มีเฉลย 1", 1, "#9A978F")]
x = 70; wtot = 1460; b = ""
for lab, n, col in segs:
    w = wtot * n / total
    b += f'<rect x="{x}" y="300" width="{w-4}" height="150" rx="8" fill="{col}"/>'
    if n > 5: b += f'<text x="{x+w/2}" y="392" font-size="40" font-weight="700" text-anchor="middle" style="stroke:none;fill:#fff">{n}</text>'
    x += w
b += legend([(c, l) for l, n, c in segs], 70, 530, 470)
b += f'<text x="70" y="650" font-size="28">transcript จริง 48 ฉบับ · 47 ฉบับมีเฉลย · แบ่งตามเอกสารต้นทาง (ภาพที่มาจากเอกสารเดียวกันอยู่ชุดเดียวกัน)</text>'
b += f'<text x="70" y="700" font-size="28">Metric หลัก: exact field accuracy · เสริม: row F1, CER, latency · เป้า: accuracy &gt; 91%, เวลาเฉลี่ย &lt; 30 วินาที/ฉบับ</text>'
page("s11_split", "ทดสอบกับ transcript จริง 48 ฉบับ แยก dev 35 · test 12", "การแบ่งชุดข้อมูลระดับเอกสาร", b, "ที่มา: docs/process.md (Decision Log), model/data/manifest.json")

# S12 — accuracy by input
items = [("PDF dev", 96.55, ORANGE, "ชุดที่ใช้ปรับระบบ"), ("PDF test (blind ครั้งแรก)", 88.34, RED, "ต่ำกว่าเป้า"), ("PDF test (reused)", 97.68, ORANGE, "หลังนำข้อผิดพลาดมาปรับ"),
         ("ภาพต้นฉบับ test", 95.74, ORANGE, "reused"), ("ภาพ noise 47 ภาพ", 92.46, ORANGE, ""), ("ภาพมือถือ 6 ภาพ", 97.29, ORANGE, "เอกสารชุดเดียวกับที่ฝึก"),
         ("ภาพ augmented 60 ภาพ", 69.74, RED, ""), ("ภาพถ่ายหน้าจอ 4 มุม", 70.50, RED, "เอกสารเดียว")]
b = hbars(items, 30, 225, 560, 760, 68, 100, pct, target=91, font=26, gap=0.28)
b = b.replace('font-size="21" style', 'font-size="19" style')
b += legend([(ORANGE, "ผ่านเป้า แต่ reused / ไม่ใช่ holdout อิสระ"), (RED, "ต่ำกว่าเป้า")], 70, 818, 640)
page("s12_accuracy", "แม่นเกิน 95% กับ PDF และภาพต้นฉบับ แต่ภาพ augmented และภาพหน้าจอยังต่ำกว่าเป้า", "Exact field accuracy แยกตามชนิดอินพุต (ห้ามรวมเป็นค่าเดียว)", b, "ที่มา: model/reports/ (final-dev, first-blind-test, regression-pdf-test, image-original-test-*, noise-all, augmented-dev-*, phone-all-final, peam-angles-after)")

# S13 — stacked 100% by stage
SEG = [("Tesseract OCR", ORANGE), ("Poppler (render/ดึงข้อความ)", "#F9B27C"), ("เรขาคณิต OpenCV", "#4B4A46"), ("จัดวาง/ถอดรหัสภาพ", "#9A978F"), ("parse + ซ่อม + ตรวจ", GREEN), ("อื่นๆ", "#D6D3CC")]
rows = [("PDF ผ่านเกณฑ์ข้อความฝัง", 0.12, [0, 0.099, 0, 0, 0.022, 0.002]),
        ("PDF ไม่ผ่านเกณฑ์ → OCR", 5.10, [3.825, 1.254, 0, 0.014, 0.010, 0.002]),
        ("ภาพ PNG 150 DPI", 8.87, [7.405, 0, 0.394, 1.058, 0.005, 0.007]),
        ("ภาพถ่ายจำลอง", 10.22, [7.838, 0, 0.458, 1.772, 0.008, 0.140])]
x0, y0, bw, rh = 480, 235, 900, 125
b = ""
for i, (lab, tot, parts) in enumerate(rows):
    y = y0 + i * rh; sm = sum(parts); x = x0
    b += f'<text x="{x0-18}" y="{y+68}" font-size="28" text-anchor="end">{esc(lab)}</text>'
    for (sl, col), v in zip(SEG, parts):
        w = bw * v / sm
        if w <= 0: continue
        b += f'<rect x="{x}" y="{y+18}" width="{w}" height="80" fill="{col}"/>'
        p = 100 * v / sm
        if p >= 6: b += f'<text x="{x+w/2}" y="{y+68}" font-size="25" font-weight="700" text-anchor="middle" style="stroke:none;fill:{"#fff" if col in (ORANGE, "#4B4A46", "#9A978F", GREEN) else DARK}">{p:.0f}%</text>'
        x += w
    b += f'<text x="{x0+bw+18}" y="{y+68}" font-size="30" font-weight="700">{tot:.2f} วินาที</text>'
b += legend([(c, n) for n, c in SEG[:3]], 70, 775, 520) + legend([(c, n) for n, c in SEG[3:]], 70, 820, 520)
page("s13_stages", "เวลาส่วนใหญ่หมดไปกับ Tesseract — parse ซ่อม และตรวจรวมกันไม่ถึง 0.03 วินาที", "สัดส่วนเวลาแต่ละขั้นตอนต่อไฟล์ (100%) และเวลาเฉลี่ยรวม · วัดในคอนเทนเนอร์ Docker (Apple Silicon, 10 CPU)", b, "ที่มา: model/reports/step-timing-20261009.json · เอกสาร test 8 ฉบับ · ภาพถ่ายจำลอง = หน้า PDF ที่หมุนและบิดมุมมอง ไม่ใช่ภาพถ่ายจริง")

# S14 — weak spots
items = [("ภาพเบลอ / คอนทราสต์ต่ำ", 57.18, RED, "augmented"), ("ภาพ perspective", 60.37, RED, "augmented"), ("ภาพ JPEG / มืด", 61.80, RED, "augmented"), ("ภาพถ่ายหน้าจอ 4 มุม", 70.50, RED, "เอกสารเดียว")]
b = hbars(items, 30, 235, 600, 700, 130, 100, pct, target=91, font=29, gap=0.38)
b += f'<text x="70" y="810" font-size="24" style="fill:{GRAY}">ภาพมือถือ: ผิด 24/885 ฟิลด์ — ชื่อวิชา 13 · วันที่ 4 · เกรด 3 · ชื่อคน 2 · คำนำหน้า 1 · รหัสวิชา 1</text>'
page("s14_weak", "ยังอ่านภาพเบลอ/มืด/เอียงแรงไม่ดี ต่ำกว่าเป้า 91%", "กลุ่มภาพที่ยังไม่ผ่านเป้า (exact field accuracy)", b, "ที่มา: model/reports/augmented-dev-deskew-full-20261004.json, peam-angles-after-20261004.json, phone-all-final-20261007.json")

# B4 — phone training results
items = [("ไม่ฝึก (มุม 2 ตรวจ)", 84.75, RED, "250/295"), ("ฝึกแล้ว (มุม 2 ตรวจ)", 97.63, ORANGE, "288/295 · เอกสารชุดเดียวกัน"),
         ("มุม 3 ครั้งแรก", 85.42, RED, "252/295 · ก่อนแก้ geometry"), ("มุม 3 หลังแก้ geometry", 97.29, ORANGE, "287/295 · reused"), ("ทั้ง 6 ภาพ", 97.29, ORANGE, "861/885")]
b = hbars(items, 30, 235, 520, 700, 112, 100, pct, target=91, font=28, gap=0.30)
b += legend([(ORANGE, "ผ่านเป้า แต่เอกสารชุดเดียวกับที่ฝึก"), (RED, "ต่ำกว่าเป้า")], 70, 818, 700)
page("b04_phone", "ฝึกเพิ่มช่วยได้จริง แต่ทุกผลวัดบนเอกสารชุดเดียวกัน", "ภาพมือถือ HEIC 6 ภาพ (2 เอกสาร × 3 มุม) · exact field accuracy · ใช้ตัวอ่านเดียวกัน", b, "ที่มา: model/reports/phone-training-summary-20261007.json")

# B5 — overfit protection
items = [("Noise dev · catalog รวมเอกสารนั้น", 94.42, "#9A978F", "in-sample · 1184/1254"), ("Noise dev · กันเอกสารออกจาก catalog", 92.11, GREEN, "document-held-out · 1155/1254"),
         ("ภาพต้นฉบับ dev 35 ฉบับ · กันเอกสารออก", 92.11, GREEN, "document-held-out · 4192/4551")]
b = hbars(items, 30, 250, 640, 600, 150, 100, pct, target=91, font=27, gap=0.40)
b += f'<text x="70" y="760" font-size="30" font-weight="700" style="fill:{GREEN}">กันเอกสารออกจาก catalog ทั้งฉบับ ผลลดลง 2.3 จุด (94.42 → 92.11)</text>'
b += f'<text x="70" y="806" font-size="23" style="fill:{GRAY}">ยังไม่ใช่ holdout อิสระของทั้งระบบ เพราะ parser เคยปรับบนชุด dev</text>'
page("b05_overfit", "กัน catalog ออกทั้งฉบับ ผลลดลงเพียง 2.3 จุด", "ผลของ course catalog ต่อความแม่นยำ: แบบรวมเอกสารที่วัดเข้า catalog เทียบกับแบบกันออก", b, "ที่มา: model/reports/noise-dev-term-fix.json, noise-dev-catalog-held-out.json, original-dev-catalog-held-out-all.json")
print("generated")
