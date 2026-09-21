#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab8a_denoise.py — Lab 8A : ทำเอกสารให้สะอาด และวัดว่า LLM "แก้" หรือ "ทำพัง"
วิชา 06026240 การพัฒนาระบบอัจฉริยะ · ภาควิชาเทคโนโลยีสารสนเทศ สจล.

ต่อยอดจาก Lab 7A ซึ่งสกัด transcript ได้แล้วบนเอกสารสะอาด
Lab 8A ตอบคำถามว่า "ถ้าเอกสารไม่สะอาดล่ะ จะเกิดอะไรขึ้น และแก้ได้แค่ไหน"

โครงของแล็บ
  1) สร้าง noise แบบควบคุมได้ 4 ระดับ L1-L4 (ground truth ไม่เปลี่ยน)
  2) รัน pipeline ของ Lab 7A บนทุกระดับ  → หา "จุดพัง"
  3) ทำความสะอาดด้วย OpenCV 3 ระดับ     → วัดว่ากู้คืนได้เท่าไร
  4) ให้ LLM แก้ข้อความหลัง OCR 2 แบบ    → วัดด้วย triage (แก้ถูก / ทำพัง)
  5) สรุปเป็นตารางเดียวเพื่อการตัดสินใจ

คำสั่งหลัก
  python3 lab8a_denoise.py check
  python3 lab8a_denoise.py selftest
  python3 lab8a_denoise.py noise   -i data/transcript.pdf -o work/noisy/
  python3 lab8a_denoise.py denoise -i work/noisy/L3_tilted_copy/page_01.png -m light -g gt/transcript_gt.json -o work/denoise_out/
  python3 lab8a_denoise.py sweep   -i work/noisy/ -g gt/transcript_gt.json -o work/out/
  python3 lab8a_denoise.py fix     -i work/out/ -g gt/transcript_gt.json -o work/fixed/
  python3 lab8a_denoise.py report  -i work/ -o work/report/

หลักการที่ห้ามลืม
  ข้อมูล transcript เป็นข้อมูลส่วนบุคคลตาม PDPA — ทุกขั้นตอนรันบนเครื่องตัวเอง
  ห้ามอัปโหลดขึ้น Colab / cloud / API ภายนอกโดยเด็ดขาด
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

# ═══════════════════════════════════════════════════════════════════════
#  ค่าคงที่ของแล็บ
# ═══════════════════════════════════════════════════════════════════════

OLLAMA_URL = os.environ.get("LAB8_OLLAMA_URL", "http://127.0.0.1:11434")
MODEL_OCR = os.environ.get("LAB8_MODEL_OCR", "scb10x/typhoon-ocr1.5-3b")
MODEL_TEXT = os.environ.get("LAB8_MODEL_TEXT", "qwen3:4b")

# ระดับ noise — ชื่อสั้นเพื่อใช้เป็นชื่อโฟลเดอร์
NOISE_LEVELS = ["L0_clean", "L1_light", "L2_watermark", "L3_tilted_copy", "L4_rescan"]

# วิธีทำความสะอาด
CLEAN_METHODS = ["none", "light", "heavy"]

# วิธีให้ LLM แก้ข้อความ
FIX_METHODS = ["none", "free", "constrained"]

# เกรดที่ระบบทะเบียนยอมรับ — นี่คือ "closed vocabulary" ที่ใช้บังคับ LLM
VALID_GRADES = {
    "A", "B+", "B", "C+", "C", "D+", "D", "F",
    "W", "S", "U", "I", "P", "T", "V", "AU",
}

# ฟิลด์ที่ห้าม LLM เดาเด็ดขาด (แก้ผิดแล้วกู้ไม่ได้ และกระทบสิทธิ์นักศึกษา)
# ใส่ทั้งชื่อของ schema ตัวอย่างใน selftest และชื่อจริงที่เฉลยของ Lab 7A ใช้
CRITICAL_FIELDS = ("grade", "grade_earn", "credits", "credit",
                   "code", "subject_id", "student_id")

DPI = 300


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 0 — ตรวจสภาพแวดล้อม
# ═══════════════════════════════════════════════════════════════════════

def check_environment() -> bool:
    """
    ตรวจว่าเครื่องพร้อมทำแล็บหรือยัง

    หลักการสำคัญ: dependency ที่ "พังเงียบ" ต้องเป็น required เสมอ
    - augraphy ขาด  -> สร้างชุด noise ไม่ได้เลย (พังดัง ไม่อันตราย)
    - opencv ขาด    -> ทำความสะอาดไม่ได้ (พังดัง)
    - Ollama ไม่ทำงาน -> ส่วนที่ 2-4 ทำไม่ได้ (พังดัง)
    ทั้งสามตัวพังแบบเห็นชัด จึงตรวจตรงนี้ทีเดียวจบ
    """
    print("=" * 68)
    print("  ตรวจสภาพแวดล้อม Lab 8A")
    print("=" * 68)
    ok = True

    # ── ไลบรารี Python ที่จำเป็น ────────────────────────────────────
    required = [
        ("cv2", "opencv-python", "ทำความสะอาดภาพ"),
        ("numpy", "numpy", "คำนวณเมทริกซ์ภาพ"),
        ("fitz", "pymupdf", "แปลง PDF เป็นภาพ"),
        ("augraphy", "augraphy", "สร้าง noise แบบควบคุมได้"),
        ("requests", "requests", "เรียก Ollama"),
    ]
    for mod, pipname, why in required:
        try:
            __import__(mod)
            print(f"  [ ok ] {pipname:<16} — {why}")
        except ImportError:
            print(f"  [FAIL] {pipname:<16} — {why}")
            print(f"         แก้ด้วย:  pip install {pipname}")
            ok = False

    # ── Ollama ──────────────────────────────────────────────────────
    try:
        import requests
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        names = [m["name"] for m in r.json().get("models", [])]
        print(f"  [ ok ] Ollama ทำงานอยู่ที่ {OLLAMA_URL}")
        for want in (MODEL_OCR, MODEL_TEXT):
            hit = any(n == want or n.startswith(want.split(":")[0]) for n in names)
            if hit:
                print(f"  [ ok ] พบโมเดล {want}")
            else:
                print(f"  [FAIL] ไม่พบโมเดล {want}")
                print(f"         แก้ด้วย:  ollama pull {want}")
                ok = False
    except Exception as e:
        print(f"  [FAIL] ต่อ Ollama ไม่ได้ ({type(e).__name__})")
        print(f"         เปิด service ด้วย:  ollama serve")
        ok = False

    print("=" * 68)
    print("  พร้อมทำแล็บ" if ok else "  ยังไม่พร้อม — แก้ตามข้อความ [FAIL] ข้างบนก่อน")
    print("=" * 68)
    return ok


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 1 — สร้าง noise แบบควบคุมได้
# ═══════════════════════════════════════════════════════════════════════
#
#  ทำไมต้อง "สร้าง" noise เอง แทนที่จะไปหาเอกสารสแกนจริงมาใช้
#
#    เพราะเราต้องรู้เฉลย 100%
#    ถ้าไปเก็บเอกสารสแกนจริงมา เราจะไม่มีทางรู้ว่า "ค่าจริง" คืออะไร
#    นอกจากนั่งพิมพ์เองทุกช่อง ซึ่งช้าและผิดพลาดได้
#    แต่ถ้าเราเอาเอกสารสะอาดที่มีเฉลยอยู่แล้ว (จาก Lab 7A) มาเติม noise
#    เฉลยเดิมยังใช้ได้ทุกระดับ ทำให้เปรียบเทียบข้ามระดับได้อย่างยุติธรรม
#
#    นี่คือหลัก "controlled degradation" ที่ใช้ในงานวิจัย document analysis จริง
# ═══════════════════════════════════════════════════════════════════════

