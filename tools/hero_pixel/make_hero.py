"""도트 주인공(보라 망토) 동작 시트를 만든다: python tools/hero_pixel/make_hero.py

재료 (이 폴더):
- source.gif        사용자가 준 도트 주인공 (첫 프레임이 기본 자세)
- base_clean.png    칼과 칼 든 팔을 지운 몸 (베기_수정/make_slash.py가 만든 것)
- ../../대기_모션/대기_시트_투명배경.png   사용자가 만든 숨쉬기 대기 24프레임 (한손검일 때 그대로 쓴다)

그림 한 칸(아트 픽셀)은 게임 화면 1px이다. 160 × 160 칸 프레임에서 발밑은 122줄, 몸 가운데는 71칸.
몸을 윗몸·뒷다리·앞다리로 나눠 줄 단위로 밀고(기울기·웅크림·다리 흔들기), 칼 든 팔은
두 마디 관절(IK)로 손 위치에 맞춰 새로 그린다. 공격은 player_attack.py의 키프레임을 그대로 따른다.

결과: assets/주인공_도트/hero_w{무기}.png (+ hero_echo.png)
  줄 순서: 대기 24, 걷기 8, 점프 8, 베기 10, 찌르기 10 (한 칸 160 × 160)
"""
import math
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
sys.path.insert(0, str(PROJECT))
import player_attack as pa  # noqa: E402

SIZE = 160
FEET, ACTOR_X = 121.5, 71
HIP, KNEE, TOP = 90, 106, 29.5        # 다리를 나누는 줄, 무릎(웅크림 기준) 줄, 머리 꼭대기
HAIR_TOP = 39                         # 이 위 머리카락은 한 박자 늦게 따라온다
CAPE = (44, 62, 70, 104)              # 망토 x0, x1, y0, y1
LEG_SPLIT = 72                        # 이 칸 왼쪽이 뒷다리
CAPE_EDGE = 58                        # 다리 줄에서 이 칸 왼쪽은 망토 자락
GLOVE = (84, 93, 80, 95)              # 칼 안 든 손 x0, x1, y0, y1
SHOULDER = (69, 66)
HEIGHT_SCALE = 0.78                   # 게임 키프레임 손 높이를 이 몸에 맞춘다

OUTLINE = (24, 19, 29, 255)
BLADE = [(232, 229, 235, 255), (207, 204, 211, 255), (133, 129, 141, 255)]
GUARD = (170, 165, 177, 255)
GRIP = (101, 65, 51, 255)
SLEEVE = [(89, 59, 97, 255), (70, 48, 78, 255)]
CUFF = (230, 206, 177, 255)
GLOVE_COLORS = [(154, 100, 71, 255), (130, 84, 61, 255), (101, 65, 51, 255)]
WOOD = [(150, 104, 66, 255), (112, 76, 48, 255)]
IRON = [(150, 150, 164, 255), (104, 104, 120, 255)]
ORB = [(150, 236, 255, 255), (84, 176, 232, 255)]

base = Image.open(HERE / 'base_clean.png').convert('RGBA').resize((SIZE, SIZE), Image.NEAREST)
BASE = base.load()


# ---------------------------------------------------------------- 몸 나누기와 조립

def _parts():
    upper, back, front = (Image.new('RGBA', (SIZE, SIZE)) for _ in range(3))
    u, b, f = upper.load(), back.load(), front.load()
    for y in range(SIZE):
        for x in range(SIZE):
            c = BASE[x, y]
            if not c[3]:
                continue
            glove = GLOVE[0] <= x < GLOVE[1] and GLOVE[2] <= y < GLOVE[3]
            if y < HIP or x < CAPE_EDGE or glove:
                u[x, y] = c
            elif x < LEG_SPLIT:
                b[x, y] = c
            else:
                f[x, y] = c
    return upper, back, front


UPPER, BACK_LEG, FRONT_LEG = _parts()


def _leg(layer, shear, lift):
    """다리를 엉덩이에서 발끝으로 갈수록 shear만큼 밀고, 발을 lift만큼 든다 (다리 줄을 고르게 줄인다).
    결과 줄마다 원본 줄을 거꾸로 찾아 빈 줄이나 겹친 줄이 생기지 않는다."""
    out = Image.new('RGBA', (SIZE, SIZE))
    src, o = layer.load(), out.load()
    bottom = FEET + 0.5
    for y in range(HIP, SIZE):
        sy = HIP + (y - HIP) * (bottom - HIP) / (bottom - lift - HIP)
        if sy >= SIZE:
            break
        sy = int(sy)
        dx = round(shear * (sy - HIP) / (FEET - HIP))
        for x in range(SIZE):
            c = src[x, sy]
            if c[3] and 0 <= x + dx < SIZE:
                o[x + dx, y] = c
    return out


