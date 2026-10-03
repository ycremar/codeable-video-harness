"""Intentional negative fixture: wrong copy, poor contrast and unsafe bounds."""
from vch.core import Canvas


def render(ctx):
    v=ctx['spec']['video'];c=Canvas(v['width'],v['height'],'#FFFFFF')
    c.text('bad',(v['width']-45,12),'BOOK NOW',ctx['root']/ctx['spec']['style']['font'],12,'#FAFAFA')
    return c.finish()