def build_noise_pipeline(level: str, seed: int = 42):
    """
    คืน Augraphy pipeline สำหรับระดับ noise ที่ระบุ

    เอกสารสมัยนี้ส่วนใหญ่เป็นไฟล์ดิจิทัล (export/scan/แชร์ต่อ) ไม่ใช่กระดาษ
    ที่ผ่านเครื่องพิมพ์/เครื่องถ่ายเอกสารซ้ำหลายรอบ จึงจำลองแค่สิ่งที่เกิดจริง
    ตอนไฟล์ถูกบีบอัดซ้ำ (SubtleNoise/Jpeg) ส่วนลายน้ำ "COPY" และมุมเอียง
    ถูกใส่แยกต่างหากใน make_noise_dataset() เพราะ Augraphy ไม่มี op นี้
    """
    import numpy as np
    from augraphy import AugraphyPipeline, Jpeg, SubtleNoise

    np.random.seed(seed)

    if level == "L0_clean":
        # ระดับ 0 ไม่ใส่อะไรเลย ใช้เป็นเส้นฐานเปรียบเทียบ
        return None

    if level == "L1_light":
        # แค่บันทึกไฟล์ซ้ำเป็น JPEG คุณภาพสูง — แทบไม่ต่างจากต้นฉบับ
        return AugraphyPipeline(
            ink_phase=[], paper_phase=[],
            post_phase=[SubtleNoise(subtle_range=4, p=1.0),
                        Jpeg(quality_range=(85, 95), p=1.0)],
        )

    if level == "L2_watermark":
        # ไฟล์ที่แชร์ต่อพร้อมลายน้ำ "COPY" จาง ๆ + เอียงเล็กน้อยตอนสแกน
        return AugraphyPipeline(
            ink_phase=[], paper_phase=[],
            post_phase=[SubtleNoise(subtle_range=5, p=1.0),
                        Jpeg(quality_range=(75, 90), p=1.0)],
        )

    if level == "L3_tilted_copy":
        # สำเนาที่ถูกบีบอัดซ้ำหลายต่อ + ลายน้ำเข้มขึ้น + เอียงมากขึ้น
        return AugraphyPipeline(
            ink_phase=[], paper_phase=[],
            post_phase=[SubtleNoise(subtle_range=6, p=1.0),
                        Jpeg(quality_range=(60, 80), p=1.0)],
        )

    if level == "L4_rescan":
        # สแกนซ้ำจากสำเนา (ความละเอียดลด) + ลายน้ำเข้มสุด + เอียงสุด
        return AugraphyPipeline(
            ink_phase=[], paper_phase=[],
            post_phase=[SubtleNoise(subtle_range=8, p=1.0),
                        Jpeg(quality_range=(45, 65), p=1.0)],
        )

    raise ValueError(f"ไม่รู้จักระดับ noise: {level}")


def add_watermark_circle(img, opacity: float):
    """
    วาดลายน้ำเป็นตราปั๊มวงกลมสีส้มขนาดใหญ่กลางหน้า (วงแหวนซ้อน + เส้นรัศมีโดยรอบ)

    จำลองสถานการณ์ที่พบได้จริงในปัจจุบัน (เอกสาร export/แชร์ต่อมีตราปั๊มทับ)
    ใช้กับระดับ L2_watermark และเป็นส่วนหนึ่งของ L4_rescan
    """
    import cv2
    import numpy as np

    if opacity <= 0:
        return img

    h, w = img.shape[:2]
    layer = np.zeros((h, w, 3), dtype="uint8")
    color = (0, 140, 255)  # BGR ส้ม
    cx, cy = w // 2, h // 2
    radius = int(min(h, w) * 0.38)

    # วงแหวนซ้อนกันแบบตราปั๊ม
    for r in (radius, int(radius * 0.86)):
        cv2.circle(layer, (cx, cy), r, color, thickness=6, lineType=cv2.LINE_AA)

    # เส้นรัศมีรอบวง ให้ดูเป็นลวดลาย/ตราปั๊ม
    for deg in range(0, 360, 12):
        rad = np.radians(deg)
        p1 = (int(cx + radius * 0.6 * np.cos(rad)), int(cy + radius * 0.6 * np.sin(rad)))
        p2 = (int(cx + radius * 0.86 * np.cos(rad)), int(cy + radius * 0.86 * np.sin(rad)))
        cv2.line(layer, p1, p2, color, thickness=4, lineType=cv2.LINE_AA)

    M = cv2.getRotationMatrix2D((cx, cy), 20, 1.0)
    layer = cv2.warpAffine(layer, M, (w, h), borderMode=cv2.BORDER_CONSTANT,
                           borderValue=(0, 0, 0))

    mask = (layer.sum(axis=2) > 0)
    mask3 = np.repeat(mask[:, :, None], 3, axis=2)
    blended = cv2.addWeighted(img, 1 - opacity, layer, opacity, 0)
    return np.where(mask3, blended, img).astype("uint8")


def add_watermark_tiled_copy(img, opacity: float):
    """
    วาดคำว่า COPY สีเทาตัวหนา เอียง 30 องศา กระจายเต็มหน้า

    จำลองไฟล์ที่ถูกประทับ "COPY" ซ้ำหลายจุดตอน export/แชร์
    ใช้กับระดับ L3_tilted_copy และเป็นส่วนหนึ่งของ L4_rescan
    """
    import cv2
    import numpy as np

    if opacity <= 0:
        return img

    h, w = img.shape[:2]
    layer = np.zeros((h, w, 3), dtype="uint8")
    color = (150, 150, 150)  # BGR เทา
    scale = w / 700
    thickness = max(4, int(scale * 6))
    step_x, step_y = int(w / 2.0), int(h / 4.0)
    for y in range(step_y, h + step_y, step_y):
        for x in range(-step_x, w + step_x, step_x):
            cv2.putText(layer, "COPY", (x, y), cv2.FONT_HERSHEY_DUPLEX,
                       scale, color, thickness, cv2.LINE_AA)

    M = cv2.getRotationMatrix2D((w / 2, h / 2), 30, 1.0)
    layer = cv2.warpAffine(layer, M, (w, h), borderMode=cv2.BORDER_CONSTANT,
                           borderValue=(0, 0, 0))

    mask = (layer.sum(axis=2) > 0)
    mask3 = np.repeat(mask[:, :, None], 3, axis=2)
    blended = cv2.addWeighted(img, 1 - opacity, layer, opacity, 0)
    return np.where(mask3, blended, img).astype("uint8")


def pdf_to_images(pdf_path: Path, out_dir: Path, dpi: int = DPI) -> list[Path]:
    """แปลง PDF เป็นภาพ PNG หน้าละไฟล์ ที่ความละเอียด dpi"""
    import fitz
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    paths = []
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        p = out_dir / f"page_{i:02d}.png"
        pix.save(p)
        paths.append(p)
    doc.close()
    return paths


def apply_rotation(img, degrees: float):
    """
    หมุนภาพโดยเติมขอบด้วยสีขาว

    แยกออกมาจาก Augraphy เพราะเราต้องคุมมุมเองให้ได้แน่นอน
    เวลาทดสอบ deskew จะได้รู้ว่า "มุมจริง" คือเท่าไร
    """
    import cv2
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), degrees, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))


# มุมเอียงประจำแต่ละระดับ (องศา) — คงที่เพื่อให้ทำซ้ำได้
LEVEL_SKEW = {"L0_clean": 0.0, "L1_light": 0.3, "L2_watermark": 1.0,
              "L3_tilted_copy": 2.5, "L4_rescan": 4.0}

# อัตราลดความละเอียดของแต่ละระดับ (จำลองการสแกนที่ dpi ต่ำ)
LEVEL_SCALE = {"L0_clean": 1.0, "L1_light": 1.0, "L2_watermark": 1.0,
               "L3_tilted_copy": 0.95, "L4_rescan": 0.85}

# ความเข้มของลายน้ำตราปั๊มประจำแต่ละระดับ (0 = ไม่มี)
LEVEL_WATERMARK = {"L0_clean": 0.0, "L1_light": 0.0, "L2_watermark": 0.35,
                   "L3_tilted_copy": 0.45, "L4_rescan": 0.55}


