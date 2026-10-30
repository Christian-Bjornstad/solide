"""Resize the approved source artwork into PNG and multiresolution Windows ICO."""
from pathlib import Path
from PIL import Image

assets=Path(__file__).resolve().parents[1]/'src'/'solide'/'assets'
with Image.open(assets/'solide-source.png') as source:
    image=source.convert('RGBA').resize((256,256),Image.Resampling.LANCZOS)
    image.save(assets/'solide.png')
    image.save(assets/'solide.ico',sizes=[(n,n) for n in (16,24,32,48,64,128,256)])
print(assets/'solide.ico')
