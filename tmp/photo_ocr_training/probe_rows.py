import csv, io, json, statistics, subprocess
from pathlib import Path

from PIL import Image
from model.evaluate import evaluate_one
from model.extract import parse

root=Path('tmp/photo_ocr_training')
tess=r'C:\Program Files\Tesseract-OCR\tesseract.exe'
def call(path, psm, tsv=False):
  args=[tess,str(path),'stdout','-l','eng_photo','--psm',str(psm),'--tessdata-dir','model/data/photo_ocr']
  if tsv: args += ['-c','tessedit_create_tsv=1']
  return subprocess.run(args,capture_output=True,encoding='utf-8',errors='replace',check=True).stdout
for stem in ('pooh','doc'):
  source=root/f'{stem}-title-original.png'
  image=Image.open(source)
  rows=list(csv.DictReader(io.StringIO(call(source,11,True)),delimiter='\t'))
  boxes=[]
  for row in rows:
    if row['level']!='5' or not row['text'].strip():continue
    box={k:int(row[k]) for k in ('left','top','width','height')}
    if box['height']<2 or box['height']>70:continue
    box['center']=box['top']+box['height']/2
    boxes.append(box)
  median_height=statistics.median(box['height'] for box in boxes)
  threshold=median_height*.72
  groups=[]
  for box in sorted(boxes,key=lambda item:item['center']):
    if groups and abs(box['center']-statistics.median(x['center'] for x in groups[-1]))<=threshold:
      groups[-1].append(box)
    else:groups.append([box])
  print(stem,'boxes',len(boxes),'median height',median_height,'groups',len(groups),flush=True)
  lines=[]
  centers=[statistics.median(box['center'] for box in group) for group in groups]
  for i,group in enumerate(groups):
    lo=min(box['top'] for box in group)-round(median_height*.3)
    hi=max(box['top']+box['height'] for box in group)+round(median_height*.3)
    if i:lo=max(lo,round((centers[i-1]+centers[i])/2))
    if i+1<len(groups):hi=min(hi,round((centers[i]+centers[i+1])/2))
    lo=max(0,lo);hi=min(image.height,hi)
    if hi-lo<median_height*.5:continue
    path=root/f'{stem}-row-{i:02d}.png'
    image.crop((0,lo,image.width,hi)).save(path)
    line=call(path,7).strip()
    lines.append(line)
  body='\n'.join(lines)
  (root/f'{stem}-rows.txt').write_text(body,encoding='utf-8')
  result=parse(body,'bachelor_en')
  truth=json.loads(Path(f'ground_truth_new/{stem}.json').read_text(encoding='utf-8'))
  score=evaluate_one(result,truth)
  print(stem,'rows score',score['rows'],'semesters',[(s['year'],s['sem_num'],len(s['subject'])) for s in result['transcript_detail']['semesters']],flush=True)
