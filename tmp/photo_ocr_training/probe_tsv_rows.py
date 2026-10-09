import csv, io, json, re, subprocess
from pathlib import Path

from PIL import Image
from model.evaluate import evaluate_one
from model.extract import parse

root=Path('tmp/photo_ocr_training')
tess=r'C:\Program Files\Tesseract-OCR\tesseract.exe'
def ocr(path,psm,model='eng_photo',directory='model/data/photo_ocr',tsv=False):
  args=[tess,str(path),'stdout','-l',model,'--psm',str(psm),'--tessdata-dir',directory]
  if tsv: args += ['-c','tessedit_create_tsv=1']
  return subprocess.run(args,capture_output=True,encoding='utf-8',errors='replace',check=True).stdout
for stem in ('pooh','doc'):
  path=root/f'{stem}-title-original.png'
  image=Image.open(path)
  tsv=ocr(path,6,tsv=True)
  rows=list(csv.DictReader(io.StringIO(tsv),delimiter='\t'))
  lines=[]
  for row in rows:
    if row['level']!='4':continue
    left,top,width,height=[int(row[k]) for k in ('left','top','width','height')]
    if height<4 or height>80:continue
    lines.append((top,height))
  lines.sort()
  body=[]
  for i,(top,height) in enumerate(lines):
    pad=round(height*.25)
    lo=max(0,top-pad)
    hi=min(image.height,top+height+pad)
    if i:lo=max(lo,round((lines[i-1][0]+lines[i-1][1]/2+top+height/2)/2))
    if i+1<len(lines):hi=min(hi,round((top+height/2+lines[i+1][0]+lines[i+1][1]/2)/2))
    crop=root/f'{stem}-tsvrow-{i:02d}.png'
    image.crop((0,lo,image.width,hi)).save(crop)
    photo=ocr(crop,7).strip()
    if re.search('Sem|Seon|Year|Ysac',photo,re.I):
      best=ocr(crop,7,'eng_best','tmp/photo_ocr_training').strip()
      print(stem,'term?',top,repr(photo),repr(best),flush=True)
    body.append(photo)
  text='\n'.join(body)
  (root/f'{stem}-tsvrows.txt').write_text(text,encoding='utf-8')
  record=parse(text,'bachelor_en')
  truth=json.loads(Path(f'ground_truth_new/{stem}.json').read_text(encoding='utf-8'))
  score=evaluate_one(record,truth)
  print(stem,'lines',len(lines),'score',score['rows'],'semesters',[(s['year'],s['sem_num'],len(s['subject'])) for s in record['transcript_detail']['semesters']],flush=True)