def make_noise_dataset(src: Path, out_dir: Path, seed: int = 42) -> dict:
    """
    สร้างชุดข้อมูล noise ระดับ L1-L4 จากเอกสารต้นฉบับหนึ่งฉบับ

    ไม่สร้าง L0_clean เพราะเป็นต้นฉบับเดิม ใช้ไฟล์ที่ src ชี้ไว้ได้โดยตรงอยู่แล้ว
    ผลลัพธ์:  out_dir/L1_light/page_01.png, out_dir/L2_watermark/page_01.png, ...
    เฉลย (ground truth) ใช้ไฟล์เดิมของ Lab 7A ได้ทุกระดับ
    """
    import cv2
    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)

    # ขั้นที่ 1 — ได้ภาพสะอาดมาก่อน
    tmp = out_dir / "_source"
    if src.suffix.lower() == ".pdf":
        pages = pdf_to_images(src, tmp)
    elif src.is_dir():
        pages = sorted([p for p in src.iterdir()
                        if p.suffix.lower() in (".png", ".jpg", ".jpeg")])
    else:
        pages = [src]
    print(f"  ต้นฉบับ {len(pages)} หน้า")

    manifest = {"source": str(src), "seed": seed, "dpi": DPI, "levels": {}}

    # ขั้นที่ 2 — วนสร้างทีละระดับ (ข้าม L0_clean เพราะคือต้นฉบับเดิม ไม่ต้องสร้างซ้ำ)
    for level in NOISE_LEVELS[1:]:
        lv_dir = out_dir / level
        lv_dir.mkdir(parents=True, exist_ok=True)
        pipe = build_noise_pipeline(level, seed=seed)
        made = []

        for idx, p in enumerate(pages):
            img = cv2.imread(str(p))
            if img is None:
                print(f"    ! อ่านไม่ได้: {p}")
                continue

            # ลำดับสำคัญ: ย่อ -> หมุน -> ลายน้ำ -> จบด้วยการบีบอัด JPEG
            # เพราะในโลกจริง การ export ซ้ำ/เอกสารเอียงเกิดก่อน แล้วลายน้ำ
            # ถูกประทับตอน share/print ก่อนที่ไฟล์จะถูกบีบอัดครั้งสุดท้าย
            s = LEVEL_SCALE[level]
            if s < 1.0:
                img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            deg = LEVEL_SKEW[level]
            if abs(deg) > 1e-6:
                img = apply_rotation(img, deg)
            wm = LEVEL_WATERMARK[level]
            if level == "L2_watermark":
                img = add_watermark_circle(img, wm)
            elif level == "L3_tilted_copy":
                img = add_watermark_tiled_copy(img, wm)
            elif level == "L4_rescan":
                # L4 = ตราปั๊มวงกลมของ L2 + คำว่า COPY เอียงของ L3 ซ้อนกัน
                # แล้วเข้มขึ้นทั้งแผ่นเล็กน้อย จำลองการสแกนซ้ำจากสำเนา
                img = add_watermark_circle(img, LEVEL_WATERMARK["L2_watermark"])
                img = add_watermark_tiled_copy(img, LEVEL_WATERMARK["L3_tilted_copy"])
                img = cv2.convertScaleAbs(img, alpha=0.9, beta=0)
            if pipe is not None:
                img = pipe(img)
                if isinstance(img, dict):          # Augraphy บางรุ่นคืน dict
                    img = img["output"]
                img = np.asarray(img)
                if img.ndim == 2:
                    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

            dst = lv_dir / f"page_{idx + 1:02d}.png"
            cv2.imwrite(str(dst), img)
            made.append(dst.name)

        manifest["levels"][level] = {
            "pages": made,
            "skew_deg": LEVEL_SKEW[level],
            "scale": LEVEL_SCALE[level],
            "watermark_opacity": LEVEL_WATERMARK[level],
        }
        print(f"  [{level:<14}] {len(made)} หน้า  "
              f"(เอียง {LEVEL_SKEW[level]}° · ย่อ {LEVEL_SCALE[level]:.0%} · "
              f"ลายน้ำ {LEVEL_WATERMARK[level]:.0%})")

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 2 — ทำความสะอาดภาพด้วย OpenCV
# ═══════════════════════════════════════════════════════════════════════
#
#  คำเตือนที่นักศึกษาจะพิสูจน์เองในส่วนที่ 5
#
#    "สะอาดขึ้นในสายตาคน" ไม่ได้แปลว่า "OCR อ่านได้ดีขึ้น"
#    Typhoon-OCR เป็น VLM ที่ฝึกมาบนเอกสารสแกนจริงจำนวนมาก
#    มันจึง "คุ้นเคย" กับ noise ระดับหนึ่งอยู่แล้ว
#    การ binarize แรง ๆ จะตัดข้อมูล grayscale ที่โมเดลใช้แยกสระ/วรรณยุกต์ไทยทิ้ง
#    ผลคือภาพดูคมขึ้นสำหรับคน แต่โมเดลอ่านแย่ลง
# ═══════════════════════════════════════════════════════════════════════

def estimate_skew(gray) -> float:
    """
    ประมาณมุมเอียงจากเส้นแนวตั้งที่ยาวที่สุดในหน้าเอกสารด้วย Hough transform

    กรองเฉพาะเส้นที่เอียงจากแนวตั้งไม่เกิน 10 องศา แล้วคืนมุมสำหรับ
    apply_rotation() โดยตรง ถ้าไม่พบเส้นแนวตั้งที่ยาวพอจะคืน 0.0
    """
    import cv2
    import numpy as np

    if gray is None or gray.size == 0:
        return 0.0

    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)

    height, _ = gray.shape[:2]
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150, apertureSize=3)

    # ใช้ Probabilistic Hough เพื่อให้ได้ปลายเส้นและวัดความยาวจริงได้
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 1800,       # ความละเอียดมุม 0.1 องศา
        threshold=max(50, int(height * 0.05)),
        minLineLength=max(50, int(height * 0.20)),
        maxLineGap=max(10, int(height * 0.03)),
    )
    if lines is None:
        return 0.0

    longest = None
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        dx = float(x2 - x1)
        dy = float(y2 - y1)
        length = float(np.hypot(dx, dy))

        # มุมเบี่ยงจากแนวตั้ง: 0 คือเส้นตั้งตรง และทำให้ไม่ขึ้นกับลำดับปลายเส้น
        deviation = float(np.degrees(np.arctan2(dx, dy)))
        while deviation <= -90.0:
            deviation += 180.0
        while deviation > 90.0:
            deviation -= 180.0

        if abs(deviation) <= 10.0 and (longest is None or length > longest[0]):
            longest = (length, deviation)

    if longest is None:
        return 0.0

    # deviation คือมุมที่ภาพเอียงอยู่ จึงหมุนด้วยเครื่องหมายตรงข้ามเพื่อแก้กลับ
    return -longest[1]


def remove_watermark_tint(img):
    """
    ลบลายน้ำก่อนแปลงเป็น grayscale — ต้องทำก่อน estimate_skew() เสมอ
    ไม่งั้นเส้นลายน้ำเอียง ๆ จะไปปนกับตัวอักษรจริงตอนประมาณมุมเอียง

    ลายน้ำมีสองแบบ ต้องกรองคนละเงื่อนไข
      วงกลม/ตราปั๊ม (L2, L4) — สีส้ม จึงกรองด้วย Hue ช่วงเหลือง/ส้ม
      คำว่า COPY (L3, L4)   — สีเทา (satuation ต่ำ) ต่างจากตัวอักษรจริงที่เป็น
                              สีดำเข้ม (value ต่ำมาก) จึงกรองด้วยช่วง value กลาง ๆ แทน
    แล้วดึงบริเวณที่ตรงเงื่อนไขกลับเป็นสีขาวล้วน โดยไม่แตะตัวอักษรจริง
    """
    import cv2
    import numpy as np
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    orange_stamp = (h >= 15) & (h <= 40) & (v >= 120)
    gray_copy = (s <= 40) & (v >= 90) & (v <= 235)
    watermark = orange_stamp | gray_copy
    s = np.where(watermark, 0, s).astype("uint8")
    v = np.where(watermark, 255, v).astype("uint8")
    return cv2.cvtColor(cv2.merge([h, s, v]), cv2.COLOR_HSV2BGR)


def clean_image(img, method: str):
    """
    ทำความสะอาดภาพตามระดับที่เลือก

    none  — ไม่ทำอะไร (เส้นฐาน)
    light — ลบลายน้ำ + แก้เอียง + ลด noise เบา ๆ  แต่ "คงระดับสีเทาไว้"
    heavy — light + binarize แบบรักษาเส้นหมึก  ตัดเป็นขาวดำล้วน
    """
    import cv2
    if method == "none":
        return img

    # 0) ลบลายน้ำสีก่อนแปลงเป็น grayscale — ทำตอนยังมีสีอยู่เท่านั้น
    img = remove_watermark_tint(img)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img

    # 1) แก้ภาพเอียง — ทำก่อนเสมอ เพราะขั้นอื่นสมมติว่าบรรทัดอยู่แนวนอน
    ang = estimate_skew(gray)
    if abs(ang) > 0.1:
        gray = apply_rotation(gray, ang)

    # 2) ลด noise แบบรักษาขอบตัวอักษร
    gray = cv2.fastNlMeansDenoising(gray, None, h=7, templateWindowSize=7,
                                    searchWindowSize=21)

    if method == "light":
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    if method == "heavy":
        # 3) binarize แบบปรับตามพื้นที่ — ลด C เพื่อไม่ให้ threshold
        # กินขอบตัวอักษรบางๆ และใช้พื้นที่รอบข้างกว้างขึ้นเพื่อให้พื้นหลังนิ่ง
        bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, blockSize=41, C=7)
        # fastNlMeansDenoising ด้านบนเก็บ noise ไปแล้ว จึงไม่ทำ morphological
        # opening ซ้ำ เพราะ kernel 2x2 สามารถทำให้เส้นอักษรขนาด 1–2 px ขาดได้
        return cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)

    raise ValueError(f"ไม่รู้จักวิธีทำความสะอาด: {method}")


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 3 — เรียกใช้ main() ของ Lab 7A
# ═══════════════════════════════════════════════════════════════════════

