"""Per-stage timing of model.extract (measured 2026-10-09, results: model/reports/step-timing-20261009.json).

Each stage is wrapped by an exclusive timer (its time excludes the stages it calls), and the external tools
(pdftotext, pdftoppm, tesseract) are timed separately, so the parts add up to the total.

Run inside the backend image from the repository root (mount the current code, data and an output folder):

    mkdir -p out
    docker run --rm --entrypoint python -v "$PWD/out:/work/out" -v "$PWD/model/profile_steps.py:/work/profile_steps.py:ro" \
        -v "$PWD/data_transcript:/work/data_transcript:ro" -v "$PWD/model:/app/model:ro" \
        <backend-image> /work/profile_steps.py

It reads the test split from model/data/manifest.json (2 documents per format), times PDF text layer, forced OCR,
150 DPI PNG and a synthetic tilted photo, and writes /work/out/step-timing.json plus before/after geometry images.
The "synthetic photo" is a PDF page rotated and perspective-warped for timing only; it is not a real photograph.
"""
import sys, os, json, time, subprocess, statistics, tempfile, platform, collections
from pathlib import Path
sys.path.insert(0, "/app")
os.chdir("/work")
import model.extract as ex
import model.photo_geometry as pg
import model.layout_ocr as lo
import model.screen_table as st
import model.phone_table as pt
import model.photo_unofficial as pu

acc = collections.defaultdict(float)
stack = []

def timed(cat, fn):
    def w(*a, **k):
        t0 = time.perf_counter(); stack.append(0.0)
        try:
            return fn(*a, **k)
        finally:
            el = time.perf_counter() - t0; child = stack.pop()
            acc[cat] += el - child
            if stack: stack[-1] += el
    return w

TOOLS = {"pdftotext": "pdftotext (Poppler)", "pdftoppm": "pdftoppm render (Poppler)", "tesseract": "tesseract OCR"}
_run = subprocess.run
def run(cmd, *a, **k):
    name = os.path.basename(cmd[0]) if isinstance(cmd, (list, tuple)) else str(cmd)
    return timed(TOOLS.get(name, "other subprocess"), _run)(cmd, *a, **k)
subprocess.run = run

GEOM = "image geometry (OpenCV)"; READ = "layout/column reading (python logic)"; PARSE = "parse to JSON (regex)"
POST = "post-process (catalog, repairs)"; VAL = "validation"
for mod, names, cat in [(pg, ["straighten_photo", "straighten_clipped_photo", "deskew_table"], GEOM),
                        (lo, ["read_layout_body"], READ), (st, ["read_screen_table"], READ),
                        (pt, ["read_phone_table"], READ), (pu, ["read_unofficial_photo"], READ)]:
    for n in names: setattr(mod, n, timed(cat, getattr(mod, n)))
for n, cat in [("_orient_photo", GEOM), ("read_image_profile", READ), ("read_bachelor_columns", READ), ("parse", PARSE),
               ("apply_course_catalog", POST), ("recover_semester_headings", POST),
               ("cumulative_gpa_from_sources", POST), ("validate_record", VAL), ("read_document", "read_document (decode/IO only)")]:
    setattr(ex, n, timed(cat, getattr(ex, n)))

def measure(path, **kw):
    acc.clear(); stack.clear()
    t0 = time.perf_counter(); res = ex.extract(Path(path), **kw); total = time.perf_counter() - t0
    d = dict(acc); d["other (load image, detect format, glue)"] = max(0.0, total - sum(d.values()))
    return total, d, res

manifest = json.load(open("/app/model/data/manifest.json"))["documents"]
tests = [x for x in manifest if x["split"] == "test"]
per_group = collections.defaultdict(list)
for x in tests: per_group[(x["group"], x["language"])].append(x)
docs = [v[0] for v in per_group.values()] + [v[1] for v in per_group.values()]  # 2 per group/language
print("docs:", [(d["id"], d["group"], d["language"]) for d in docs], flush=True)

work = Path(tempfile.mkdtemp(prefix="prof_"))
def png_of(d):
    out = work / (d["id"] + ".png")
    if not out.exists(): _run(["pdftoppm", "-r", "150", "-png", "-singlefile", d["pdf"], str(out.with_suffix(""))], check=True)
    return out

def synth_photo(d):
    import cv2, numpy as np
    img = cv2.imread(str(png_of(d))); h, w = img.shape[:2]
    canvas = np.full((int(h * 1.25), int(w * 1.25), 3), 55, np.uint8)
    oy, ox = (canvas.shape[0] - h) // 2, (canvas.shape[1] - w) // 2
    canvas[oy:oy + h, ox:ox + w] = img
    cx, cy = canvas.shape[1] / 2, canvas.shape[0] / 2
    M = cv2.getRotationMatrix2D((cx, cy), 6, 1.0)
    canvas = cv2.warpAffine(canvas, M, (canvas.shape[1], canvas.shape[0]), borderValue=(55, 55, 55))
    s = canvas.shape; src = np.float32([[0, 0], [s[1], 0], [s[1], s[0]], [0, s[0]]])
    dst = np.float32([[s[1] * .03, s[0] * .02], [s[1] * .97, 0], [s[1], s[0] * .98], [0, s[0]]])
    canvas = cv2.warpPerspective(canvas, cv2.getPerspectiveTransform(src, dst), (s[1], s[0]), borderValue=(55, 55, 55))
    canvas = cv2.convertScaleAbs(canvas, alpha=0.85, beta=-10)
    out = work / (d["id"] + "_photo.jpg"); cv2.imwrite(str(out), canvas, [cv2.IMWRITE_JPEG_QUALITY, 90]); return out, canvas

modes = [("pdf_text_layer", lambda d: (d["pdf"], {}), 3),
         ("pdf_force_ocr", lambda d: (d["pdf"], {"force_ocr": True}), 2),
         ("image_png_150dpi", lambda d: (png_of(d), {}), 2),
         ("synthetic_photo", lambda d: (synth_photo(d)[0], {}), 2)]
out = {"platform": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count(), "runs": []}
for mode, make, reps in modes:
    use = docs if mode != "synthetic_photo" else docs[:2]
    for d in use:
        path, kw = make(d)
        for r in range(reps):
            total, parts, res = measure(path, **kw)
            out["runs"].append({"mode": mode, "id": d["id"], "group": d["group"], "language": d["language"], "rep": r,
                                "total": round(total, 4), "parts": {k: round(v, 4) for k, v in parts.items()},
                                "engine": res["engine"], "format": res["record"].get("format_id"),
                                "courses": res["validation"]["course_count"], "reported_seconds": res["processing_seconds"]})
        print(mode, d["id"], "ok", round(total, 2), flush=True)
json.dump(out, open("/work/out/step-timing.json", "w"), ensure_ascii=False, indent=1)
# before/after images for the geometry slide (same functions the pipeline uses)
from PIL import Image
d = docs[0]; path, canvas = synth_photo(d)
src = Image.open(path).convert("RGB")
src.save("/work/out/geometry_before.jpg", quality=90)
page = pg.straighten_photo(src)
print("straighten_photo ->", None if page is None else page.size, flush=True)
if page is not None:
    page.save("/work/out/geometry_after.png")
    fixed = pg.deskew_table(page)
    if fixed: fixed[0].save("/work/out/geometry_after_deskew.png"); print("deskew angle", fixed[1])
