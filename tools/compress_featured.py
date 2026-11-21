import sys, os, glob
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)
for f in sorted(glob.glob(os.path.join(src, 'dj-featured--*.webp'))):
    name = os.path.basename(f)[len('dj-featured--'):-5]
    im = Image.open(f).convert('RGB')
    for suffix, w, q in (('', 1600, 80), ('-640', 640, 76)):
        r = im if im.width <= w else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
        out = os.path.join(dst, f'{name}{suffix}.webp')
        r.save(out, 'WEBP', quality=q, method=6)
        print(f'{os.path.getsize(out)//1024:5d} KB  {r.width}x{r.height}  {name[:50]}{suffix}')
