import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from model.evaluate import evaluate_one
from model.extract import parse

root=Path('tmp/photo_ocr_training')
tess=r'C:\Program Files\Tesseract-OCR\tesseract.exe'
model='model/data/photo_ocr'
def ocr(path,psm):
  return subprocess.run([tess,str(path),'stdout','-l','eng_photo','--psm',str(psm),'--tessdata-dir',model],capture_output=True,encoding='utf-8',errors='replace',check=True).stdout
def columns(im):
  a=np.asarray(im.convert('L'));h,w=a.shape
  bw=cv2.threshold(a[round(h*.13):round(h*.94)],0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
  v=cv2.morphologyEx(bw,cv2.MORPH_OPEN,np.ones((round(h*.11),1),np.uint8))
  count=(v>0).sum(axis=0)
  xs=np.flatnonzero(count>h*.09)
  groups=[]
  for x in xs:
    if groups and x-groups[-1][-1]<4:groups[-1].append(x)
    else:groups.append([x])
  return [round(float(np.median(g))) for g in groups if w*.02 < np.median(g)<w*.6][:4]
for stem,name in [('pooh','1.jpg'),('doc','2.png')]:
  im=Image.open(root/(name+'-upright.png')).convert('RGB');w,h=im.size
  xs=columns(im);print(stem,xs,flush=True)
  base=im.crop((xs[0]+3,round(h*.12),xs[1]-3,round(h*.94)))
  for mode in ('original','autocontrast'):
    crop=base.resize((base.width*3,base.height*3),Image.Resampling.LANCZOS)
    if mode=='autocontrast':crop=ImageOps.autocontrast(crop.convert('L'))
    path=root/f'{stem}-title-{mode}.png';crop.save(path)
    for psm in (4,6):
      body=ocr(path,psm)
      record=parse(body,'bachelor_en')
      truth=json.loads(Path(f'ground_truth_new/{stem}.json').read_text(encoding='utf-8'))
      score=evaluate_one(record,truth)
      n=sum(len(s['subject']) for s in record['transcript_detail']['semesters'])
      print(stem,mode,psm,'rows',score['rows'],'detected',n,'semesters',[(s['year'],s['sem_num']) for s in record['transcript_detail']['semesters']],flush=True)
      (root/f'{stem}-title-{mode}-{psm}.txt').write_text(body,encoding='utf-8')
