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
    logs.append({'args':list(args),'text':out if 'tsv' not in args else '', 'lines':[x for x in out.splitlines() if re.search(r'Semester|2025|2026|06066300|DATABASE',x,re.I)]})
    return out
m.run=trace
results=[]
for name in ['pooh_angle_left - Copy - Copy.jpg','pooh_angle_left - Copy.jpg']:
    logs.clear()
    result=m.extract(Path('C:/Users/User/Downloads')/name)
    results.append({'file':name,'result':result,'ocr':list(logs)})
    print(name, result['record']['transcript_detail']['cumulative_gpa'],result['processing_seconds'],flush=True)
    print(json.dumps([{'args':x['args'],'lines':x['lines']} for x in logs if 'tsv' not in x['args']]),flush=True)
Path(sys.argv[1]).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')