def ollama_generate(model: str, prompt: str, images: list[str] | None = None,
                    fmt: str | None = None, timeout: int = 600) -> str:
    """เรียก Ollama บนเครื่องตัวเอง — ไม่มีการส่งข้อมูลออกนอกเครื่อง"""
    import base64
    import requests

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "num_ctx": 8192},
    }
    if images:
        payload["images"] = [
            base64.b64encode(Path(p).read_bytes()).decode() for p in images
        ]
    if fmt:
        payload["format"] = fmt

    r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json().get("response", "")


def parse_json_loose(s: str) -> dict:
    """ดึง JSON ออกจากคำตอบของโมเดล แม้จะมี fence หรือข้อความหุ้มมาด้วย"""
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S)
    s = re.sub(r"^```(?:json)?|```$", "", s.strip(), flags=re.M).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    depth = 0
    for i in range(start, len(s)) if start >= 0 else []:
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[start:i + 1])
                except json.JSONDecodeError:
                    break
    return {}


def _lab7_module():
    """โหลด Lab 7A แบบรองรับทั้ง package และการรันไฟล์ตรง"""
    try:
        from . import lab7a_transcript
    except ImportError:
        import lab7a_transcript
    return lab7a_transcript


def ocr_one_page(img_path: Path, lab7=None) -> str:
    """อ่านภาพหนึ่งหน้าเป็น Markdown โดยยังไม่โหลด text LLM"""
    lab7 = lab7 or _lab7_module()
    pages = lab7.load_pages(str(img_path))
    return lab7.ocr_pages_to_markdown(pages)


def structure_one_page(markdown: str, lab7=None) -> dict:
    """จัด Markdown หนึ่งหน้าเป็น JSON โดยไม่เรียก vision model ซ้ำ"""
    lab7 = lab7 or _lab7_module()
    return lab7.structure_markdown(markdown)


def extract_one_page(img_path: Path) -> tuple[str, dict]:
    """อ่านภาพด้วย pipeline VLM ของ Lab 7A แล้วคืน Markdown และ JSON"""
    lab7 = _lab7_module()
    lab7.assert_offline()
    t0 = time.time()
    md = ocr_one_page(img_path, lab7)
    rec = structure_one_page(md, lab7)
    rec["_meta"] = {
        "pipeline": "vlm",
        "elapsed_sec": round(time.time() - t0, 1),
        "models": {"ocr": lab7.MODEL_OCR, "text": lab7.MODEL_TEXT},
        "dpi": lab7.DPI,
    }
    return md, rec


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 4 — ให้ LLM แก้ข้อความหลัง OCR
# ═══════════════════════════════════════════════════════════════════════

FREE_FIX_PROMPT = """ข้อมูลใบแสดงผลการศึกษาต่อไปนี้ได้มาจาก OCR ที่อ่านเอกสารคุณภาพต่ำ
จึงมีตัวสะกดผิดและอักขระเพี้ยนอยู่ กรุณาแก้ไขให้ถูกต้อง

ตอบกลับเป็น JSON โครงสร้างเดิมทั้งหมด ไม่ต้องอธิบาย

ข้อมูล:
"""

CONSTRAINED_FIX_PROMPT = """ข้อมูลใบแสดงผลการศึกษาต่อไปนี้ได้มาจาก OCR ที่อ่านเอกสารคุณภาพต่ำ
งานของคุณคือแก้เฉพาะ "ชื่อวิชา" และ "ชื่อบุคคล" ที่สะกดผิดจาก OCR เท่านั้น

กติกาที่ห้ามฝ่าฝืน
1. ห้ามแก้ค่าในฟิลด์ code, credits, grade, student_id เด็ดขาด — คัดลอกมาตามเดิมทุกตัวอักษร
2. ถ้าไม่มั่นใจว่าค่าที่ถูกคืออะไร ให้ใส่ null ห้ามเดา
3. ห้ามเพิ่มหรือลบรายวิชา จำนวนรายการต้องเท่าเดิม
4. ห้ามคำนวณหรือเติมค่าที่หายไป

ตอบกลับเป็น JSON โครงสร้างเดิมทั้งหมด ไม่ต้องอธิบาย

ข้อมูล:
"""


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def snap_grade(value: Any) -> Any:
    """
    บังคับให้เกรดอยู่ในชุดที่ระบบทะเบียนยอมรับ

    - ถ้าตรงอยู่แล้ว        -> คืนค่าเดิม
    - ถ้าใกล้เคียงตัวเดียว   -> แก้ให้ (เช่น "8+" -> "B+" เพราะ 8 กับ B สับสนกันบ่อย)
    - ถ้าใกล้เคียงหลายตัว   -> คืน None (ให้คนตรวจ) ปลอดภัยกว่าเดา
    """
    if value is None:
        return None
    v = str(value).strip().upper().replace(" ", "")
    if v in VALID_GRADES:
        return v
    # แก้ความสับสนของ OCR ที่พบบ่อยก่อน
    table = str.maketrans({"8": "B", "6": "G", "0": "D", "1": "I", "5": "S"})
    v2 = v.translate(table)
    if v2 in VALID_GRADES:
        return v2
    cands = [g for g in VALID_GRADES if similar(v, g) >= 0.75]
    return cands[0] if len(cands) == 1 else None


def snap_code(value: Any, registry: set[str] | None) -> Any:
    """
    บังคับให้รหัสวิชาเป็นเลข 8 หลัก และ (ถ้ามีทะเบียนวิชา) ต้องมีอยู่จริง

    ทะเบียนวิชาคือ "closed vocabulary" ที่ดีที่สุดที่เรามี
    ถ้ารหัสที่ OCR อ่านได้ต่างจากรหัสจริงแค่หลักเดียว เราแก้ให้ได้อย่างมั่นใจ
    แต่ถ้าต่างสองหลักขึ้นไป อาจกลายเป็นวิชาอื่นได้จริง — จึงคืน None
    """
    if value is None:
        return None
    v = re.sub(r"\D", "", str(value))
    if registry is None:
        return v if len(v) == 8 else None
    if v in registry:
        return v
    near = [c for c in registry if len(c) == len(v)
            and sum(x != y for x, y in zip(c, v)) == 1]
    return near[0] if len(near) == 1 else None


def snap_credits(value: Any) -> Any:
    """หน่วยกิตต้องเป็นจำนวนเต็ม 0-12 เท่านั้น นอกช่วงนี้ถือว่าอ่านผิด"""
    if value is None:
        return None
    try:
        n = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= 12 else None


# ═══════════════════════════════════════════════════════════════════════
#  ตัวแปลง schema — ทำให้โค้ดบังคับข้อจำกัดทำงานกับเฉลยจริงได้
#
#  selftest ใช้ schema ตัวอย่างแบน ๆ  semesters[].courses[]
#  ที่มีคีย์ code / credits / grade
#  แต่เฉลยจริงของ Lab 7A ใช้    transcript_detail.semesters[].subject[]
#  ที่มีคีย์ subject_id / credit / grade_earn
#
#  ถ้าเดินเฉพาะ schema แรก โค้ดจะหาฟิลด์ไม่เจอแล้ว "เงียบ ๆ ไม่ทำอะไร"
#  ผลคือ pipeline constrained จะกลายเป็น free โดยที่ไม่มีใครรู้
# ═══════════════════════════════════════════════════════════════════════

COURSE_LIST_KEYS = ("courses", "subject")

# ฟิลด์เชิงตรรกะ -> ชื่อคีย์ที่เป็นไปได้ (schema ตัวอย่าง, schema จริง)
FIELD_ALIASES = {
    "code": ("code", "subject_id"),
    "grade": ("grade", "grade_earn"),
    "credits": ("credits", "credit"),
}


def _semesters_of(rec: Any) -> list:
    """ดึงรายการภาคเรียนออกจาก record ไม่ว่าจะเป็น schema แบบไหน"""
    if not isinstance(rec, dict):
        return []
    sems = rec.get("semesters")
    if sems is None:
        sems = (rec.get("transcript_detail") or {}).get("semesters")
    return sems or []


def _courses_of(sem: Any) -> list:
    """ดึงรายการวิชาในหนึ่งภาคเรียน"""
    if not isinstance(sem, dict):
        return []
    for key in COURSE_LIST_KEYS:
        courses = sem.get(key)
        if courses:
            return courses
    return []


def _course_key(course: dict, logical: str) -> str | None:
    """คืนชื่อคีย์จริงที่วิชานี้ใช้เก็บฟิลด์เชิงตรรกะที่ระบุ (None ถ้าไม่มี)"""
    for key in FIELD_ALIASES[logical]:
        if key in course:
            return key
    return None


