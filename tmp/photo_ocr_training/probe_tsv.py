import csv,io,subprocess
from collections import defaultdict
from pathlib import Path

tess=r'C:\Program Files\Tesseract-OCR\tesseract.exe'
for stem in ('pooh','doc'):
  path=Path('tmp/photo_ocr_training')/f'{stem}-title-original.png'
  result=subprocess.run([tess,str(path),'stdout','-l','eng_photo','--tessdata-dir','model/data/photo_ocr','--psm','6','-c','tessedit_create_tsv=1'],capture_output=True,encoding='utf-8',errors='replace',check=True).stdout
  groups=defaultdict(list)
  for row in csv.DictReader(io.StringIO(result),delimiter='\t'):
    if row['level']=='5' and row['text'].strip():
      key=(row['block_num'],row['par_num'],row['line_num'])
      groups[key].append(row)
  lines=[]
  for group in groups.values():
    y=min(int(x['top']) for x in group)
    text=' '.join(x['text'] for x in group)
    lines.append((y,text))
  print(stem,'lines',len(lines))
  for y,text in sorted(lines): print(y,text)
