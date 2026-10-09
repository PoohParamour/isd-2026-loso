import json
import subprocess
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from model.evaluate import evaluate_one
from model.extract import parse

root = Path('tmp/photo_ocr_training')
tess = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
model_dir = Path('model/data/photo_ocr')

def ocr(path, psm, language='eng_photo', directory=model_dir):
    args = [tess, str(path), 'stdout', '-l', language, '--psm', str(psm),
            '--tessdata-dir', str(directory)]
    return subprocess.run(args, check=True, capture_output=True,
                          encoding='utf-8', errors='replace').stdout

for stem, name in [('pooh','1.jpg'),('doc','2.png')]:
    source = Image.open(root / (name + '-upright.png')).convert('RGB')
    width, height = source.size
    header = source.crop((0, 0, width, round(height * .22))).resize((width*2, round(height*.22)*2))
    footer = source.crop((0, round(height*.79), width, height)).resize((width*2, (height-round(height*.79))*2))
    header.save(root / (stem+'-header.png'))
    footer.save(root / (stem+'-footer.png'))
    full = ocr(root / (stem+'-header.png'),6) + '\n' + ocr(root/(stem+'-footer.png'),6)
    truth=json.loads(Path(f'ground_truth_new/{stem}.json').read_text(encoding='utf-8'))
    for right in (.52,.55,.58):
      for mode in ('original','autocontrast','sharpen'):
        crop=source.crop((0,round(height*.21),round(width*right),round(height*.87)))
        crop=crop.resize((crop.width*2,crop.height*2),Image.Resampling.LANCZOS)
        if mode=='autocontrast': crop=ImageOps.autocontrast(ImageOps.grayscale(crop))
        if mode=='sharpen': crop=ImageEnhance.Contrast(ImageOps.grayscale(crop)).enhance(1.5).filter(ImageFilter.UnsharpMask(radius=2,percent=180,threshold=3))
        path=root / f'{stem}-{right}-{mode}.png'; crop.save(path)
        for psm in (4,6):
          body=ocr(path,psm)
          record=parse(full+'\n'+body,'bachelor_en',body)
          score=evaluate_one(record,truth)
          rows=score['rows']
          correct=sum(x['correct'] for x in score['categories'].values())
          total=sum(x['total'] for x in score['categories'].values())
          print(stem,right,mode,psm,'correct',correct,'/',total,'rows',rows,flush=True)
          (root / f'{stem}-{right}-{mode}-{psm}.txt').write_text(body,encoding='utf-8')
