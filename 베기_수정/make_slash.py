"""Rebuild the sword-slash GIF: clean body, real arm (2-bone IK), crisp sword, lean/crouch, smear."""
import math
from collections import Counter
from PIL import Image, ImageSequence

SRC = '../../images/1.gif'
OUTLINE = (24, 19, 29, 255)
BLADE = [(232, 229, 235, 255), (207, 204, 211, 255), (133, 129, 141, 255)]  # top, mid, bottom
GUARD = (170, 165, 177, 255)
GRIP = (101, 65, 51, 255)
SLEEVE = [(89, 59, 97, 255), (70, 48, 78, 255)]  # light, dark
CUFF = (230, 206, 177, 255)
GLOVE = [(154, 100, 71, 255), (130, 84, 61, 255), (101, 65, 51, 255)]
SMEAR = [(255, 245, 235, 255), (232, 229, 235, 255), (207, 204, 211, 255)]

frames = [f.convert('RGBA') for f in ImageSequence.Iterator(Image.open(SRC))]
nat = [f.resize((320, 320), Image.NEAREST) for f in frames]  # source pixels are 2x2 blocks
n0, n7 = nat[0], nat[7]


def inpaint(img, mask):
    px = img.load()
    mask = set(mask)
    while mask:
        done = []
        for (x, y) in mask:
            nb = [px[x + dx, y + dy] for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                  if (dx or dy) and (x + dx, y + dy) not in mask and px[x + dx, y + dy][3]]
            if len(nb) >= 3:
                done.append(((x, y), Counter(nb).most_common(1)[0][0]))
        if not done:
            break
        for p, c in done:
            px[p] = c
            mask.discard(p)


def is_handish(c):
    r, g, b, a = c
    return a and (r > g + 15 and r > b + 15 or max(c[:3]) - min(c[:3]) < 25 and r > 90)  # browns/skin/beige/grey


# --- clean body: frame 0 above the cuff, frame 7 (already repainted without hand) below ---
base = n7.copy()
base.paste(n0.crop((0, 0, 320, 147)), (0, 0))
bp = base.load()
gold = (207, 152, 75, 255)
hole = [(x, y) for x in range(112, 153) for y in range(140, 170) if is_handish(bp[x, y]) and bp[x, y] != gold]
for x, y in hole:
    bp[x, y] = (0, 0, 0, 0)
# transparent pixels not reachable from the border are holes
outside, stack = set(), [(0, 0)]
while stack:
    x, y = stack.pop()
    if (x, y) in outside or not (0 <= x < 320 and 0 <= y < 320) or bp[x, y][3]:
        continue
    outside.add((x, y))
    stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
holes = [(x, y) for x in range(100, 210) for y in range(130, 215) if not bp[x, y][3] and (x, y) not in outside]
specks = [(x, y) for x in range(100, 210) for y in range(165, 215)
          if bp[x, y][3] and max(bp[x, y][:3]) - min(bp[x, y][:3]) < 25 and bp[x, y][0] > 90]
inpaint(base, hole + holes + specks)
# drop the dotted leftovers of the old blade (tiny islands)
seen = set()
for y in range(320):
    for x in range(320):
        if bp[x, y][3] and (x, y) not in seen:
            comp, st = [], [(x, y)]
            while st:
                p = st.pop()
                if p in seen or not (0 <= p[0] < 320 and 0 <= p[1] < 320) or not bp[p][3]:
                    continue
                seen.add(p)
                comp.append(p)
                st += [(p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1)]
            if len(comp) < 30:
                for p in comp:
                    bp[p] = (0, 0, 0, 0)
# belt continues where the cuff used to cover it
n0p = n0.load()
for y in range(146, 159):
    for x in range(127, 153):
        bp[x, y] = n0p[x, y] if x >= 141 else n0p[145, y] if x > 127 else OUTLINE

FEET, KNEE, TOP = 243, 212, 59  # native rows


