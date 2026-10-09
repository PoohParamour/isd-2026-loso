import json
from pathlib import Path

from model.evaluate import evaluate_one
from model.extract import extract

root = Path(__file__).resolve().parents[1]
docs = {doc['id']: doc for doc in json.loads((root / 'model/data/manifest.json').read_text(encoding='utf-8'))['documents'] if doc['split'] == 'dev'}
for name in ('71010001_aug1_rotate_bright', '71010001_aug4_perspective', '71010009_aug4_perspective'):
    doc = docs[name[:8]]
    truth = json.loads((root / doc['gt']).read_text(encoding='utf-8'))
    record = extract(root / 'tmp' / f'{name}-table-rectified.png')['record']
    score = evaluate_one(record, truth)
    correct = sum(row['correct'] for row in score['categories'].values())
    total = sum(row['total'] for row in score['categories'].values())
    print(name, f'{correct}/{total}', score['rows'], flush=True)
