import sys,json,re,os
from pathlib import Path
os.environ['PATH']='C:/Program Files/Tesseract-OCR;'+os.environ['PATH']
sys.path.insert(0,str(Path('.').resolve()))
sys.path.insert(0,str(Path('tmp/gpa-deps').resolve()))
from model import extract as m
original=m.run
logs=[]
def trace(*args,**kwargs):
    out=original(*args,**kwargs)
    logs.append({'args':list(args),'lines':[x for x in out.splitlines() if re.search(r'cumul|gpa|2[.,:]42',x,re.I)]})
    return out
m.run=trace
results=[]
for name in ['pooh_angle_left - Copy - Copy.jpg','pooh_angle_left - Copy.jpg']:
    logs.clear()
    result=m.extract(Path('C:/Users/User/Downloads')/name)
    results.append({'file':name,'result':result,'ocr':list(logs)})
    print(name, result['record']['transcript_detail']['cumulative_gpa'],result['processing_seconds'],flush=True)
    print(json.dumps(logs),flush=True)
Path(sys.argv[1]).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
