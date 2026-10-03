"""Original demonstration: clean editorial motion, no reference-video art copied."""
import math
from vch.core import Canvas, ease, noise


def render(ctx):
    spec,scene=ctx['spec'],ctx['scene']; v=spec['video'];w,h=v['width'],v['height']
    p=ctx['progress'];params=scene.get('params',{})
    portrait=h>w
    palette=spec['style'];c=Canvas(w,h,palette['background'])
    font=ctx['root']/spec['style']['font'];ink=palette['ink'];accent=palette['accent']
    margin=36 if portrait else 44
    c.text('brand',(margin,28),spec['title'],font,18,ink)
    c.draw.line((margin,64,w-margin,64),fill=accent,width=2)
    y=105 if portrait else 90
    for i,line in enumerate(params['headline']):
        c.text(f"{scene['id']}.headline.{i}",(margin,y+i*(39 if portrait else 44)),line,font,28 if portrait else 36,ink)
    # Short labels remain stationary; motion belongs to the illustration.
    mode=params.get('visual','orbit');cy=h*.58 if portrait else h*.69
    if mode=='orbit':
        cx=w*.52
        r=58 if portrait else 40
        c.draw.ellipse((cx-r,cy-r,cx+r,cy+r),outline=palette['muted'],width=2)
        for i in range(5):
            a=i*math.tau/5+p*math.tau*.55
            x=cx+math.cos(a)*r; yy=cy+math.sin(a)*r
            radius=5+3*noise(ctx['seed'],i)
            c.draw.ellipse((x-radius,yy-radius,x+radius,yy+radius),fill=accent)
    elif mode=='bars':
        for i in range(5):
            x=margin+i*(w-2*margin)/5
            height=(25+48*noise(ctx['seed'],i))*ease(min(1,p*2))
            c.draw.rounded_rectangle((x,cy-height,x+28,cy+25),radius=5,fill=accent)
    elif mode=='flow':
        for i in range(3):
            x=margin+20+i*(w-2*margin-40)/2
            c.draw.ellipse((x-12,cy-12,x+12,cy+12),fill=accent if p*3>=i else palette['muted'])
            if i<2:c.draw.line((x+14,cy,x+(w-2*margin-40)/2-14,cy),fill=ink,width=2)
    c.text('status',(margin,h-86),spec['footer'],font,18,ink)
    c.draw.line((margin,h-45,w-margin,h-45),fill=palette['muted'],width=2)
    c.draw.line((margin,h-45,margin+(w-2*margin)*ctx['t']/v['duration'],h-45),fill=accent,width=3)
    return c.finish()
