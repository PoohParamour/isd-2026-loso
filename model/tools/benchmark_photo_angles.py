"""Score photographs of one labeled source document; never a blind test."""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from unittest.mock import patch

from model import extract as extractor
from model.evaluate import evaluate_one


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--gt', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    details = []
    for image in sorted(args.input.iterdir()):
        if image.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
            continue
        sources = []
        original_run = extractor.run

        def capture(*pos, **kw):
            text = original_run(*pos, **kw)
            sources.append({'command': list(pos), 'text': text})
            return text

        with patch.object(extractor, 'run', side_effect=capture):
            result = extractor.extract(image)
        truth = json.loads(args.gt.read_text(encoding='utf-8'))
        score = evaluate_one(result['record'], truth)
        correct = sum(b['correct'] for b in score['categories'].values())
        total = sum(b['total'] for b in score['categories'].values())
        row = {'image': image.name, 'correct': correct, 'total': total,
               'accuracy': correct / total, 'score': score, 'result': result,
               'ocr_sources': sources}
        details.append(row)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({'evaluation': 'views of one document; development regression, not an independent holdout',
                                       'details': details}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(image.name, correct, total, score['rows'], result['validation']['course_count'],
              result['record']['header_detail']['student_id'], result['processing_seconds'], flush=True)
    if not details:
        raise ValueError('No supported photographs found')
    matrix = collections.defaultdict(lambda: {'correct': 0, 'total': 0})
    rows = collections.Counter()
    for detail in details:
        for category, values in detail['score']['categories'].items():
            matrix[category]['correct'] += values['correct']
            matrix[category]['total'] += values['total']
        rows.update(detail['score']['rows'])
    for values in matrix.values():
        values['accuracy'] = values['correct']/values['total'] if values['total'] else None
    correct, total = sum(d['correct'] for d in details), sum(d['total'] for d in details)
    precision = rows['tp']/(rows['tp']+rows['fp']) if rows['tp']+rows['fp'] else 0
    recall = rows['tp']/(rows['tp']+rows['fn']) if rows['tp']+rows['fn'] else 0
    report = {'evaluation': 'views of one document; development regression, not an independent holdout',
              'images': len(details), 'correct': correct, 'total': total, 'accuracy': correct/total,
              'matrix': dict(matrix), 'rows': dict(rows), 'row_precision': precision,
              'row_recall': recall, 'row_f1': 2*precision*recall/(precision+recall) if precision+recall else 0,
              'mean_seconds': sum(d['result']['processing_seconds'] for d in details)/len(details),
              'details': details}
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
