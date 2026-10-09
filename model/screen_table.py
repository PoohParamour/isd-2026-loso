"""Read ruled screen photographs by aligning OCR cells with visible rows.

Only image geometry and recognized text are used; no document labels or
course catalog is needed to find the cells.
"""
from __future__ import annotations

import csv
import io
import re
import statistics
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


def read_screen_table(path: Path) -> tuple[str, str] | None:
    try:
        from model.extract import run, parse_term
        from model.photo_unofficial import _table_top
    except ModuleNotFoundError:
        from extract import run, parse_term
        from photo_unofficial import _table_top

    with Image.open(path) as opened:
        source = ImageOps.exif_transpose(opened).convert('L')
    width, height = source.size
    if width < 900 or height <= width:
        return None
    # Smooth screen subpixels before any enlargement. Keep glyph edges while
    # suppressing the fine vertical pattern that Tesseract otherwise segments.
    gray = cv2.GaussianBlur(np.asarray(source), (0, 0), .7)
    top = _table_top(Image.fromarray(gray))
    if top is None:
        return None
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((height // 3, 1), np.uint8))
    counts = (vertical > 0).sum(axis=0)
    xs = np.flatnonzero(counts > height * .3)
    groups = np.split(xs, np.flatnonzero(np.diff(xs) > max(4, width * .012)) + 1)
    borders = [int(group[np.argmax(counts[group])]) for group in groups if len(group)]
    options = []
    for a, b, c in zip(borders, borders[1:], borders[2:]):
        if (.3 * width < a < .6 * width and .025 * width < b-a < .065 * width
                and .025 * width < c-b < .065 * width and .65 < (b-a)/(c-b) < 1.5):
            options.append((int(counts[a]+counts[b]+counts[c]), a, b, c))
    if not options:
        return None
    _, title_end, credit_end, grade_end = max(options)
    normalized = cv2.divide(gray, cv2.GaussianBlur(gray, (0, 0), 8), scale=255)
    # Keep continuous grayscale after illumination correction. Binarizing
    # here discards thin digit strokes; enlarging the raw photograph instead
    # amplifies the screen pattern.
    ink = normalized
    # The left end of the long top rule locates the title cell independently
    # of screen reflections that also happen to form vertical streaks.
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((1, round(width*.12)), np.uint8))
    rule = np.flatnonzero(horizontal[max(0, top-2):top+5].max(axis=0) > 0)
    left = int(rule[0]) if len(rule) else max(0, title_end-round(width*.4))
    if title_end-left < width*.25:
        return None
    bottom = height
    with tempfile.TemporaryDirectory(prefix='isd_screen_cells_') as temp:
        work = Path(temp)

        def ocr(box, name, psm=6, extra=(), tsv=False, raw=False):
            l, t, r, b = map(int, box)
            l, t, r, b = max(0,l), max(0,t), min(width,r), min(height,b)
            if r <= l or b <= t:
                return ''
            pixels = normalized if raw else cv2.threshold(normalized, 225, 255, cv2.THRESH_BINARY)[1] if name == 'header' else ink
            region = Image.fromarray(pixels[max(0,t):min(height,b),max(0,l):min(width,r)])
            region = region.resize((region.width*2, region.height*2), Image.Resampling.LANCZOS)
            if re.search(r'heading|titles', name):
                arr = np.array(region)
                dark = cv2.threshold(arr, 128, 255, cv2.THRESH_BINARY_INV)[1]
                rules = cv2.morphologyEx(dark, cv2.MORPH_OPEN,
                                       np.ones((1,max(30,round(region.width*.2))),np.uint8))
                arr[rules > 0] = 255
                region = Image.fromarray(arr)
            region = ImageOps.expand(region, 12, 'white')
            region.save(work / (name+'.png'))
            model_dir = Path(__file__).resolve().parent / 'data/photo_ocr'
            model_args = ('-l','eng_photo','--tessdata-dir',str(model_dir)) if (model_dir/'eng_photo.traineddata').exists() and name != 'header' and not raw else ('-l','eng')
            return run('tesseract', name+'.png', 'stdout', *model_args, '--psm', str(psm),
                       *extra, *(('-c','tessedit_create_tsv=1') if tsv else ()), cwd=work)

        header = ocr((0,0,width,top-3),'header')
        header = '\n'.join(re.sub(r'^[^A-Za-z0-9(]+', '', line) for line in header.splitlines())
        header = re.sub(r'\bStud\w*\s+[I1f]D\b', 'Student ID', header, flags=re.I)
        if not re.search(r'Unofficial\s+Transcript', header, re.I):
            return None
        left_header = ocr((0,round(top*.4),grade_end,top-3),'header-left',6,raw=True)
        right_header = ocr((grade_end,round(top*.4),width,top-3),'header-right',6,raw=True)
        marker = next(line for line in header.splitlines() if re.search(r'Unofficial\s+Transcript',line,re.I))
        split_header = marker+'\n'+left_header+'\n'+right_header
        def clean_header(value):
            value = '\n'.join(re.sub(r'^[^A-Za-z0-9(]+', '', line) for line in value.splitlines())
            return re.sub(r'\b(?:Stud\w*|Sud\w*)\s+[I1f]D\b','Student ID',value,flags=re.I)
        split_header = clean_header(split_header)
        cues = lambda value: sum(bool(re.search(r'(?mi)^'+label,value)) for label in ('Name','Date of Birth','Degree','Program'))
        if cues(split_header) >= cues(header):
            header = split_header
        identity_tsv = ocr((grade_end,round(top*.4),width,top-3),'identity',6,tsv=True,raw=True)
        for word in csv.DictReader(io.StringIO(identity_tsv),delimiter='\t',quoting=csv.QUOTE_NONE):
            token = re.sub(r'[^A-Za-z0-9]','',word.get('text') or '')
            if word.get('level') != '5' or not (7 <= len(token) <= 10 and sum(c.isdigit() for c in token) >= 6):
                continue
            x = grade_end+(int(word['left'])-12)/2
            y = round(top*.4)+(int(word['top'])-12)/2
            number = ocr((x-4,y-4,x+int(word['width'])/2+4,y+int(word['height'])/2+4),
                         'student-number',7,('-c','tessedit_char_whitelist=0123456789'),raw=True).strip()
            if re.fullmatch(r'\d{8}',number):
                header = 'Student ID '+number+'\n'+header
                break
        title_left = left + 4
        table_start = top + round(height * .02)
        tsv = ocr((title_left,table_start,title_end-4,bottom),'titles',tsv=True)
        lines = {}
        for word in csv.DictReader(io.StringIO(tsv), delimiter='\t', quoting=csv.QUOTE_NONE):
            if word.get('level') != '5' or not (word.get('text') or '').strip():
                continue
            key = tuple(word.get(k) for k in ('block_num','par_num','line_num'))
            lines.setdefault(key,[]).append(word)
        body = []
        for index, words in enumerate(lines.values()):
            words.sort(key=lambda w: int(w['left']))
            text = ' '.join(w['text'] for w in words)
            if re.search(r'Total|Cumulative|Transcript Closed|Checked|Date Issued', text, re.I):
                break
            code_words = [w for w in words if int(w['left']) < (title_end-title_left)*.145*2]
            useful = [w for w in words if re.search(r'[A-Za-z0-9]',w['text'])]
            if not useful:
                continue
            y = table_start + (statistics.median(int(w['top']) for w in useful)-12)/2
            glyph_height = statistics.median(int(w['height']) for w in useful)/2
            row_top, row_bottom = y-4, y+glyph_height+4
            if re.search(r'Seme|GPS|GPA', text, re.I):
                reread = ocr((title_left,row_top,title_end-4,row_bottom),f'heading-{index}',7,raw=True)
                # Choose an independently read term, never infer dates from
                # neighboring semesters or from the known source document.
                if parse_term(reread, 'en') or re.search(r'GPS\s*:',reread,re.I):
                    text = reread.strip()
                body.append(text)
                continue
            token = re.sub(r'[^A-Za-z0-9]', '', ''.join(w['text'] for w in code_words))
            if not (code_words and 6 <= len(token) <= 10 and sum(ch.isdigit() for ch in token) >= 3):
                body.append(text)
                continue
            code_right = title_left+(title_end-title_left)*.145
            code = token if re.fullmatch(r'\d{8}',token) else ocr(
                (title_left,row_top,code_right,row_bottom),f'code-{index}',7,
                ('-c','tessedit_char_whitelist=0123456789')).strip()
            credit = ocr((title_end+4,row_top,credit_end-4,row_bottom),f'credit-{index}',7,
                         ('-c','tessedit_char_whitelist=0123456789.')).strip()
            if re.fullmatch(r'\d+\.',credit):
                credit = credit[:-1]
            grade = ocr((credit_end+4,row_top,grade_end-4,row_bottom),f'grade-{index}',7,
                        ('-c','tessedit_char_whitelist=ABCDFSPUW+-')).strip()
            name = ' '.join(w['text'] for w in words if w not in code_words).strip(' |.,=')
            # Missing grades are valid in an in-progress semester; never fill
            # them from a neighboring row or from GPA.
            code = code if re.fullmatch(r'\d{7,9}',code) else '?'
            credit = credit if re.fullmatch(r'\d{1,2}',credit) else '?'
            grade = grade if re.fullmatch(r'[A-F][+]?|S|I|W|P|NP|U|G|-',grade) else '?'
            body.append(f'{code} {name} {credit} {grade}')
        footer = ocr((left,round(height*.8),grade_end,height),'footer')
        footer = '\n'.join(line for line in footer.splitlines()
                           if re.search(r'Total|Cumulative|Date Issued', line, re.I))
    body_text = '\n'.join(body)
    return '\n'.join((header,footer,body_text)), body_text