def _upper(lean, drop, hair, cape_off, glove_dx):
    """윗몸: 위로 갈수록 lean만큼 기울고 drop만큼 내려앉는다. 머리카락은 hair만큼 더 내려온다."""
    out = Image.new('RGBA', (SIZE, SIZE))
    src, o = UPPER.load(), out.load()
    for y in range(SIZE):
        for x in range(SIZE):
            c = src[x, y]
            if not c[3]:
                continue
            nx, ny = x, y + (drop if y < KNEE else 0) + (hair if y < HAIR_TOP else 0)
            if y < KNEE:
                nx += round(lean * (KNEE - y) / (KNEE - TOP))
            if CAPE[0] <= x < CAPE[1] and CAPE[2] <= y < CAPE[3]:
                nx += cape_off(y)
            if GLOVE[0] <= x < GLOVE[1] and GLOVE[2] <= y < GLOVE[3]:
                nx += glove_dx
            if 0 <= nx < SIZE and 0 <= ny < SIZE:
                o[nx, ny] = c
    return out


def cape_wave(phase, amp, trail=0.0):
    """망토 자락: 아래로 갈수록 크게 흔들리고 trail만큼 뒤로 날린다."""
    def off(y):
        depth = max(0.0, (y - CAPE[2]) / (CAPE[3] - CAPE[2]))
        return round(amp * depth ** 1.5 * math.sin(phase - 2.2 * depth) - trail * depth ** 1.2)
    return off


# ---------------------------------------------------------------- 팔과 무기 (베기_수정/make_slash.py와 같은 방식)

def _seg(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy or 1)))
    return math.hypot(px - ax - t * vx, py - ay - t * vy)


def capsule(layer, a, b, r, colors):
    lp = layer.load()
    nx, ny = -(b[1] - a[1]), b[0] - a[0]
    n = math.hypot(nx, ny) or 1
    if ny > 0:
        nx, ny = -nx, -ny
    for y in range(int(min(a[1], b[1]) - r - 1), int(max(a[1], b[1]) + r + 2)):
        for x in range(int(min(a[0], b[0]) - r - 1), int(max(a[0], b[0]) + r + 2)):
            if 0 <= x < SIZE and 0 <= y < SIZE and _seg(x + .5, y + .5, *a, *b) <= r:
                side = ((x + .5 - a[0]) * nx + (y + .5 - a[1]) * ny) / n
                lp[x, y] = colors[0] if side > r * 0.35 else colors[1]


def weapon(layer, hx, hy, ang, index):
    """ang: 0이 앞, 90이 위 (y는 위로). index: 0 맨손, 1 단검, 2 한손검, 3 전투 망치, 4 마력 지팡이."""
    if index == 0:
        return
    lp = layer.load()
    ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    blade = {1: 15, 2: 31}.get(index, 0)
    for y in range(SIZE):
        for x in range(SIZE):
            dx, dy = x + .5 - hx, -(y + .5 - hy)
            u, v = dx * ca + dy * sa, -dx * sa + dy * ca
            c = None
            if index in (1, 2):
                if 3.5 <= u <= blade and abs(v) <= (1.8 if index == 1 else 2.2) * min(1, (blade + 2 - u) / 4):
                    c = BLADE[0] if v > 0.8 else BLADE[1] if v > -0.8 else BLADE[2]
                elif 1.5 <= u < 3.5 and abs(v) <= (3.4 if index == 1 else 4.6):
                    c = GUARD
                elif -6 <= u < 1.5 and abs(v) <= 1.1:
                    c = GRIP
                elif -8.6 <= u < -6 and abs(v) <= 1.8:
                    c = GUARD
            elif index == 3:
                if 19 <= u <= 27 and abs(v) <= 5.5:
                    c = IRON[0] if v > 0 else IRON[1]
                elif -6 <= u < 19 and abs(v) <= 1.2:
                    c = WOOD[0] if v > 0 else WOOD[1]
            else:
                if math.hypot(u - 27, v) <= 3.4:
                    c = ORB[0] if v > 0.5 or u < 26 else ORB[1]
                elif -14 <= u < 24 and abs(v) <= 1.2:
                    c = WOOD[0] if v > 0 else WOOD[1]
            if c:
                lp[x, y] = c


