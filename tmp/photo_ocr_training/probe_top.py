import json,subprocess
from pathlib import Path
from PIL import Image,ImageOps
from model.extract import parse
from model.evaluate import evaluate_one

root=Path('tmp/photo_ocr_training')
tess=r'C:\Program Files\Tesseract-OCR\tesseract.exe'
def ocr(path,psm):
  return subprocess.run([tess,str(path),'stdout','-l','eng_photo','--psm',str(psm),'--tessdata-dir','model/data/photo_ocr'],capture_output=True,encoding='utf-8',errors='replace',check=True).stdout
for stem,name in [('pooh','1.jpg'),('doc','2.png')]:
  image=Image.open(root/(name+'-upright.png')).convert('RGB');w,h=image.size
  full=ocr(root/(stem+'-header.png'),6)+'\n'+ocr(root/(stem+'-footer.png'),6)
  truth=json.loads(Path(f'ground_truth_new/{stem}.json').read_text(encoding='utf-8'))
  for top in (.12,.16,.20):
    crop=image.crop((0,round(h*top),round(w*.58),round(h*.92)))
    crop=ImageOps.autocontrast(crop.resize((crop.width*2,crop.height*2),Image.Resampling.LANCZOS).convert('L'))
    path=root/f'{stem}-top{top}.png';crop.save(path)
    body=ocr(path,4)
    p=parse(full+'\n'+body,'bachelor_en',body)
    s=evaluate_one(p,truth)
    c=sum(v['correct'] for v in s['categories'].values());n=sum(v['total'] for v in s['categories'].values())
    print(stem,top,c,n,s['rows'],[(x['year'],x['sem_num']) for x in p['transcript_detail']['semesters']],flush=True)
