"""Explicit readable colours for native Windows themes and popup windows."""
from PyQt6.QtGui import QColor,QPalette


def light_palette():
    palette=QPalette()
    colours={
        QPalette.ColorRole.Window:'#F5F7F4',QPalette.ColorRole.WindowText:'#243128',
        QPalette.ColorRole.Base:'#FFFFFF',QPalette.ColorRole.AlternateBase:'#FAFBF9',
        QPalette.ColorRole.Text:'#243128',QPalette.ColorRole.Button:'#FFFFFF',
        QPalette.ColorRole.ButtonText:'#243128',QPalette.ColorRole.Highlight:'#425B3D',
        QPalette.ColorRole.HighlightedText:'#FFFFFF',QPalette.ColorRole.PlaceholderText:'#596454',
        QPalette.ColorRole.ToolTipBase:'#243128',QPalette.ColorRole.ToolTipText:'#FFFFFF',
        QPalette.ColorRole.Link:'#36582C',QPalette.ColorRole.LinkVisited:'#36582C',
    }
    for role,value in colours.items():palette.setColor(role,QColor(value))
    for role in (QPalette.ColorRole.Text,QPalette.ColorRole.WindowText,QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled,role,QColor('#596454'))
    return palette


def text_pixels(value):
    try:value=int(value)
    except (TypeError,ValueError):return 16
    return value if value in (14,16,18,20) else 16
