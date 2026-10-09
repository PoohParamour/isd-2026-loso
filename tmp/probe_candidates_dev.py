"""Compare OCR parse candidates on dev-only transformed pages."""

import json
from pathlib import Path

from model.course_catalog import apply_course_catalog
from model.evaluate import evaluate_one
from model.extract import detect_format, parse, read_document, read_image_profile
from model.validate import validate_record

root = Path(__file__).resolve().parents[1]
docs = {doc['id']: doc for doc in json.loads((root / 'model/data/manifest.json').read_text(encoding='utf-8'))['documents'] if doc['split'] == 'dev'}
for name in ('71010001_aug4_perspective', '71010009_aug4_perspective', '71010009_aug3_blur_contrast'):
    path = next((root / 'all/Lab5_transcript_dataset/images/augmented').rglob(name + '.png'))
    text, _ = read_document(path)
    fmt = detect_format(text)
    text, body = read_image_profile(path, fmt)
    fmt = detect_format(text)
    truth = json.loads((root / docs[name[:8]]['gt']).read_text(encoding='utf-8'))
    print(name, fmt, flush=True)
    for label, candidate_body in (('body', body), ('full', None)):
        record = apply_course_catalog(parse(text, fmt, candidate_body))
        semesters = record['transcript_detail']['semesters']
        score = evaluate_one(record, truth)
        checks = validate_record(record)
        print(label, 'rows', sum(len(s['subject']) for s in semesters),
              'terms', sum(s.get('year') is not None for s in semesters),
              'correct', sum(v['correct'] for v in score['categories'].values()),
              'row', score['rows'], 'validation', checks, flush=True)
