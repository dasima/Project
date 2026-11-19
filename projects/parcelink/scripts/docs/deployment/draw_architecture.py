from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import html
import math


import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import generator_context

ROOT = Path(__file__).resolve().parents[3]
CONTEXT = generator_context(ROOT, 'Draw the single-host deployment architecture.')
OUT = CONTEXT.output_root / 'assets/deployment'
OUT.mkdir(parents=True, exist_ok=True)
W, H = 2000, 1640
FINAL_H = 1600
FONT = str(CONTEXT.font_path)
BG = '#FFFFFF'
INK = '#143247'
MUTED = '#50697A'
BLUE = '#28648C'
TEAL = '#227D78'
BORDER = '#A9BFCD'
FONT_CACHE = {}
im = Image.new('RGB', (W, H), BG)
d = ImageDraw.Draw(im)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{FINAL_H}" viewBox="0 25 {W} {FINAL_H}">', '<rect x="0" y="25" width="2000" height="1600" fill="white"/>']


def font(size):
    if size not in FONT_CACHE:
        FONT_CACHE[size] = ImageFont.truetype(FONT, size)
    return FONT_CACHE[size]


def rect(box, fill, outline, radius=20, width=3):
    x1, y1, x2, y2 = box
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    svg.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="{radius}" fill="{fill}" stroke="{outline}" stroke-width="{width}"/>')


def line(points, color=BLUE, width=6, dashed=False):
    if not dashed:
        d.line(points, fill=color, width=width, joint='curve')
    else:
        dash, gap = 17, 13
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            length = math.hypot(x2-x1, y2-y1)
            for start in range(0, int(length), dash+gap):
                stop = min(start+dash, length)
                d.line([(x1+(x2-x1)*start/length, y1+(y2-y1)*start/length),
                        (x1+(x2-x1)*stop/length, y1+(y2-y1)*stop/length)], fill=color, width=width)
    pts = ' '.join(f'{x},{y}' for x, y in points)
    dash_attr = ' stroke-dasharray="17 13"' if dashed else ''
    svg.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"{dash_attr}/>')


def arrow(points, color=BLUE, width=6, dashed=False, head=18):
    line(points, color, width, dashed)
    x, y = points[-1]
    px, py = points[-2]
    angle = math.atan2(y-py, x-px)
    sides = [(x, y),
             (x-head*math.cos(angle)+head*0.5*math.sin(angle), y-head*math.sin(angle)-head*0.5*math.cos(angle)),
             (x-head*math.cos(angle)-head*0.5*math.sin(angle), y-head*math.sin(angle)+head*0.5*math.cos(angle))]
    d.polygon(sides, fill=color)
    pts = ' '.join(f'{a:.2f},{b:.2f}' for a,b in sides)
    svg.append(f'<polygon points="{pts}" fill="{color}"/>')


def text(x, y, value, size=34, fill=INK, anchor='mm', bold=False):
    size = max(37, size)  # >=9 pt when printed at the document's 6.85-inch width.
    # Pillow anchors center the font metrics; SVG uses the same central baseline.
    d.text((x, y), value, font=font(size), fill=fill, anchor=anchor, stroke_width=0.25 if bold else 0)
    align = 'middle' if anchor[0] == 'm' else ('start' if anchor[0] == 'l' else 'end')
    svg.append(f'<text x="{x}" y="{y}" font-family="{html.escape(CONTEXT.font_family, quote=True)}, sans-serif" font-size="{size}" text-anchor="{align}" dominant-baseline="central" fill="{fill}" font-weight="{600 if bold else 400}">{html.escape(value)}</text>')


def node(box, title, body=(), fill='#FFFFFF', outline=BORDER, title_size=40, title_y=None):
    rect(box, fill, outline)
    x1,y1,x2,y2 = box
    cx = (x1+x2)/2
    if title_y is None:
        title_y = y1 + 43
    text(cx, title_y, title, title_size, bold=True)
    for i, value in enumerate(body):
        text(cx, title_y + 53 + i*45, value, 34, MUTED)


# Deployment and private network boundaries.
rect((50, 350, 1505, 1530), '#F4F8FB', '#8DAABA', 30, 4)
text(95, 390, '单台云主机 · Linux VM', 42, anchor='lm', bold=True)
rect((110, 430, 1450, 1320), '#FFFFFF', '#B3C6D2', 24, 3)
text(150, 466, 'Docker Compose · 私有网络', 36, MUTED, anchor='lm')

# All connection paths are drawn before the component cards.
line([(480,180), (480,270), (1180,270), (1180,180)], BLUE, 6)
arrow([(830,270), (830,500)], BLUE)
arrow([(605,650), (605,790)], BLUE)
arrow([(605,940), (605,1075)], BLUE)
arrow([(605,1190), (605,1230)], '#6C899B', 5, head=14)

