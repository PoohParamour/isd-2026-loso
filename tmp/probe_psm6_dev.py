"""Dev-only PSM alternative probe; never imported by inference."""

import json
from pathlib import Path

import model.extract as extractor
from model.evaluate import evaluate_one

root = Path(__file__).resolve().parents[1]
documents = {doc['id']: doc for doc in json.loads((root / 'model/data/manifest.json').read_text(encoding='utf-8'))['documents'] if doc['split'] == 'dev'}
baseline = json.loads((root / 'tmp/augmented-dev-current.json').read_text(encoding='utf-8'))
baseline_scores = {(row['id'], row['augmentation']): row['correct'] for row in baseline['details']}
original_run = extractor.run


def psm6_run(*args, cwd=None):
    args = list(args)
    if '--psm' in args and args[args.index('--psm') + 1] == '4':
        args[args.index('--psm') + 1] = '6'
    return original_run(*args, cwd=cwd)


extractor.run = psm6_run
cases = (
    ('71010001', 'aug1_rotate_bright'),
    ('71010001', 'aug4_perspective'),
    ('71010009', 'aug3_blur_contrast'),
    ('71010009', 'aug4_perspective'),
    ('73036011', 'aug5_jpeg_dark'),
)
for doc_id, augmentation in cases:
    image = next((root / 'all/Lab5_transcript_dataset/images/augmented').rglob(f'{doc_id}_{augmentation}.png'))
    truth = json.loads((root / documents[doc_id]['gt']).read_text(encoding='utf-8'))
    result = extractor.extract(image)
    score = evaluate_one(result['record'], truth)
    correct = sum(values['correct'] for values in score['categories'].values())
    print(doc_id, augmentation, 'baseline', baseline_scores[(doc_id, augmentation)],
          'psm6', correct, 'rows', score['rows'], flush=True)
