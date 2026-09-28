import cv2,numpy as np
from PIL import Image
from pathlib import Path
root=Path('tmp/photo_ocr_training')
for name in ['1.jpg','2.png']:
 a=np.asarray(Image.open(root/(name+'-upright.png')).convert('L'))
 h,w=a.shape
 bw=cv2.threshold(a,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
 closed=cv2.morphologyEx(bw,cv2.MORPH_CLOSE,np.ones((1,9),np.uint8))
 horizontal=cv2.morphologyEx(closed,cv2.MORPH_OPEN,np.ones((1,round(w*.12)),np.uint8))
 counts=(horizontal>0).sum(axis=1)
 ys=np.flatnonzero((counts>w*.4)&(np.arange(h)>h*.08)&(np.arange(h)<h*.5))
 groups=[]
 for y in ys:
  if groups and y-groups[-1][-1]<4:groups[-1].append(y)
  else:groups.append([y])
 print(name,w,h,[(round(float(np.median(g))),int(counts[g].max())) for g in groups[:10]])
