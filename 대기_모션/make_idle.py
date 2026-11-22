"""Idle loop for the pixel hero: breathing, lagging hair, cape sway, a blink and a glance back."""
import math
from PIL import Image, ImageSequence

SRC = '../../images/1.gif'
SKIN, LASH = (248, 205, 164, 255), (24, 19, 29, 255)
N, MS = 24, 120

idle = next(ImageSequence.Iterator(Image.open(SRC))).convert('RGBA').resize((320, 320), Image.NEAREST)
src = idle.load()

KNEE = 210      # rows above this sink while breathing out (native px)
HAIR_TOP = 78   # hair rows above this lag one frame behind
SWORD_X = 180   # columns right of the legs: only the sword lives here, move it whole
CAPE = (88, 125, 160, 214)  # left cape: x0, x1, y0, y1
FLAP = 3.0  # art px the hem swings at the very bottom
EYE = (159, 167, 97, 104)   # x0, x1, y0, y1 (exclusive ends)


def frame(breath, hair, phase, eye):
    out = Image.new('RGBA', (320, 320))
    o = out.load()
    for y in range(320):
        for x in range(320):
            if y < HAIR_TOP:
                d = 2 * hair
            elif y < KNEE or x >= SWORD_X:
                d = 2 * breath
            else:
                d = 0
            sy = y - d
            if 0 <= sy < 320:
                o[x, y] = src[x, sy]
    # cape hem swings more towards its bottom edge
    x0, x1, y0, y1 = CAPE
    for y in range(y0, y1):
        depth = (y - y0) / (y1 - y0)
        # a wave that travels down the cape: lower rows lag behind and swing wider
        off = 2 * round(FLAP * depth ** 1.5 * math.sin(phase - 2.2 * depth))
        if not off:
            continue
        row = [o[x, y] for x in range(x0 - 8, x1)]
        for i, x in enumerate(range(x0 - 8, x1)):
            j = min(max(i - off, 0), len(row) - 1)
            if x > x1 - 3 and off < 0:  # keep the seam with the tunic closed
                continue
            o[x, y] = row[j]
    ex0, ex1, ey0, ey1 = EYE
    ey0, ey1 = ey0 + 2 * breath, ey1 + 2 * breath
    if eye == 'closed':
        for y in range(ey0, ey1):
            for x in range(ex0, ex1):
                o[x, y] = LASH if y in (ey0 + 3, ey0 + 4) else SKIN
    elif eye == 'back':  # pupil slides to the back of the eye
        patch = [[o[x, y] for x in range(ex0, ex1)] for y in range(ey0, ey1)]
        for r, y in enumerate(range(ey0, ey1)):
            for c, x in enumerate(range(ex0, ex1)):
                o[x, y] = patch[r][ex1 - ex0 - 1 - c]
    return out


breath = [0] * 6 + [1] * 6 + [0] * 6 + [1] * 6
frames = []
for i in range(N):
    phase = 2 * math.pi * 2 * i / N  # two flaps per loop
    eye = 'closed' if i == 8 else 'back' if 15 <= i <= 19 else 'open'
    frames.append(frame(breath[i], breath[i - 1], phase, eye))

sheet = Image.new('RGBA', (320 * N, 320))
for i, f in enumerate(frames):
    sheet.alpha_composite(f, (320 * i, 0))
sheet.save('idle_sheet.png')


def white(f):
    bg = Image.new('RGBA', f.size, 'white')
    bg.alpha_composite(f)
    return bg.convert('RGB').resize((640, 640), Image.NEAREST)


seq = [white(f) for f in frames]
seq[0].save('idle.gif', save_all=True, append_images=seq[1:], duration=MS, loop=0)
print('ok', N, 'frames at', MS, 'ms')
