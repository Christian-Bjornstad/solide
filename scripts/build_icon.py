"""Render the editable SVG into the app's PNG and multiresolution Windows icon."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage,QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication
from PIL import Image

assets=Path(__file__).resolve().parents[1]/'src'/'solide'/'assets'
app=QApplication.instance() or QApplication([])
canvas=QImage(256,256,QImage.Format.Format_ARGB32)
canvas.fill(Qt.GlobalColor.transparent)
painter=QPainter(canvas)
QSvgRenderer(str(assets/'solide.svg')).render(painter)
painter.end()
if not canvas.save(str(assets/'solide.png')):raise RuntimeError('Could not save app icon')
with Image.open(assets/'solide.png') as image:
    image.save(assets/'solide.ico',sizes=[(n,n) for n in (16,24,32,48,64,128,256)])
print(assets/'solide.ico')
