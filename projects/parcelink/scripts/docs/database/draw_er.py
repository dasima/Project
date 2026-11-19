from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import html


import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import generator_context

ROOT = Path(__file__).resolve().parents[3]
CONTEXT = generator_context(ROOT, 'Draw the logistics entity relationship overview.')
OUT = CONTEXT.output_root / 'assets/database'
OUT.mkdir(parents=True, exist_ok=True)
W, H = 2300, 1740
FONT = str(CONTEXT.font_path)
INK = '#111827'
TEXT = '#334155'
MUTED = '#526477'
BLUE = '#416983'
AUTH = '#727B86'
FONTS = {}
im = Image.new('RGB', (W, H), 'white')
d = ImageDraw.Draw(im)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
       '<rect width="2300" height="1740" fill="white"/>']


def font(size):
    if size not in FONTS:
        FONTS[size] = ImageFont.truetype(FONT, size)
    return FONTS[size]


def text(x, y, value, size=37, color=TEXT, anchor='lm', bold=False):
    d.text((x, y), value, font=font(size), fill=color, anchor=anchor,
           stroke_width=0.3 if bold else 0)
    align = {'l': 'start', 'm': 'middle', 'r': 'end'}[anchor[0]]
    svg.append(f'<text x="{x}" y="{y}" font-family="{html.escape(CONTEXT.font_family, quote=True)}, sans-serif" '
               f'font-size="{size}" text-anchor="{align}" dominant-baseline="central" '
               f'font-weight="{600 if bold else 400}" fill="{color}">{html.escape(value)}</text>')


def line(points, color=BLUE, width=4, dashed=False):
    if dashed:
        for (x1,y1),(x2,y2) in zip(points,points[1:]):
            length = abs(x2-x1) + abs(y2-y1)
            for start in range(0,int(length),24):
                end = min(start+14,length)
                p1 = (x1+(x2-x1)*start/length,y1+(y2-y1)*start/length)
                p2 = (x1+(x2-x1)*end/length,y1+(y2-y1)*end/length)
                d.line([p1,p2], fill=color, width=width)
    else:
        d.line(points, fill=color, width=width, joint='curve')
    pts = ' '.join(f'{x},{y}' for x,y in points)
    dash = ' stroke-dasharray="14 10"' if dashed else ''
    svg.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" '
               f'stroke-linejoin="round"{dash}/>')


def label(x,y,value,color=BLUE,anchor='mm',size=37):
    # White backing keeps cardinalities separate from nearby connection lines.
    box = d.textbbox((x,y), value, font=font(size), anchor=anchor)
    pad = 7
    d.rectangle((box[0]-pad,box[1]-3,box[2]+pad,box[3]+4),fill='white')
    svg.append(f'<rect x="{box[0]-pad}" y="{box[1]-3}" width="{box[2]-box[0]+2*pad}" '
               f'height="{box[3]-box[1]+7}" fill="white"/>')
    text(x,y,value,size,color,anchor)


def card(box, table, title, fields, framework=False):
    x1,y1,x2,y2=box
    fill = '#F0F2F4' if framework else '#EEF5FA'
    border = '#9CA5AE' if framework else '#8EADBF'
    d.rounded_rectangle(box,radius=16,fill=fill,outline=border,width=3)
    svg.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="16" '
               f'fill="{fill}" stroke="{border}" stroke-width="3"/>')
    text(x1+24,y1+31,table,36,INK,bold=True)
    text(x1+24,y1+77,title,40,INK,bold=True)
    line([(x1+22,y1+107),(x2-22,y1+107)],border,2)
    for i,value in enumerate(fields):
        text(x1+24,y1+137+i*42,value,36,TEXT)


text(90,55,'集运系统 · 数据库关系概览',54,INK,bold=True)
text(90,112,'Django 5.2 / PostgreSQL 17 · 9 张业务表 + Django 用户表',37,MUTED)

# A three-column arrangement keeps the central shipment relationships visible.
# Counts next to an entity denote how many instances may match the opposite end.
boxes = {
    'user': (120,190,700,440),
    'mapping': (855,190,1465,440),
    'customer': (1640,190,2230,440),
    'carrier': (120,630,700,880),
    'shipment': (855,630,1465,880),
    'package': (1640,630,2230,880),
    'receipt': (120,1070,700,1320),
    'event': (855,1070,1465,1320),
    'job': (1640,1070,2230,1320),
    'audit': (855,1440,1465,1690),
}

