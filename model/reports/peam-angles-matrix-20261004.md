# Four-angle screen-photo development evaluation

All four photographs show one transcript. These images were used while developing this fix; the numbers are not an independent holdout accuracy estimate.

Ground truth: `ground_truth_new/peam.json`; labels are loaded only after inference. Source images and ground truth were not modified.

| Image prefix | Before exact fields | After exact fields | Extracted rows | Correct code + semester rows |
|---|---:|---:|---:|---:|
| 19b631b5 | 0/150 (0.00%) | 105/150 (70.00%) | 32/32 | 25/32 |
| 26e37977 | 0/150 (0.00%) | 82/150 (54.67%) | 31/32 | 16/32 |
| 6cca1647 | 2/150 (1.33%) | 120/150 (80.00%) | 32/32 | 29/32 |
| f77ae849 | 0/150 (0.00%) | 116/150 (77.33%) | 32/32 | 22/32 |

| Category | Before | After |
|---|---:|---:|
| header | 0/24 (0.00%) | 20/24 (83.33%) |
| footer | 0/4 (0.00%) | 0/4 (0.00%) |
| summary | 0/8 (0.00%) | 0/8 (0.00%) |
| semester | 2/76 (2.63%) | 53/76 (69.74%) |
| course | 0/488 (0.00%) | 350/488 (71.72%) |

Overall exact fields: **0.33% → 70.50%**.
Course row precision/recall/F1 after correction: 80.70% / 71.88% / 76.03%.
Mean extraction time: 29.49s → 30.90s (concurrent development tests can affect timings).

Root causes: fixed brightness threshold loses shadowed page edges; near-axis-aligned pages were rejected; clipping created artificial corners; enlargement amplified screen moiré; table rules and narrow numeric cells confused whole-page segmentation; damaged English headings and IDs caused wrong semester assignment and course-code-as-student-ID fallback.

Fix: recover real page-edge intersections, retain rotated-page fallback, smooth screen pixels and normalize illumination before enlargement, find table borders, read credit/grade cells at each visible row, re-read semester headings and student number, retain unreadable cells as null and mark screen photographs for review.

Remaining limits: incorrect course codes/names/grades and missing or incorrect summary fields remain. A detected row is not necessarily a correct row. Do not use these outputs without review. No new weights were trained on peam labels.

Reproduce inside the backend environment:
```
python -m model.benchmark_photo_angles --input <photo-directory> --gt <peam.json> --out <report.json>
```

Validation: 83 unit tests passed. The existing 12 original-format images retained all 201 correct course rows and increased exact fields from 1,281/1,338 to 1,284/1,338 (95.96%); no individual image lost points. The old rotated `1.jpg` photo retained the current baseline of 58/145 fields and 27/30 correct course rows. Its older September report used an earlier code state and is not the baseline for this change.

Web verification: the first photograph was uploaded to `http://localhost:3000/api/proxy/transcripts/extract`. The API returned 32 rows, the correct student number, and a review warning in 27.032 seconds. Its complete record matched the benchmark record exactly. Backend was restarted; proxy health returned `ok`. Evidence: `peam-angle-api-20261004.json`.
