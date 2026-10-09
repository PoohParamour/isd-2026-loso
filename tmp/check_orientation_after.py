import sys,os,json
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('tmp/gpa-deps').resolve())]
os.environ['PATH']='C:/Program Files/Tesseract-OCR;'+os.environ['PATH']
from PIL import Image
from model.extract import extract
out=[]
source=Path('C:/Users/User/Downloads/Screenshot 2026-10-04 022941.png')
for degrees in (0,90,180,270):
 path=Path('tmp')/f'orientation-new-{degrees}.png'
 with Image.open(source) as im: im.rotate(degrees,expand=True).save(path)
 result=extract(path)
 out.append({'case':f'new-image-rotation-{degrees}','result':result})
 print(out[-1]['case'],result['validation']['course_count'],result['record']['transcript_detail']['cumulative_gpa'],result['processing_seconds'],flush=True)
for name in ['pooh_angle_left - Copy - Copy.jpg','pooh_angle_left - Copy.jpg']:
 result=extract(Path('C:/Users/User/Downloads')/name)
 out.append({'case':name,'result':result})
 print(name,result['validation']['course_count'],result['record']['transcript_detail']['cumulative_gpa'],result['processing_seconds'],flush=True)
Path('tmp/orientation-after.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