def _snappers(registry: set[str] | None):
    """คู่ (ชื่อฟิลด์เชิงตรรกะ, ฟังก์ชัน snap) ที่ใช้บังคับข้อจำกัด"""
    return (
        ("grade", snap_grade),
        ("code", lambda v: snap_code(v, registry)),
        ("credits", snap_credits),
    )


def apply_hard_constraints(rec: dict, registry: set[str] | None = None) -> dict:
    """
    บังคับข้อจำกัดกับ record ด้วยโค้ด ไม่ใช่ด้วย prompt

    นี่คือจุดต่างสำคัญของ pipeline "constrained"
    prompt เป็นเพียง "การขอร้อง" โมเดลจะทำตามหรือไม่ก็ได้
    แต่โค้ดตรงนี้เป็น "การบังคับ" ที่โมเดลข้ามไม่ได้
    """
    rec = copy.deepcopy(rec)
    for sem in _semesters_of(rec):
        for c in _courses_of(sem):
            if not isinstance(c, dict):
                continue
            for logical, snap in _snappers(registry):
                key = _course_key(c, logical)
                if key is not None:
                    c[key] = snap(c[key])
    return rec


def llm_fix(rec: dict, method: str, registry: set[str] | None = None) -> dict:
    """แก้ข้อความหลัง OCR ตามวิธีที่เลือก"""
    if method == "none":
        return rec
    if method == "free":
        raw = ollama_generate(MODEL_TEXT,
                              FREE_FIX_PROMPT + json.dumps(rec, ensure_ascii=False),
                              fmt="json")
        out = parse_json_loose(raw)
        return out or rec
    if method == "constrained":
        raw = ollama_generate(MODEL_TEXT,
                              CONSTRAINED_FIX_PROMPT + json.dumps(rec, ensure_ascii=False),
                              fmt="json")
        out = parse_json_loose(raw) or rec
        # ขั้นบังคับด้วยโค้ด — ทำหลัง LLM เสมอ เพื่อกันโมเดลแอบแก้ฟิลด์ต้องห้าม
        out = apply_hard_constraints(out, registry)
        # ฟิลด์ต้องห้ามต้องเท่าเดิมจริง ๆ ไม่งั้นคืนค่าเดิมทับ
        out = restore_forbidden_fields(rec, out, registry)
        return out
    raise ValueError(f"ไม่รู้จักวิธีแก้: {method}")


def restore_forbidden_fields(orig: dict, fixed: dict,
                             registry: set[str] | None) -> dict:
    """
    ตรวจว่า LLM แอบแก้ฟิลด์ต้องห้ามหรือไม่ ถ้าแก้ ให้ดึงค่าเดิมกลับมา

    ยกเว้นกรณีเดียว: ค่าที่ผ่าน snap_* แล้วเปลี่ยน ถือว่าเป็นการแก้ด้วยกฎ ไม่ใช่การเดา
    """
    o_sems = _semesters_of(orig)
    f_sems = _semesters_of(fixed)
    for si, f_sem in enumerate(f_sems):
        if si >= len(o_sems):
            break
        o_courses = _courses_of(o_sems[si])
        f_courses = _courses_of(f_sem)
        for ci, fc in enumerate(f_courses):
            if ci >= len(o_courses):
                break
            oc = o_courses[ci]
            if not (isinstance(oc, dict) and isinstance(fc, dict)):
                continue
            for logical, snap in _snappers(registry):
                o_key = _course_key(oc, logical)
                if o_key is None:
                    continue
                # ถ้าโมเดลเปลี่ยนชื่อคีย์ ให้ทิ้งคีย์ใหม่แล้วใช้ชื่อเดิมเสมอ
                f_key = _course_key(fc, logical)
                if f_key is not None and f_key != o_key:
                    fc.pop(f_key, None)
                fc[o_key] = snap(oc[o_key])
    return fixed


def build_registry(gt: dict) -> set[str]:
    """
    สร้างทะเบียนรหัสวิชาจากเฉลย — ใช้ในแล็บเท่านั้น

    ในระบบจริง ทะเบียนนี้มาจากฐานข้อมูลรายวิชาของสำนักทะเบียน
    ซึ่งเป็นข้อมูลสาธารณะและไม่ใช่ข้อมูลส่วนบุคคล จึงใช้ได้อย่างถูกต้อง
    """
    codes = set()
    for sem in _semesters_of(gt):
        for c in _courses_of(sem):
            if not isinstance(c, dict):
                continue
            key = _course_key(c, "code")
            code = c.get(key) if key else None
            if code:
                codes.add(re.sub(r"\D", "", str(code)))
    return codes


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 5 — การวัดผล
# ═══════════════════════════════════════════════════════════════════════

def flatten(rec: Any, prefix: str = "") -> dict[str, Any]:
    """
    แผ่ record ให้เป็น {เส้นทางของฟิลด์: ค่า}

    ตัวอย่าง: semesters[0].courses[2].grade -> "B+"
    ทำแบบนี้เพื่อให้เทียบกับเฉลยได้ทีละฟิลด์ ไม่ใช่เทียบทั้งก้อน
    """
    out: dict[str, Any] = {}
    if isinstance(rec, dict):
        for k, v in rec.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(rec, list):
        for i, v in enumerate(rec):
            out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = rec
    return out


def norm(v: Any) -> str:
    """
    ปรับค่าให้เป็นรูปมาตรฐานก่อนเทียบ

    ทำไมต้อง normalize: OCR มักคืน "B +" หรือ " B+ " หรือ "b+"
    ถ้าไม่ปรับก่อน จะนับเป็นผิดทั้งที่เนื้อหาถูก ทำให้ประเมินโมเดลต่ำกว่าจริง
    แต่ต้องระวังไม่ normalize แรงเกินจนกลบความผิดที่มีความหมาย
    (เช่น ห้ามตัด "+" ทิ้ง เพราะ B กับ B+ คนละเกรด)
    """
    if v is None:
        return ""
    s = str(v).strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("\u200b", "").replace("\ufeff", "")
    # ตัวเลขไทยเป็นอารบิก
    s = s.translate(str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789"))
    return s.casefold()


def cer(ref: str, hyp: str) -> float:
    """Character Error Rate — ระยะแก้ไขระดับตัวอักษร หารด้วยความยาวเฉลย"""
    ref, hyp = str(ref), str(hyp)
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, rc in enumerate(ref, 1):
        cur = [i]
        for j, hc in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc)))
        prev = cur
    return prev[-1] / len(ref)


@dataclass
class Triage:
    """
    ผลการจำแนกว่าการ "แก้" ของ LLM ให้ผลอย่างไรในแต่ละฟิลด์

    นี่คือหัวใจของ Lab 8A ทั้งแล็บ

    ตัวเลข accuracy เพียงตัวเดียวโกหกได้ง่ายมาก
    วิธีที่แก้ถูก 10 ช่อง แต่ทำพัง 8 ช่อง จะได้กำไรสุทธิ +2
    ดูเผิน ๆ เหมือนดีขึ้น แต่ใช้กับ transcript ไม่ได้เลย
    เพราะเราไม่มีทางรู้ว่า 8 ช่องที่พังคือช่องไหน — ต้องตรวจใหม่ทั้งใบอยู่ดี
    """
    fixed: int = 0             # เดิมผิด -> แก้แล้วถูก        (กำไร)
    corrupted: int = 0         # เดิมถูก -> แก้แล้วผิด        (ขาดทุน อันตรายที่สุด)
    kept_ok: int = 0           # เดิมถูก -> ยังถูก             (ไม่เปลี่ยน ดี)
    not_fixed: int = 0         # เดิมผิด -> ยังผิดเท่าเดิม     (ไม่เปลี่ยน เฉย ๆ)
    changed_wrong: int = 0     # เดิมผิด -> เปลี่ยนแต่ยังผิด    (เสียเวลาเปล่า)
    abstained_ok: int = 0      # เดิมถูก -> ตอบ null           (เสียของ แต่ปลอดภัย)
    abstained_bad: int = 0     # เดิมผิด -> ตอบ null           (ดีมาก ยอมรับว่าไม่รู้)
    critical_corrupted: int = 0  # corrupted ที่เกิดในฟิลด์สำคัญ
    examples: list = field(default_factory=list)

    @property
    def net(self) -> int:
        """กำไรสุทธิ — ตัวเลขที่คนมักดูตัวเดียวแล้วตัดสินใจผิด"""
        return self.fixed - self.corrupted

    @property
    def safety(self) -> float:
        """
        อัตราส่วนความปลอดภัย = แก้ถูก / (แก้ถูก + ทำพัง)

        1.00 = แก้แล้วไม่เคยทำพังเลย  ใช้กับงานที่ตรวจซ้ำไม่ได้
        0.50 = แก้ถูกเท่ากับทำพัง      ไม่มีประโยชน์
        ต่ำกว่า 0.90 ไม่ควรใช้กับ transcript
        """
        d = self.fixed + self.corrupted
        return self.fixed / d if d else 1.0


