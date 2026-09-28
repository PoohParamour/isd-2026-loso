from pathlib import Path

import numpy as np
from PIL import Image

root=Path('tmp/photo_ocr_training')
for name in ['1.jpg','2.png']:
    img=np.asarray(Image.open(root/(name+'-upright.png')).convert('L'))
    h,w=img.shape
    y0,y1=round(h*.205),round(h*.88)
    x0,x1=round(w*.07),round(w*.40)
    roi=img[y0:y1,x0:x1]
    for darkness in (90,110,130,160):
      counts=(roi<darkness).sum(axis=1)
      for threshold in (2,4,6,10):
        ys=np.flatnonzero(counts>=threshold)+y0
        groups=[]
        for y in ys:
          if groups and y-groups[-1][-1] <= 1:
            groups[-1].append(y)
          else:
            groups.append([y])
        groups=[(g[0],g[-1]) for g in groups if g[-1]-g[0]>=max(1,round(h*.001))]
        longest=max((b-a for a,b in groups),default=0)
        print(name,darkness,threshold,'groups',len(groups),'longest',longest)
