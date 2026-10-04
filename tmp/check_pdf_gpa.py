import sys,os,json
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('tmp/gpa-deps').resolve())]
os.environ['PATH']='C:/Program Files/Tesseract-OCR;C:/Users/User/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin;'+os.environ['PATH']
from model import extract as m
logs=[]; original=m.run
def trace(*args,**kwargs):
 out=original(*args,**kwargs);logs.append({'args':args,'text':out});return out
m.run=trace
out=[]
for file in [Path('C:/Users/User/Downloads/72120014.pdf'),Path('tmp/pdfs/gpa-source.png')]:
 logs.clear();r=m.extract(file,force_ocr=True)
 out.append({'file':str(file),'result':r,'ocr':list(logs)})
 print(str(file),r['record']['transcript_detail']['cumulative_gpa'],flush=True)
 for x in logs:
  if 'tsv' not in x['args']: print(x['args'][1], '\n'.join(t for t in x['text'].splitlines() if 'Cumulative' in t),flush=True)
Path(sys.argv[1]).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