def triage(base: dict, fixed_rec: dict, gt: dict,
           max_examples: int = 12) -> Triage:
    """เทียบสามทาง: ก่อนแก้ / หลังแก้ / เฉลย แล้วจำแนกทุกฟิลด์"""
    fb, ff, fg = flatten(base), flatten(fixed_rec), flatten(gt)
    t = Triage()
    for key, g in fg.items():
        b = fb.get(key)
        f = ff.get(key, b)
        gn, bn, fn = norm(g), norm(b), norm(f)
        b_ok, f_ok = (bn == gn), (fn == gn)
        is_null = (f is None or fn == "")
        is_crit = any(key.endswith(c) for c in CRITICAL_FIELDS)

        if is_null and not (g is None or gn == ""):
            if b_ok:
                t.abstained_ok += 1
            else:
                t.abstained_bad += 1
        elif b_ok and f_ok:
            t.kept_ok += 1
        elif b_ok and not f_ok:
            t.corrupted += 1
            if is_crit:
                t.critical_corrupted += 1
            if len(t.examples) < max_examples:
                t.examples.append({"field": key, "kind": "CORRUPTED",
                                   "gt": g, "before": b, "after": f})
        elif (not b_ok) and f_ok:
            t.fixed += 1
            if len(t.examples) < max_examples:
                t.examples.append({"field": key, "kind": "FIXED",
                                   "gt": g, "before": b, "after": f})
        elif bn == fn:
            t.not_fixed += 1
        else:
            t.changed_wrong += 1
    return t


def field_accuracy(pred: dict, gt: dict) -> dict:
    """
    ความถูกต้องระดับฟิลด์ + CER เฉลี่ย + จำนวน hallucination

    hallucination = เฉลยว่างเปล่า แต่โมเดลใส่ค่ามาให้
    (แนวคิดเดียวกับคอลัมน์ Hall ใน Lab 7A)
    """
    fp, fg = flatten(pred), flatten(gt)
    total = correct = hall = 0
    cer_sum = 0.0
    for key, g in fg.items():
        p = fp.get(key)
        gn, pn = norm(g), norm(p)
        total += 1
        if gn == pn:
            correct += 1
        cer_sum += cer(gn, pn)
        if gn == "" and pn != "":
            hall += 1
    # ฟิลด์ที่โมเดลสร้างเกินมาจากเฉลย ก็นับเป็น hallucination เช่นกัน
    hall += sum(1 for k, v in fp.items() if k not in fg and norm(v) != "")
    return {
        "fields": total,
        "correct": correct,
        "accuracy": correct / total if total else 0.0,
        "cer": cer_sum / total if total else 0.0,
        "hallucinated": hall,
    }


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 6 — คำสั่ง sweep : รันทุกระดับ noise × ทุกวิธีทำความสะอาด
# ═══════════════════════════════════════════════════════════════════════

def cmd_sweep(args) -> None:
    import cv2

    noisy_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    gt = json.loads(Path(args.gt).read_text(encoding="utf-8"))

    levels = args.levels.split(",") if args.levels else NOISE_LEVELS
    methods = args.methods.split(",") if args.methods else CLEAN_METHODS

    # รวมงานตามโมเดล: Typhoon อ่านทุกภาพให้เสร็จ แล้ว Qwen ค่อยจัด JSON ทั้งหมด
    # ช่วยลดการโหลดโมเดลสลับไปมาบนการ์ดจอที่มี VRAM ไม่พอวางสองโมเดลพร้อมกัน
    lab7 = _lab7_module()
    lab7.assert_offline()
    jobs = []
    for level in levels:
        lv_dir = noisy_dir / level
        if not lv_dir.is_dir():
            print(f"  ! ข้าม {level} (ไม่พบโฟลเดอร์)")
            continue
        pages = sorted(lv_dir.glob("page_*.png"))
        for method in methods:
            tag = f"{level}__{method}"
            work = out_dir / tag
            work.mkdir(parents=True, exist_ok=True)
            t_ocr = time.time()

            cleaned = []
            for p in pages:
                img = cv2.imread(str(p))
                out_img = clean_image(img, method)
                q = work / p.name
                cv2.imwrite(str(q), out_img)
                cleaned.append(q)

            markdown_pages = []
            for q in cleaned:
                try:
                    md = ocr_one_page(q, lab7)
                except Exception as e:
                    print(f"    ! {tag} {q.name}: {type(e).__name__} {e}")
                    continue
                (work / f"{q.stem}.md").write_text(md, encoding="utf-8")
                markdown_pages.append((q, md))

            jobs.append({
                "level": level,
                "method": method,
                "tag": tag,
                "work": work,
                "markdown_pages": markdown_pages,
                "ocr_seconds": time.time() - t_ocr,
            })

    print("\n  OCR ครบแล้ว — เริ่มจัด Markdown เป็น JSON ต่อเนื่อง...")
    rows = []
    for job in jobs:
        t_json = time.time()
        level = job["level"]
        method = job["method"]
        tag = job["tag"]
        work = job["work"]
        merged = {
            "header_detail": {},
            "transcript_detail": {"semesters": []},
            "footer_detail": {},
        }
        for q, md in job["markdown_pages"]:
            try:
                rec = structure_one_page(md, lab7)
            except Exception as e:
                print(f"    ! {tag} {q.name}: {type(e).__name__} {e}")
                continue

            if not merged["header_detail"] and rec.get("header_detail"):
                merged["header_detail"] = rec["header_detail"]
            transcript = rec.get("transcript_detail") or {}
            merged["transcript_detail"]["semesters"].extend(
                transcript.get("semesters") or [])
            for key, value in transcript.items():
                if key != "semesters" and value is not None:
                    merged["transcript_detail"][key] = value
            if rec.get("footer_detail"):
                merged["footer_detail"] = rec["footer_detail"]

        (work / "extracted.json").write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        m = field_accuracy(merged, gt)
        elapsed = job["ocr_seconds"] + (time.time() - t_json)
        m.update({"level": level, "clean": method,
                  "seconds": round(elapsed, 1)})
        rows.append(m)
        print(f"  [{tag:<24}] acc={m['accuracy']:.3f}  "
              f"CER={m['cer']:.3f}  hall={m['hallucinated']}  "
              f"({m['seconds']:.0f}s)")

    # รวมกับผลของรอบก่อนหน้า แทนการเขียนทับ เพื่อให้รัน --levels/--methods
    # เป็นบางส่วนได้เรื่อย ๆ โดยไม่เสียผลที่เคยรันไปแล้ว
    sweep_path = out_dir / "sweep.json"
    merged_rows = {}
    if sweep_path.exists():
        for r in json.loads(sweep_path.read_text(encoding="utf-8")):
            merged_rows[(r["level"], r["clean"])] = r
    for r in rows:
        merged_rows[(r["level"], r["clean"])] = r
    rows = list(merged_rows.values())

    sweep_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print_sweep_table(rows)


def print_sweep_table(rows: list[dict]) -> None:
    """ตารางเปรียบเทียบ ระดับ noise (แถว) × วิธีทำความสะอาด (คอลัมน์)"""
    if not rows:
        return
    methods = sorted({r["clean"] for r in rows}, key=CLEAN_METHODS.index)
    print()
    print("  ความถูกต้องระดับฟิลด์ (ยิ่งสูงยิ่งดี)")
    print("  " + "-" * 62)
    print("  {:<14}".format("ระดับ noise") + "".join(f"{m:>14}" for m in methods))
    print("  " + "-" * 62)
    for level in NOISE_LEVELS:
        sel = {r["clean"]: r for r in rows if r["level"] == level}
        if not sel:
            continue
        line = "  {:<14}".format(level)
        best = max((sel[m]["accuracy"] for m in methods if m in sel), default=0)
        for m in methods:
            if m in sel:
                v = sel[m]["accuracy"]
                mark = " *" if abs(v - best) < 1e-9 else "  "
                line += f"{v:>12.3f}{mark}"
            else:
                line += f"{'-':>14}"
        print(line)
    print("  " + "-" * 62)
    print("  * = ดีที่สุดของแถวนั้น")


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 7 — คำสั่ง fix : ให้ LLM แก้ แล้ว triage
# ═══════════════════════════════════════════════════════════════════════