# Framework user -> customer mapping; customer -> mapping.
line([(700,315),(855,315)],AUTH)
line([(1465,315),(1640,315)])

# Required customer on shipment; required customer on every package.
line([(1835,440),(1835,535),(1160,535),(1160,630)])
line([(2070,440),(2070,630)])

# An optional carrier on a shipment, and required carrier on webhook receipt.
line([(700,755),(855,755)])
line([(410,880),(410,1070)])

# Optional shipment on a package. The customer edge above remains required.
line([(1465,755),(1640,755)])

# Shipment's child records: events, at most one sync job, and optional audit links.
line([(1160,880),(1160,1070)])
line([(1360,880),(1360,975),(1935,975),(1935,1070)])
line([(855,820),(780,820),(780,1375),(1040,1375),(1040,1440)])

# Nullable actor uses an outside channel to avoid crossing the business paths.
line([(120,315),(65,315),(65,1565),(855,1565)],AUTH,dashed=True)

card(boxes['user'],'auth_user','用户（Django 管理）',
     ['id · PK','username · UNIQUE','其余字段由 Django 维护'],True)
card(boxes['mapping'],'logistics_customer_user','客户账号映射',
     ['id · PK','customer_id · FK','user_id · FK · UNIQUE'])
card(boxes['customer'],'logistics_customer','客户',
     ['id · PK','code · UNIQUE','name'])
card(boxes['carrier'],'logistics_carrier','承运商',
     ['id · PK','code · UNIQUE','name'])
card(boxes['shipment'],'logistics_shipment','运单',
     ['id · PK','customer_id · FK','carrier_id · FK · NULL'])
card(boxes['package'],'logistics_package','包裹',
     ['id · PK','customer_id · FK','shipment_id · FK · NULL'])
card(boxes['receipt'],'logistics_webhook_receipt','已验签回调',
     ['id · PK','carrier_id · FK','event_key'])
card(boxes['event'],'logistics_tracking_event','物流轨迹',
     ['id · PK','shipment_id · FK','occurred_at'])
card(boxes['job'],'logistics_sync_job','物流同步任务',
     ['id · PK','shipment_id · FK · UNIQUE','next_retry_at'])
card(boxes['audit'],'logistics_audit_log','审计日志',
     ['id · PK','shipment_id · FK · NULL','actor_id · FK · NULL'])

# Endpoint cardinalities, offset from both the cards and connection paths.
label(726,284,'1',AUTH)
label(811,284,'0..1',AUTH)
label(1504,284,'0..*')
label(1614,284,'1')
label(1799,469,'1')
label(1120,595,'0..*')
label(2120,471,'1')
label(2128,597,'0..*')
label(744,718,'0..1')
label(807,793,'0..*')
label(373,918,'1')
label(355,1030,'0..*')
label(1508,718,'0..1')
label(1597,793,'0..*')
label(1122,918,'1')
label(1105,1030,'0..*')
label(1400,917,'1')
label(1985,1030,'0..1')
label(810,849,'0..1')
label(996,1407,'0..*')
label(123,477,'0..1',AUTH)
label(803,1528,'0..*',AUTH)

# A compact interpretation guide occupies the otherwise empty lower right.
text(1640,1400,'端点基数与约束',39,INK,bold=True)
text(1640,1450,'1：必填单个    0..1：可空单个',34,MUTED)
text(1640,1493,'0..*：零个或多个',34,MUTED)
text(1640,1544,'包裹 → 运单复合外键：',34,MUTED)
text(1640,1587,'(shipment_id, customer_id)',34,TEXT)
text(1640,1630,'确保双方同属一个客户；',34,MUTED)
text(1640,1673,'预报包裹可暂不配运单。',34,MUTED)

text(145,1395,'灰框：Django 默认用户表',34,MUTED)
text(145,1439,'其余 auth / session 等框架表省略；',34,MUTED)
text(145,1483,'均由 Django migrate 创建。',34,MUTED)

im.save(OUT/'er-overview.png',dpi=(300,300),optimize=True)
svg.append('</svg>')
(OUT/'er-overview.svg').write_text('\n'.join(svg),encoding='utf-8')
print(f'Wrote {OUT / "er-overview.png"} ({W} × {H})')
print(f'Wrote {OUT / "er-overview.svg"}')