# Signed callbacks are accepted at the TLS edge, never at the database.
arrow([(1580,610), (1010,610)], BLUE)
# Scheduled outbound carrier polling.
arrow([(1265,805), (1265,730), (1580,730)], TEAL, dashed=True)
# The short-lived sync container shares the Compose database network.
arrow([(1100,960), (1060,960), (1060,1133), (1010,1133)], TEAL, dashed=True)
# The timer belongs to the host and launches the transient application container.
arrow([(1390,1380), (1390,1040)], TEAL, dashed=True)
# A database-consistent dump is copied to storage outside this VM.
arrow([(200,1133), (150,1133), (150,1430), (200,1430)], TEAL, dashed=True)
arrow([(565,1480), (565,1565), (1765,1565), (1765,1450)], TEAL, dashed=True)

# Client surfaces.
node((200,40,760,180), '客户 / 手机浏览器', ('物流查询',), '#F3F8FD', '#AAC4D7', title_y=87)
node((900,40,1460,180), '管理后台浏览器', ('运单、物流与配置',), '#F3F8FD', '#AAC4D7', title_y=87)
text(830,220, '同源 HTTPS · Session Cookie', 35, BLUE)
text(100,315, '公网：443；80 用于跳转或证书验证', 34, MUTED, anchor='lm')
text(1060,315, 'SSH：仅 VPN / 白名单', 34, MUTED, anchor='lm')

# Compose services.
node((200,500,1010,650), 'Caddy · HTTPS 入口', ('前端 HTML/CSS/JS · /static · TLS',), '#EAF3FA', '#5185A6', title_y=548)
node((200,790,1010,940), 'Django + Gunicorn · web', ('业务 API / 管理后台 · 内部 :8000',), '#EAF6F3', '#4D9A8A', title_y=838)
node((200,1075,1010,1190), 'PostgreSQL 17 · db', ('私网 :5432 · 不发布宿主机端口',), '#EDF1FA', '#778FB4', title_y=1113)
rect((200,1230,1010,1290), '#F4F6FA', '#A5B4C7', 14, 3)
text(605,1260, '持久化卷 · postgres_data', 35, MUTED)

node((1100,805,1430,1040), '物流同步临时任务', ('复用 web 镜像', 'manage.py', 'sync_tracking'), '#EEF8F6', '#4D9A8A', title_size=38, title_y=846)

# Host scheduling and backup controls sit outside the Compose boundary.
node((1055,1380,1450,1480), '宿主机定时器', ('systemd timer',), '#F1F4F8', '#97ACBC', title_size=37, title_y=1406)
rect((200,1380,930,1480), '#F1F4F8', '#97ACBC', 20, 3)
text(565,1430, '每日备份 · pg_dump', 40, bold=True)

# Services beyond the cloud VM.
node((1580,500,1950,900), '外部承运商平台', (), '#FFF7E9', '#D1AC62', title_size=38, title_y=550)
line([(1610,595), (1920,595)], '#E6D5B4', 3)
text(1765,665, '物流查询 API', 35, MUTED)
text(1765,810, '签名回调', 35, MUTED)
node((1580,1210,1950,1450), '异机对象存储', ('加密备份', '云主机之外'), '#FFF7E9', '#D1AC62', title_size=38, title_y=1258)

# Connector labels are placed only in clear channels.
text(800,713, '代理 /api、/admin', 35, BLUE)
text(780,1007, '私网 :5432', 35, BLUE)
text(1285,525, '签名 Webhook', 35, BLUE)
text(1285,569, 'HTTPS :443', 34, BLUE)
text(1395,684, 'HTTPS 轮询', 35, TEAL)
text(1220,1096, '私网 :5432', 34, TEAL)
text(1218,1235, '按计划触发', 34, TEAL)
text(1160,1542, '加密上传 · 异机保存', 34, TEAL)

# Compact print legend.
arrow([(400,1605), (495,1605)], BLUE, 5, head=14)
text(520,1605, '请求 / 数据', 34, MUTED, anchor='lm')
arrow([(1020,1605), (1115,1605)], TEAL, 5, dashed=True, head=14)
text(1140,1605, '定时任务 / 备份', 34, MUTED, anchor='lm')

im.crop((0,25,W,1625)).save(OUT / 'architecture.png', dpi=(300,300), optimize=True)
svg.append('</svg>')
(OUT / 'architecture.svg').write_text('\n'.join(svg), encoding='utf-8')
print(f'Wrote {OUT / "architecture.png"} ({W} × {FINAL_H})')
print(f'Wrote {OUT / "architecture.svg"}')