def cmd_fix(args) -> None:
    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    gt = json.loads(Path(args.gt).read_text(encoding="utf-8"))
    registry = build_registry(gt) if args.use_registry else None
    if registry:
        print(f"  ใช้ทะเบียนรหัสวิชา {len(registry)} รายการ")

    targets = sorted(p for p in in_dir.glob("*/extracted.json"))
    if not targets:
        print(f"  ! ไม่พบ extracted.json ใน {in_dir} — รัน sweep ก่อน")
        return

    methods = args.methods.split(",") if args.methods else ["free", "constrained"]
    report = []

    for src in targets:
        tag = src.parent.name
        base = json.loads(src.read_text(encoding="utf-8"))
        for method in methods:
            t0 = time.time()
            try:
                fixed_rec = llm_fix(base, method, registry)
            except Exception as e:
                print(f"  ! {tag}/{method}: {type(e).__name__} {e}")
                continue
            d = out_dir / f"{tag}__fix_{method}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "fixed.json").write_text(
                json.dumps(fixed_rec, ensure_ascii=False, indent=2), encoding="utf-8")

            t = triage(base, fixed_rec, gt)
            before = field_accuracy(base, gt)
            after = field_accuracy(fixed_rec, gt)
            row = {
                "tag": tag, "fix": method,
                "acc_before": round(before["accuracy"], 4),
                "acc_after": round(after["accuracy"], 4),
                "fixed": t.fixed, "corrupted": t.corrupted,
                "critical_corrupted": t.critical_corrupted,
                "not_fixed": t.not_fixed, "changed_wrong": t.changed_wrong,
                "abstained_bad": t.abstained_bad, "abstained_ok": t.abstained_ok,
                "net": t.net, "safety": round(t.safety, 3),
                "seconds": round(time.time() - t0, 1),
            }
            report.append(row)
            (d / "triage.json").write_text(
                json.dumps({**row, "examples": t.examples},
                           ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  [{tag}/{method:<11}] "
                  f"acc {before['accuracy']:.3f} -> {after['accuracy']:.3f} | "
                  f"แก้ถูก {t.fixed:>3}  ทำพัง {t.corrupted:>3} "
                  f"(สำคัญ {t.critical_corrupted}) | safety {t.safety:.2f}")

    (out_dir / "fix_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_triage_table(report)


def print_triage_table(rows: list[dict]) -> None:
    if not rows:
        return
    print()
    print("  ตาราง triage — ทำไม accuracy ตัวเดียวจึงไม่พอ")
    print("  " + "-" * 90)
    print("  {:<26}{:<12}{:>8}{:>8}{:>8}{:>9}{:>10}".format(
        "ชุดข้อมูล", "วิธีแก้", "แก้ถูก", "ทำพัง", "สุทธิ", "สำคัญพัง", "safety"))
    print("  " + "-" * 90)
    for r in rows:
        warn = "  <-- อันตราย" if r["critical_corrupted"] > 0 else ""
        print("  {:<26}{:<12}{:>8}{:>8}{:>8}{:>9}{:>10.2f}{}".format(
            r["tag"][:25], r["fix"], r["fixed"], r["corrupted"],
            r["net"], r["critical_corrupted"], r["safety"], warn))
    print("  " + "-" * 90)
    print("  สุทธิ = แก้ถูก - ทำพัง   ·   safety = แก้ถูก / (แก้ถูก + ทำพัง)")
    print("  ถ้ามีการทำพังในฟิลด์สำคัญแม้ช่องเดียว ห้ามนำวิธีนั้นไปใช้กับ transcript จริง")


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 8 — รายงานรวม
# ═══════════════════════════════════════════════════════════════════════

def cmd_report(args) -> None:
    root = Path(args.input)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    sweep = _load_json(root / "out" / "sweep.json") or _load_json(root / "sweep.json")
    fixrep = (_load_json(root / "fixed" / "fix_report.json")
              or _load_json(root / "fix_report.json"))

    lines = ["level,clean,accuracy,cer,hallucinated,seconds"]
    for r in sweep or []:
        lines.append("{level},{clean},{accuracy:.4f},{cer:.4f},"
                     "{hallucinated},{seconds}".format(**r))
    (out / "sweep.csv").write_text("\n".join(lines), encoding="utf-8")

    lines = ["tag,fix,acc_before,acc_after,fixed,corrupted,"
             "critical_corrupted,net,safety"]
    for r in fixrep or []:
        lines.append("{tag},{fix},{acc_before},{acc_after},{fixed},"
                     "{corrupted},{critical_corrupted},{net},{safety}".format(**r))
    (out / "triage.csv").write_text("\n".join(lines), encoding="utf-8")

    if sweep:
        print_sweep_table(sweep)
        plot_ascii(sweep)
    if fixrep:
        print_triage_table(fixrep)
    print(f"\n  บันทึก CSV ที่ {out}/")


def plot_ascii(rows: list[dict], width: int = 40) -> None:
    """กราฟแท่งแบบตัวอักษร — หา 'จุดพัง' ได้โดยไม่ต้องเปิดโปรแกรมอื่น"""
    print()
    print("  ความถูกต้องเทียบกับระดับ noise (วิธี clean=none)")
    for level in NOISE_LEVELS:
        r = next((x for x in rows if x["level"] == level and x["clean"] == "none"), None)
        if not r:
            continue
        n = int(round(r["accuracy"] * width))
        print(f"  {level:<14}|{'#' * n}{'.' * (width - n)}| {r['accuracy']:.3f}")


def _load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 9 — selftest : ตรวจว่าโค้ดวัดผลถูกก่อนเผาเวลา GPU
# ═══════════════════════════════════════════════════════════════════════

def cmd_selftest(args=None) -> bool:
    """
    ทดสอบตรรกะการวัดผลด้วยข้อมูลสมมติที่เรารู้คำตอบอยู่แล้ว

    ทำไมต้องมีขั้นนี้: การรัน OCR ครบทุกระดับใช้เวลาเป็นชั่วโมง
    ถ้าโค้ดวัดผลผิด จะรู้ตัวก็ต่อเมื่อเสียเวลาไปหมดแล้ว
    """
    print("=" * 68)
    print("  selftest — ตรวจตรรกะการวัดผล")
    print("=" * 68)
    passed = failed = 0

    def ck(name, got, want):
        nonlocal passed, failed
        if got == want:
            print(f"  [ ok ] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name}: ได้ {got!r} ต้องการ {want!r}")
            failed += 1

    # 1) normalize
    ck("norm ตัดช่องว่าง", norm(" B+ "), "b+")
    ck("norm เลขไทย", norm("๓.๕๐"), "3.50")
    ck("norm ไม่กลืน + ทิ้ง", norm("B") == norm("B+"), False)

    # 2) CER
    ck("cer เหมือนกัน", cer("abc", "abc"), 0.0)
    ck("cer ผิดหนึ่งตัว", round(cer("abc", "abd"), 4), round(1 / 3, 4))

    # 3) snap_grade — ต้องแก้ที่แก้ได้ และคืน None เมื่อกำกวม
    ck("snap 8+ เป็น B+", snap_grade("8+"), "B+")
    ck("snap b เป็น B", snap_grade(" b "), "B")
    ck("snap ขยะคืน None", snap_grade("###"), None)

    # 4) snap_code
    reg = {"06026240", "06026241", "90130001"}
    ck("code ต่างหลักเดียวแก้ได้", snap_code("06026241", reg), "06026241")
    ck("code ต่างสองหลักคืน None", snap_code("06026999", reg), None)
    ck("code ที่มีอยู่ผ่าน", snap_code("90130001", reg), "90130001")

    # 5) snap_credits
    ck("credits ปกติ", snap_credits("3"), 3)
    ck("credits นอกช่วงคืน None", snap_credits("33"), None)

    # 5b) ตัวบังคับข้อจำกัดต้องทำงานกับ schema จริงของ Lab 7A ด้วย
    #     เคสชุดนี้มีไว้กันไม่ให้ constrained กลายเป็น free แบบเงียบ ๆ อีก
    real = {"transcript_detail": {"semesters": [{"subject": [
        {"subject_id": "06026241", "subject_name": "คอมพิวเตอร์วิทัศน์",
         "credit": 3, "grade_earn": "B+"},
    ]}]}}
    ck("registry อ่าน schema จริงได้", build_registry(real), {"06026241"})

    dirty = copy.deepcopy(real)
    sub = dirty["transcript_detail"]["semesters"][0]["subject"][0]
    sub["grade_earn"], sub["credit"] = "b+", "99"
    snapped = apply_hard_constraints(dirty, {"06026241"})
    s_sub = snapped["transcript_detail"]["semesters"][0]["subject"][0]
    ck("snap เกรดใน schema จริง", s_sub["grade_earn"], "B+")
    ck("snap หน่วยกิตนอกช่วงใน schema จริง", s_sub["credit"], None)

    tampered = copy.deepcopy(real)
    tampered["transcript_detail"]["semesters"][0]["subject"][0]["grade_earn"] = "A"
    restored = restore_forbidden_fields(real, tampered, {"06026241"})
    ck("กันโมเดลแอบแก้เกรดใน schema จริง",
       restored["transcript_detail"]["semesters"][0]["subject"][0]["grade_earn"],
       "B+")

    # 5c) ฟิลด์สำคัญที่ใช้ชื่อจริงต้องถูกนับเป็น critical ครบทุกตัว
    ck("critical ครอบคลุมชื่อฟิลด์จริง",
       [k for k in ("a.subject_id", "a.credit", "a.grade_earn",
                    "header_detail.student_id")
        if not any(k.endswith(c) for c in CRITICAL_FIELDS)], [])

    # 6) triage — กรณีสำคัญที่สุด
    gt = {"semesters": [{"courses": [
        {"code": "06026240", "name": "ระบบอัจฉริยะ", "credits": 3, "grade": "B+"},
        {"code": "06026241", "name": "คอมพิวเตอร์วิทัศน์", "credits": 3, "grade": "A"},
    ]}]}
    base = copy.deepcopy(gt)
    base["semesters"][0]["courses"][0]["name"] = "ระบบอัจฉรืยะ"   # ผิด (จะถูกแก้)
    fixed_rec = copy.deepcopy(gt)
    fixed_rec["semesters"][0]["courses"][1]["grade"] = "A-"        # เดิมถูก -> พัง
    t = triage(base, fixed_rec, gt)
    ck("triage นับ fixed", t.fixed, 1)
    ck("triage นับ corrupted", t.corrupted, 1)
    ck("triage สุทธิเป็นศูนย์", t.net, 0)
    ck("triage จับ critical", t.critical_corrupted, 1)
    ck("triage safety = 0.5", t.safety, 0.5)

    # 7) abstain นับแยกจริง
    ab = copy.deepcopy(gt)
    ab["semesters"][0]["courses"][0]["name"] = None
    t2 = triage(base, ab, gt)
    ck("abstain จากค่าที่เดิมผิด", t2.abstained_bad, 1)
    ck("abstain ไม่ถูกนับเป็น corrupted", t2.corrupted, 0)

    # 8) hallucination
    gt_h = {"header": {"name_th": "สมชาย", "name_en": ""}}
    pred_h = {"header": {"name_th": "สมชาย", "name_en": "Somchai"}}
    ck("นับ hallucination", field_accuracy(pred_h, gt_h)["hallucinated"], 1)

    # 9) โครงสร้างภาพ (ไม่ต้องใช้ Ollama)
    try:
        import cv2
        import numpy as np
        blank = np.full((200, 400, 3), 255, dtype="uint8")
        cv2.putText(blank, "06026240 B+", (10, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        cv2.line(blank, (350, 15), (350, 185), (0, 0, 0), 2)
        rot = apply_rotation(blank, 3.0)
        est = estimate_skew(cv2.cvtColor(rot, cv2.COLOR_BGR2GRAY))
        ck("deskew หาเส้นตั้งและคืนมุมหมุนกลับ", abs(est + 3.0) < 1.0, True)
        for m in CLEAN_METHODS:
            out = clean_image(blank, m)
            assert out.shape[:2] == blank.shape[:2]
        ck("clean_image ทุกวิธีคืนภาพขนาดเดิม", True, True)
    except ImportError:
        print("  [skip] ไม่มี opencv จึงข้ามการทดสอบภาพ")

    print("=" * 68)
    print(f"  ผ่าน {passed} · ไม่ผ่าน {failed}")
    print("=" * 68)
    return failed == 0


# ═══════════════════════════════════════════════════════════════════════
#  ส่วนที่ 10 — denoise : ทำความสะอาด + OCR + เทียบ gt ให้ภาพเดียว
# ═══════════════════════════════════════════════════════════════════════
#
#  ต่างจาก sweep ตรงที่ทำทีละภาพ ใช้ตอนอยากทดสอบไวว่า level/method คู่ไหน
#  ใช้ได้จริง โดยไม่ต้องรอให้ครบทุก combination ก่อน
# ═══════════════════════════════════════════════════════════════════════

def cmd_denoise(args) -> None:
    import cv2

    src = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    gt = json.loads(Path(args.gt).read_text(encoding="utf-8"))

    t_start = time.time()

    def step(msg: str) -> None:
        print(f"  [{time.time() - t_start:6.1f}s] {msg}")

    step(f"[1/3] อ่านภาพ {src} แล้วทำความสะอาดด้วยวิธี '{args.method}' ...")
    img = cv2.imread(str(src))
    if img is None:
        raise SystemExit(f"❌ อ่านภาพไม่ได้: {src}")
    cleaned = clean_image(img, args.method)
    cleaned_path = out_dir / f"{src.stem}__{args.method}.png"
    cv2.imwrite(str(cleaned_path), cleaned)
    step(f"      บันทึกภาพที่สะอาดแล้ว: {cleaned_path}")

    step("[2/3] เรียก Lab 7A OCR ภาพที่สะอาดแล้ว ...")
    md, rec = extract_one_page(cleaned_path)
    (out_dir / f"{src.stem}.md").write_text(md, encoding="utf-8")
    pred_path = out_dir / f"{src.stem}__pred.json"
    pred_path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    step(f"      บันทึกผลที่โมเดลอ่านได้: {pred_path}")

    step("[3/3] เทียบผลกับ ground truth ...")
    m = field_accuracy(rec, gt)
    step(f"      accuracy={m['accuracy']:.3f}  CER={m['cer']:.3f}  "
         f"hallucinated={m['hallucinated']}  ({m['correct']}/{m['fields']} ฟิลด์ถูก)")

    print(f"\n  เสร็จสิ้น รวมเวลา {time.time() - t_start:.1f} วินาที")


# ═══════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Lab 8A — ทำเอกสารให้สะอาด และวัดว่า LLM แก้หรือทำพัง",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="ตรวจสภาพแวดล้อม")
    sub.add_parser("selftest", help="ทดสอบตรรกะการวัดผล (ไม่ต้องใช้ Ollama)")

    p = sub.add_parser("noise", help="สร้างชุดข้อมูล noise 4 ระดับ (L1-L4)")
    p.add_argument("-i", "--input", required=True, help="PDF หรือโฟลเดอร์ภาพต้นฉบับ")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--seed", type=int, default=42)

    p = sub.add_parser("denoise", help="ทำความสะอาด + OCR + เทียบ gt ให้ภาพเดียว")
    p.add_argument("-i", "--input", required=True,
                   help="ไฟล์ภาพ noise ไฟล์เดียว เช่น work/noisy/L3_tilted_copy/page_01.png")
    p.add_argument("-m", "--method", default="light", choices=CLEAN_METHODS,
                   help="วิธีทำความสะอาด (none/light/heavy)")
    p.add_argument("-g", "--gt", required=True, help="ไฟล์เฉลย JSON")
    p.add_argument("-o", "--output", default="work/denoise_out", help="โฟลเดอร์ผลลัพธ์")

    p = sub.add_parser("sweep", help="รัน OCR ทุกระดับ x ทุกวิธีทำความสะอาด")
    p.add_argument("-i", "--input", required=True, help="โฟลเดอร์ที่ได้จาก noise")
    p.add_argument("-g", "--gt", required=True, help="ไฟล์เฉลย JSON")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--levels", default="", help="เช่น L0_clean,L2_watermark")
    p.add_argument("--methods", default="", help="เช่น none,light")

    p = sub.add_parser("fix", help="ให้ LLM แก้ข้อความ แล้ว triage")
    p.add_argument("-i", "--input", required=True, help="โฟลเดอร์ที่ได้จาก sweep")
    p.add_argument("-g", "--gt", required=True)
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--methods", default="", help="เช่น free,constrained")
    p.add_argument("--use-registry", action="store_true",
                   help="ใช้ทะเบียนรหัสวิชาช่วยแก้รหัส")

    p = sub.add_parser("report", help="สรุปผลเป็นตารางและ CSV")
    p.add_argument("-i", "--input", required=True, help="โฟลเดอร์ work/")
    p.add_argument("-o", "--output", required=True)

    args = ap.parse_args()

    if args.cmd == "check":
        sys.exit(0 if check_environment() else 1)
    if args.cmd == "selftest":
        sys.exit(0 if cmd_selftest(args) else 1)
    if args.cmd == "noise":
        make_noise_dataset(Path(args.input), Path(args.output), args.seed)
    elif args.cmd == "denoise":
        cmd_denoise(args)
    elif args.cmd == "sweep":
        cmd_sweep(args)
    elif args.cmd == "fix":
        cmd_fix(args)
    elif args.cmd == "report":
        cmd_report(args)



if __name__ == "__main__":
    main()
