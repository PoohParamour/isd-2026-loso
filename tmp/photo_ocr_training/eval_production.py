import json
from pathlib import Path

from model.evaluate import evaluate_one
from model.extract import extract

root = Path('data_transcript/input_new')
out = Path('tmp/photo_ocr_training')
for stem, name in [('pooh', '1.jpg'), ('doc', '2.png')]:
    saved = out / f'{stem}-production.json'
    prediction = json.loads(saved.read_text(encoding='utf-8')) if saved.exists() else extract(root / name)
    (out / f'{stem}-production.json').write_text(
        json.dumps(prediction, ensure_ascii=False, indent=2), encoding='utf-8')
    truth = json.loads((Path('ground_truth_new') / f'{stem}.json').read_text(encoding='utf-8'))
    score = evaluate_one(prediction['record'], truth)
    correct = sum(bucket['correct'] for bucket in score['categories'].values())
    total = sum(bucket['total'] for bucket in score['categories'].values())
    print(stem, correct, total, score['rows'], prediction['processing_seconds'], flush=True)