def pose_body(lean, crouch):
    """lean: art px offset at head top (+ = forward). crouch: art px knee bend."""
    out = Image.new('RGBA', (320, 320))
    src = base.load()
    o = out.load()
    for y in range(320):
        if y >= KNEE:
            sy, dx = y, 0
        else:
            sy = y - 2 * crouch
            dx = 2 * round(lean * (KNEE - sy) / (KNEE - TOP))
        for x in range(320):
            c = src[x, sy] if 0 <= sy < 320 else (0, 0, 0, 0)
            if c[3] and 0 <= x + dx < 320:
                o[x + dx, y] = c
    return out


def shift_at(lean, crouch, ny):
    return 2 * round(lean * (KNEE - ny) / (KNEE - TOP)) / 2, -crouch  # art px


# ---------- art-resolution (160) drawing ----------
def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy or 1)))
    return math.hypot(px - ax - t * vx, py - ay - t * vy)


def draw_capsule(layer, a, b, r, colors):
    """colors[0] on the upper side of the segment, colors[1] elsewhere."""
    lp = layer.load()
    nx, ny = -(b[1] - a[1]), b[0] - a[0]
    n = math.hypot(nx, ny) or 1
    if ny > 0:
        nx, ny = -nx, -ny  # normal pointing up on screen
    for y in range(int(min(a[1], b[1]) - r - 1), int(max(a[1], b[1]) + r + 2)):
        for x in range(int(min(a[0], b[0]) - r - 1), int(max(a[0], b[0]) + r + 2)):
            if 0 <= x < 160 and 0 <= y < 160 and seg_dist(x + .5, y + .5, *a, *b) <= r:
                side = ((x + .5 - a[0]) * nx + (y + .5 - a[1]) * ny) / n
                lp[x, y] = colors[0] if side > r * 0.35 else colors[1]


def draw_sword(layer, hx, hy, ang):
    lp = layer.load()
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    for y in range(160):
        for x in range(160):
            dx, dy = x + .5 - hx, -(y + .5 - hy)  # y up
            u, v = dx * ca + dy * sa, -dx * sa + dy * ca  # along blade, across (+ = blade top)
            c = None
            if 3.5 <= u <= 31 and abs(v) <= 2.2 * min(1, (33 - u) / 4):
                c = BLADE[0] if v > 0.8 else BLADE[1] if v > -0.8 else BLADE[2]
            elif 1.5 <= u < 3.5 and abs(v) <= 4.6:
                c = GUARD
            elif -6 <= u < 1.5 and abs(v) <= 1.1:
                c = GRIP
            elif -8.6 <= u < -6 and abs(v) <= 1.8:
                c = GUARD
            if c:
                lp[x, y] = c


def draw_smear(layer, hx, hy, a0, a1, strength):
    """Crescent between the previous and current blade angles."""
    lp = layer.load()
    lo, hi = sorted((a0, a1))
    for y in range(160):
        for x in range(160):
            dx, dy = x + .5 - hx, -(y + .5 - hy)
            r = math.hypot(dx, dy)
            a = math.degrees(math.atan2(dy, dx))
            for k in (-360, 0, 360):
                if lo <= a + k <= hi:
                    t = (a + k - a1) / (a0 - a1)  # 0 at sword, 1 at trailing end
                    inner = 22 + 10 * t
                    if inner <= r <= 34 - 1.5 * t and t <= strength:
                        lp[x, y] = SMEAR[0] if r > 31.5 - 1.5 * t else SMEAR[1] if t < 0.5 else SMEAR[2]
                    break


def draw_glove(layer, hx, hy):
    lp = layer.load()
    for y in range(round(hy) - 2, round(hy) + 2):
        for x in range(round(hx) - 2, round(hx) + 2):
            ex, ey = x - round(hx) + 2, y - round(hy) + 2
            lp[x, y] = GLOVE[0] if ey == 0 else GLOVE[2] if ey == 3 or ex == 3 else GLOVE[1]


