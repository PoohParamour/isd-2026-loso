import sys,os,json
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('tmp/gpa-deps').resolve())]
os.environ['PATH']='C:/Program Files/Tesseract-OCR;'+os.environ['PATH']
from model.extract import extract
r=extract(Path('C:/Users/User/Downloads/Screenshot 2026-10-04 022941.png'))
Path('tmp/orientation-before.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print({'seconds':r['processing_seconds'],'courses':r['validation']['course_count'],'gpa':r['record']['transcript_detail']['cumulative_gpa']})
