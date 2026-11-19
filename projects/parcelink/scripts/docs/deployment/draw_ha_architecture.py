from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import html
import math

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import generator_context

ROOT = Path(__file__).resolve().parents[3]
CONTEXT = generator_context(ROOT, 'Draw the two-host high availability architecture.')
OUT = CONTEXT.output_root / 'assets/deployment'
W, H = 2000, 1580
FONT = str(CONTEXT.font_path)
INK, MUTED, BLUE, TEAL = '#143247', '#50697A', '#28648C', '#227D78'
im = Image.new('RGB', (W, H), '#FFFFFF')
d = ImageDraw.Draw(im)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', '<rect width="2000" height="1580" fill="white"/>']
fonts = {}

def font(size):
    if size not in fonts:
        fonts[size] = ImageFont.truetype(FONT, size)
    return fonts[size]

def text(x, y, value, size=39, fill=INK, bold=False, anchor='mm'):
    d.text((x, y), value, font=font(size), fill=fill, anchor=anchor, stroke_width=.25 if bold else 0)
    align = 'middle' if anchor[0] == 'm' else 'start'
    svg.append(f'<text x="{x}" y="{y}" font-family="{html.escape(CONTEXT.font_family, quote=True)}, sans-serif" font-size="{size}" text-anchor="{align}" dominant-baseline="central" fill="{fill}" font-weight="{600 if bold else 400}">{html.escape(value)}</text>')

def rect(box, fill='#F4F8FB', outline='#8DAABA', radius=22, width=3):
    x1, y1, x2, y2 = box
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    svg.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="{radius}" fill="{fill}" stroke="{outline}" stroke-width="{width}"/>')

def line(points, color=BLUE, width=6, dashed=False, head=False):
    if dashed:
        for (x1,y1),(x2,y2) in zip(points,points[1:]):
            length = math.hypot(x2-x1,y2-y1)
            for a in range(0,int(length),30):
                b=min(a+17,length)
                d.line([(x1+(x2-x1)*a/length,y1+(y2-y1)*a/length),(x1+(x2-x1)*b/length,y1+(y2-y1)*b/length)],fill=color,width=width)
    else:
        d.line(points,fill=color,width=width,joint='curve')
    pts=' '.join(f'{x},{y}' for x,y in points)
    dash=' stroke-dasharray="17 13"' if dashed else ''
    svg.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"{dash}/>')
    if head:
        x,y=points[-1]; px,py=points[-2]; a=math.atan2(y-py,x-px); h=19
        sides=[(x,y),(x-h*math.cos(a)+h*.5*math.sin(a),y-h*math.sin(a)-h*.5*math.cos(a)),(x-h*math.cos(a)-h*.5*math.sin(a),y-h*math.sin(a)+h*.5*math.cos(a))]
        d.polygon(sides,fill=color)
        svg.append('<polygon points="'+' '.join(f'{a:.2f},{b:.2f}' for a,b in sides)+f'" fill="{color}"/>')

def node(box, title, body=(), fill='#EAF3FA', outline='#5185A6'):
    rect(box,fill,outline)
    x1,y1,x2,y2=box; x=(x1+x2)/2
    text(x,y1+44,title,43,bold=True)
    for i,value in enumerate(body):
        text(x,y1+98+i*46,value,38,MUTED)

# Request and data routes are drawn beneath the component cards.
line([(1000,150),(1000,190),(500,190),(500,245)],head=True)
line([(1000,190),(1500,190),(1500,245)],head=True)
line([(500,370),(500,414),(1000,414),(1000,460)],head=True)
line([(1500,370),(1500,414),(1000,414)],head=False)
line([(1000,610),(1000,659),(525,659),(525,770)],head=True)
line([(1000,659),(1475,659),(1475,770)],head=True)
line([(525,1110),(525,1190),(1475,1190),(1475,1260)],head=True)
line([(525,1190),(525,1260)],head=True)
line([(1475,1110),(1475,1190)],head=False)

node((600,20,1400,150),'客户与管理后台',('HTTPS 浏览器访问',))
node((100,245,900,370),'主域名 待配置',('托管冗余 DNS',))
node((1100,245,1900,370),'备用域名 待配置',('提前公布并配置 DNS 与 TLS',))
node((450,460,1550,610),'托管冗余负载均衡',('健康检查与摘除故障实例',))

for x1,x2,cx,label in [(100,950,525,'应用主机 A · 故障域 A'),(1050,1900,1475,'应用主机 B · 故障域 B')]:
    rect((x1,710,x2,1110),'#F4F8FB','#8DAABA',28,4)
    text(cx,745,label,41,bold=True)
    node((x1+45,800,x2-45,950),'Caddy + Gunicorn + Django',('Compose · 无状态 · 相同镜像',),'#EAF6F3','#4D9A8A')
    rect((x1+45,985,x2-45,1070),'#EEF8F6','#4D9A8A',15)
    text(cx,1028,'systemd timer · 同步任务',39,TEAL,bold=True)

node((100,1260,950,1440),'托管高可用 PostgreSQL',('主备与自动故障切换', '业务数据 · Session · 任务锁'),'#EDF1FA','#778FB4')
node((1050,1260,1900,1440),'冗余对象存储',('用户附件 · 加密备份', '应用实例之外持久保存'),'#FFF7E9','#D1AC62')
text(1000,1155,'共享私网访问',38,BLUE)
text(1000,1500,'冗余调度入口共享数据库锁与任务租约 · 幂等处理',40,TEAL)
text(1000,1550,'推荐正式部署方案 · 云端故障切换指标需实测',37,MUTED)

OUT.mkdir(parents=True,exist_ok=True)
im.save(OUT/'ha-architecture.png',dpi=(300,300),optimize=True)
svg.append('</svg>')
(OUT/'ha-architecture.svg').write_text('\n'.join(svg),encoding='utf-8')
print(OUT/'ha-architecture.png')