def outline(layer):
    lp = layer.load()
    pts = [(x, y) for y in range(1, 159) for x in range(1, 159) if not lp[x, y][3]
           and any(lp[x + dx, y + dy][3] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    for p in pts:
        lp[p] = OUTLINE


def ik(s, h, l1=11.5, l2=11.5):
    dx, dy = h[0] - s[0], h[1] - s[1]
    d = min(math.hypot(dx, dy), l1 + l2 - 0.01)
    base_a = math.atan2(dy, dx)
    cos_a = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    a = base_a + math.acos(max(-1, min(1, cos_a)))  # elbow bends down/back
    elbow = (s[0] + l1 * math.cos(a), s[1] + l1 * math.sin(a))
    h = (s[0] + d * math.cos(base_a), s[1] + d * math.sin(base_a))
    return elbow, h


SHOULDER = (69, 66)  # art px on the clean body


def render(hand, ang, lean, crouch, smear=None):
    body = pose_body(lean, crouch)
    sx = SHOULDER[0] + shift_at(lean, crouch, SHOULDER[1] * 2)[0]
    s = (sx, SHOULDER[1] + crouch)
    elbow, h = ik(s, (hand[0], hand[1] + crouch))
    behind = ang > 120

    def layer():
        return Image.new('RGBA', (160, 160))

    sword, arm, fx = layer(), layer(), layer()
    if smear:
        draw_smear(fx, h[0], h[1], smear[0], ang, smear[1])
        outline(fx)
    draw_sword(sword, h[0], h[1], ang)
    outline(sword)
    draw_capsule(arm, s, elbow, 2.3, SLEEVE)
    fore_end = (elbow[0] + (h[0] - elbow[0]) * 0.7, elbow[1] + (h[1] - elbow[1]) * 0.7)
    draw_capsule(arm, elbow, fore_end, 2.1, SLEEVE)
    draw_capsule(arm, fore_end, (elbow[0] + (h[0] - elbow[0]) * 0.85, elbow[1] + (h[1] - elbow[1]) * 0.85), 2.4,
                 (CUFF, CUFF))
    draw_glove(arm, h[0], h[1])
    outline(arm)

    up = lambda im: im.resize((320, 320), Image.NEAREST)
    out = Image.new('RGBA', (320, 320))
    order = [sword, None, fx, arm] if behind else [None, fx, arm, sword]
    for item in order:
        if item is None:
            out.alpha_composite(body)
        else:
            out.alpha_composite(up(item))
    if not behind:  # fingers wrap over the grip
        g = layer()
        draw_glove(g, h[0], h[1])
        out.alpha_composite(up(g))
    return out


# (hand art px, sword angle deg, lean, crouch, smear(prev_angle, length), ms)
def main():
    KEYS = [
        (None, None, 0, 0, None, 220),           # idle (original art)
        ((64, 72), 140, -1, 0, None, 70),        # lift, blade swings back
        ((62, 56), 150, -2, 1, None, 70),        # hand up beside the head
        ((61, 52), 160, -2, 2, None, 130),       # hold: sword cocked behind
        ((72, 46), 95, 0, 1, (160, 1.0), 35),    # strike starts over the head
        ((88, 60), 20, 2, 2, (95, 1.0), 35),     # main cut
        ((90, 74), -40, 3, 2, (20, 0.8), 55),    # impact
        ((86, 81), -55, 2, 1, (-20, 0.4), 80),   # follow-through
        ((79, 85), -45, 1, 0, None, 90),         # settle
        ((71, 88), -30, 0, 0, None, 110),        # return
    ]

    out_frames, durations = [], []
    for hand, ang, lean, crouch, smear, ms in KEYS:
        f = n0.copy() if hand is None else render(hand, ang, lean, crouch, smear)
        out_frames.append(f.resize((640, 640), Image.NEAREST))
        durations.append(ms)

    out_frames[0].save('slash_fixed.gif', save_all=True, append_images=out_frames[1:], duration=durations,
                       loop=0, disposal=2, transparency=0)
    sheet = Image.new('RGBA', (320 * len(out_frames), 320))
    for i, f in enumerate(out_frames):
        sheet.paste(f.resize((320, 320), Image.NEAREST), (320 * i, 0))
    sheet.save('slash_fixed_sheet.png')
    base.save('base_clean.png')
    print('ok', len(out_frames))


if __name__ == '__main__':
    main()
