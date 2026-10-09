from pathlib import Path
import pymupdf
from PIL import Image, ImageDraw

out = Path('tmp/context-read')
specs = [
    ('all/ch5_Deep generative modeling.pdf', 'ch5', 0, 30),
    ('all/ch6_Deep Reinforcement Learning.pdf', 'ch6a', 0, 22),
    ('all/ch6_Deep Reinforcement Learning.pdf', 'ch6b', 22, 44),
]
for filename, name, start, end in specs:
    doc = pymupdf.open(filename)
    sheet = Image.new('RGB', (2000, ((end-start+3)//4)*310), 'white')
    draw = ImageDraw.Draw(sheet)
    for n in range(start, end):
        pix = doc[n].get_pixmap(matrix=pymupdf.Matrix(0.8, 0.8))
        im = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        im.thumbnail((495, 285))
        x, y = ((n-start)%4)*500, ((n-start)//4)*310
        sheet.paste(im, (x, y+20))
        draw.text((x+5, y+2), 'Page '+str(n+1), fill='black')
    sheet.save(out/(name+'.png'))