def glove(layer, hx, hy):
    lp = layer.load()
    for y in range(round(hy) - 2, round(hy) + 2):
        for x in range(round(hx) - 2, round(hx) + 2):
            ex, ey = x - round(hx) + 2, y - round(hy) + 2
            if 0 <= x < SIZE and 0 <= y < SIZE:
                lp[x, y] = GLOVE_COLORS[0] if ey == 0 else GLOVE_COLORS[2] if ey == 3 or ex == 3 else GLOVE_COLORS[1]


def outline(layer):
    lp = layer.load()
    points = [(x, y) for y in range(1, SIZE - 1) for x in range(1, SIZE - 1) if not lp[x, y][3]
              and any(lp[x + dx, y + dy][3] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    for point in points:
        lp[point] = OUTLINE


def ik(s, h, l1=14, l2=14):
    dx, dy = h[0] - s[0], h[1] - s[1]
    d = min(math.hypot(dx, dy), l1 + l2 - 0.01)
    base_a = math.atan2(dy, dx)
    a = base_a + math.acos(max(-1, min(1, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d))))
    return (s[0] + l1 * math.cos(a), s[1] + l1 * math.sin(a)), (s[0] + d * math.cos(base_a), s[1] + d * math.sin(base_a))


# ---------------------------------------------------------------- 한 프레임

def frame(index, *, lean=0, drop=0, hair=0, cape=None, glove_dx=0, front=(0, 0), back=(0, 0),
          hand=(72, 86), angle=-35, shift=0, trail=()):
    cape = cape or cape_wave(0, 0)
    body = Image.new('RGBA', (SIZE, SIZE))
    back_leg = _leg(BACK_LEG, *back)
    body.alpha_composite(back_leg)
    body.alpha_composite(_upper(lean, drop, hair, cape, glove_dx))
    body.alpha_composite(_leg(FRONT_LEG, *front))

    shoulder = (SHOULDER[0] + round(lean * (KNEE - SHOULDER[1]) / (KNEE - TOP)), SHOULDER[1] + drop)
    elbow, h = ik(shoulder, hand)
    behind = angle > 120 or angle < -200

    arm = Image.new('RGBA', (SIZE, SIZE))
    capsule(arm, shoulder, elbow, 2.3, SLEEVE)
    fore = (elbow[0] + (h[0] - elbow[0]) * 0.7, elbow[1] + (h[1] - elbow[1]) * 0.7)
    capsule(arm, elbow, fore, 2.1, SLEEVE)
    capsule(arm, fore, (elbow[0] + (h[0] - elbow[0]) * 0.85, elbow[1] + (h[1] - elbow[1]) * 0.85), 2.4, (CUFF, CUFF))
    glove(arm, *h)
    outline(arm)
    held = Image.new('RGBA', (SIZE, SIZE))
    weapon(held, h[0], h[1], angle, index)
    outline(held)

    out = Image.new('RGBA', (SIZE, SIZE))
    if behind:
        out.alpha_composite(held)
    out.alpha_composite(body)
    for ghost_hand, ghost_angle, strength in trail:   # 휘두를 때 무기 잔상
        layer = Image.new('RGBA', (SIZE, SIZE))
        weapon(layer, *ghost_hand, ghost_angle, index)
        layer.putalpha(layer.getchannel('A').point(lambda v: round(v * strength)))
        out.alpha_composite(layer)
    out.alpha_composite(arm)
    if not behind:
        out.alpha_composite(held)
        fingers = Image.new('RGBA', (SIZE, SIZE))
        glove(fingers, *h)
        out.alpha_composite(fingers)
    if shift:
        moved = Image.new('RGBA', (SIZE, SIZE))
        moved.alpha_composite(out, (shift, 0))
        out = moved
    return out


REST = {0: ((72, 86), -35), 1: ((72, 86), -35), 2: ((72, 86), -35), 3: ((72, 87), -70), 4: ((73, 84), 80)}


# ---------------------------------------------------------------- 동작

def idle(index):
    if index == 2:   # 한손검: 사용자가 만든 숨쉬기 대기를 그대로 쓴다
        sheet = Image.open(PROJECT / '대기_모션' / '대기_시트_투명배경.png').convert('RGBA')
        return [sheet.crop((320 * i, 0, 320 * i + 320, 320)).resize((SIZE, SIZE), Image.NEAREST)
                for i in range(sheet.width // 320)]
    hand, angle = REST[index]
    breath = [0] * 6 + [1] * 6 + [0] * 6 + [1] * 6
    return [frame(index, drop=breath[i], hair=breath[i - 1] - breath[i],
                  cape=cape_wave(2 * math.pi * 2 * i / 24, 1.5),
                  hand=(hand[0], hand[1] + breath[i]), angle=angle) for i in range(24)]


def walk(index):
    hand, angle = REST[index]
    frames = []
    for i in range(8):
        p = 2 * math.pi * i / 8
        swing = math.sin(p)
        frames.append(frame(
            index, lean=1, drop=1 if abs(swing) > 0.7 else 0, hair=1 if abs(swing) < 0.3 else 0,
            cape=cape_wave(p * 2, 2.0, trail=3.0), glove_dx=round(-1.5 * swing),
            front=(round(8 * swing), round(3 * max(0.0, math.cos(p)))),
            back=(round(-8 * swing), round(3 * max(0.0, -math.cos(p)))),
            hand=(hand[0] + round(2.5 * swing), hand[1]), angle=angle + 8 * swing))
    return frames


def jump(index):
    hand, angle = REST[index]
    frames = []
    for i in range(8):
        t = (i + 0.5) / 8
        crouch = 2 if t < 0.12 or t > 0.88 else 0
        tuck = math.sin(min(1.0, max(0.0, (t - 0.1) / 0.8)) * math.pi)
        rising = t < 0.5
        frames.append(frame(
            index, lean=1, drop=crouch, hair=-1 if rising and crouch == 0 else 1,
            cape=cape_wave(i, 1.0, trail=2 + 3 * tuck),
            front=(round(5 * tuck), round(10 * tuck)), back=(round(-4 * tuck), round(7 * tuck)),
            hand=(hand[0] + round(4 * tuck), hand[1] - round(9 * tuck)), angle=angle + 50 * tuck))
    return frames


def attack(index, kind):
    def pose(progress):
        fwd, height, game_angle, lunge = pa.weapon_pose(kind, progress)
        return (ACTOR_X + fwd + lunge, FEET - height * HEIGHT_SCALE), 90 - game_angle, lunge

    frames = []
    for i in range(10):
        progress = (i + 0.5) / 10
        hand, angle, lunge = pose(progress)
        lean = max(-2, min(3, round(lunge / 3)))
        trail = []
        for past, strength in pa.trail(progress):
            ghost_hand, ghost_angle, _ = pose(past)
            _, h = ik((SHOULDER[0] + round(lunge), SHOULDER[1]), ghost_hand)
            trail.append((h, ghost_angle, strength))
        step = round(lunge)
        frames.append(frame(
            index, lean=lean, drop=1 if abs(lunge) > 3 else 0,
            cape=cape_wave(i, 1.5, trail=max(0.0, lunge / 3)),
            front=(max(0, step // 2), 0), back=(min(0, -step // 2), 0),
            hand=(hand[0] - step, hand[1]), angle=angle, shift=step,
            trail=[((h[0] - step, h[1]), a, s) for h, a, s in trail]))
    return frames


ROWS = ('idle', 'walk', 'jump', 'slash', 'thrust')


def sheet(index):
    rows = [idle(index), walk(index), jump(index), attack(index, 'slash'), attack(index, 'thrust')]
    out = Image.new('RGBA', (SIZE * 24, SIZE * len(rows)))
    for r, frames in enumerate(rows):
        for c, f in enumerate(frames):
            out.alpha_composite(f, (SIZE * c, SIZE * r))
    return out


def echo(image):
    """분신: 밝기를 은빛·청록으로 바꾸고 조금 투명하게."""
    out = image.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a:
                light = (r * 0.3 + g * 0.59 + b * 0.11) / 255
                px[x, y] = (int(70 + 170 * light), int(96 + 150 * light), int(130 + 125 * light), int(a * 0.88))
    return out


def main():
    target = PROJECT / 'assets' / '주인공_도트'
    target.mkdir(exist_ok=True)
    for index in range(5):
        image = sheet(index)
        image.save(target / f'hero_w{index}.png')
        if index == 2:
            echo(image).save(target / 'hero_echo.png')
        print('saved', f'hero_w{index}.png')


if __name__ == '__main__':
    main()
