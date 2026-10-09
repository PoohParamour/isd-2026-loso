import cv2
import numpy as np
from PIL import Image
from pathlib import Path

root=Path('tmp/photo_ocr_training')
for name in ['1.jpg','2.png']:
  a=np.asarray(Image.open(root/(name+'-upright.png')).convert('L'))
  h,w=a.shape
  roi=a[round(h*.13):round(h*.94)]
  bw=cv2.threshold(roi,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
  vertical=cv2.morphologyEx(bw,cv2.MORPH_OPEN,np.ones((round(h*.11),1),np.uint8))
  counts=(vertical>0).sum(axis=0)
  xs=np.flatnonzero(counts>h*.09)
  groups=[]
  for x in xs:
    if groups and x-groups[-1][-1]<4: groups[-1].append(x)
    else: groups.append([x])
  print(name,w,h,[(round(float(np.median(g))),int(counts[g].max())) for g in groups])
