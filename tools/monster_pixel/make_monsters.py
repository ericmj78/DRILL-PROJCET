"""사용자가 준 도트 몬스터(거미, 외눈 유령)로 동작 시트를 만든다: python tools/monster_pixel/make_monsters.py

원본은 왼쪽을 본다 (게임에서 오른쪽을 볼 때 뒤집는다). 그림 한 칸 = 게임 화면 1px.
원본 픽셀은 돌리거나 늘리지 않고 줄·덩어리 단위로 옮겨서 선이 깨지지 않게 한다.

결과: assets/몬스터_도트/
  spider.png, spider_echo.png    0줄 걷기 8 · 1줄 공격 8 (준비 4 + 물기 4) · 2줄 대기 4
  watcher.png, watcher_echo.png  0줄 떠다니기 16 · 1줄 공격 8 (준비 4 + 덮치기 4)
  칸 크기와 발밑(기준선) 위치는 monster_sheets.json에 적는다.
"""
import json
import math
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
TARGET = HERE.parent.parent / 'assets' / '몬스터_도트'


def load(name):
    return Image.open(HERE / f'{name}_source.png').convert('RGBA')


def blank(image):
    return Image.new('RGBA', image.size)


def rows_map(image, mapping):
    """mapping(x, y) → (새 x, 새 y) 또는 None. 앞에서부터 찍어 나중 픽셀이 위에 온다."""
    out = blank(image)
    src, o = image.load(), out.load()
    w, h = image.size
    for y in range(h):
        for x in range(w):
            c = src[x, y]
            if not c[3]:
                continue
            target = mapping(x, y)
            if target and 0 <= target[0] < w and 0 <= target[1] < h:
                o[target] = c
    return out


def components(image, top):
    """top 줄 아래에서 이어진 픽셀 덩어리(다리 끝)들. 왼쪽부터 정렬."""
    px = image.load()
    w, h = image.size
    seen, groups = set(), []
    for y in range(top, h):
        for x in range(w):
            if px[x, y][3] and (x, y) not in seen:
                stack, group = [(x, y)], []
                while stack:
                    p = stack.pop()
                    if p in seen or not (0 <= p[0] < w and top <= p[1] < h) or not px[p][3]:
                        continue
                    seen.add(p)
                    group.append(p)
                    stack += [(p[0] + dx, p[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
                if len(group) > 6:
                    groups.append(group)
    return sorted(groups, key=lambda g: sum(p[0] for p in g) / len(g))


# ---------------------------------------------------------------- 거미

SPIDER_LEGS_TOP = 124     # 이 줄 아래의 다리 끝 덩어리를 따로 움직인다
SPIDER_FEET = 142
SPIDER_HEAD_X = 46        # 이 칸 왼쪽이 머리와 앞다리


def spider_frames():
    src = load('spider')
    legs = components(src, SPIDER_LEGS_TOP)
    leg_of = {p: i for i, group in enumerate(legs) for p in group}
    px = src.load()
    body = blank(src)
    b = body.load()
    for y in range(src.height):
        for x in range(src.width):
            if px[x, y][3] and (x, y) not in leg_of:
                b[x, y] = px[x, y]

    def compose(bob, leg_moves, head_lift=0, head_dx=0, lunge=0):
        """leg_moves[i] = (발끝 밀기, 들기). head_*: 머리 쪽(왼쪽)만 들고 밀기."""
        def body_map(x, y):
            dy = bob
            dx = lunge
            if x < SPIDER_HEAD_X:   # 머리 쪽은 왼쪽으로 갈수록 더 든다
                k = (SPIDER_HEAD_X - x) / SPIDER_HEAD_X
                dy -= round(head_lift * k)
                dx += head_dx   # 머리는 한 덩어리로 옮겨 빈틈이 생기지 않게 한다
            return x + dx, y + dy

        out = rows_map(body, body_map)
        o = out.load()
        for i, group in enumerate(legs):
            shear, lift = leg_moves[i]
            front = sum(p[0] for p in group) / len(group) < SPIDER_HEAD_X
            for x, y in group:
                t = (y - SPIDER_LEGS_TOP) / (SPIDER_FEET - SPIDER_LEGS_TOP)
                nx = x + round(shear * t) + lunge
                ny = y - round(lift * t) + (round(bob * (1 - t)))
                if front:
                    ny -= round(head_lift * 0.6 * t)
                    nx += round(head_dx * 0.5)
                if 0 <= nx < src.width and 0 <= ny < src.height:
                    o[nx, ny] = px[x, y]
        return out

    walk = []
    for i in range(8):
        p = 2 * math.pi * i / 8
        moves = []
        for leg in range(len(legs)):
            phase = p + (math.pi if leg % 2 else 0)
            moves.append((round(-3 * math.sin(phase)), round(2 * max(0.0, math.cos(phase)))))
        walk.append(compose(1 if i % 4 in (1, 2) else 0, moves))

    still = [(0, 0)] * len(legs)
    attack = []
    for i in range(4):   # 준비: 머리와 앞다리를 쳐들며 뒤로 물러난다
        t = (i + 1) / 4
        attack.append(compose(0, still, head_lift=round(6 * t), head_dx=round(2 * t), lunge=round(2 * t)))
    for i, (lift, dx, lunge) in enumerate(((2, -1, -6), (-1, -2, -8), (0, -1, -4), (1, 0, -1))):
        attack.append(compose(1 if i == 1 else 0, still, head_lift=lift, head_dx=dx, lunge=lunge))

    idle = []
    for i in range(4):
        breath = (0, 1, 1, 0)[i]
        moves = [(0, 0)] * len(legs)
        idle.append(compose(0, moves, head_lift=0) if not breath else
                    rows_map(compose(0, moves), lambda x, y: (x, y + (1 if y < 106 and x >= SPIDER_HEAD_X else 0))))
    return [walk, attack, idle], src.size


# ---------------------------------------------------------------- 외눈 유령

WATCHER_TENTACLE_TOP = 104
WATCHER_BOTTOM = 146
EYE = (36, 64, 76, 94)        # 눈 x0, x1, y0, y1


def is_eye(c):
    r, g, b, a = c
    return a and r > 180 and g > 100 and b < 130


def watcher_frames():
    src = load('watcher')
    px = src.load()
    lid = (92, 46, 104, 255)

    def compose(phase, bob, amp, lean=0, blink=False, glow=0.0):
        def mapping(x, y):
            dx = lean
            if y >= WATCHER_TENTACLE_TOP:   # 촉수: 아래로 갈수록 크게 물결치고 뒤로 처진다
                depth = (y - WATCHER_TENTACLE_TOP) / (WATCHER_BOTTOM - WATCHER_TENTACLE_TOP)
                dx += round(amp * depth ** 1.3 * math.sin(phase - 3.0 * depth)) - round(lean * 0.8 * depth)
            elif y < 62:                    # 두건 끝 자락
                depth = (62 - y) / 16
                dx += round(1.2 * depth * math.sin(phase + 1.0))
            return x + dx, y + bob

        out = rows_map(src, mapping)
        o = out.load()
        if blink or glow:
            for y in range(out.height):
                for x in range(out.width):
                    c = o[x, y]
                    if not is_eye(c):
                        continue
                    if blink and abs(y - (EYE[2] + EYE[3]) // 2 - bob) > 0:
                        o[x, y] = lid
                    elif glow:
                        o[x, y] = (255, min(255, int(c[1] + 70 * glow)), min(255, int(c[2] + 120 * glow)), 255)
        return out

    float_frames = [compose(2 * math.pi * i / 16, round(2 * math.sin(2 * math.pi * i / 16)), 3.0,
                            blink=i == 11) for i in range(16)]
    attack = []
    for i in range(4):   # 준비: 뒤로 물러나며 눈을 번뜩인다
        t = (i + 1) / 4
        attack.append(compose(i, -round(2 * t), 2.0, lean=round(4 * t), glow=t))
    for i, lean in enumerate((-8, -10, -5, -1)):   # 덮치기: 앞으로 튀어나가고 촉수가 뒤로 끌린다
        attack.append(compose(4 + i, 1 if i < 2 else 0, 4.0, lean=lean, glow=0.6 if i < 2 else 0.0))
    return [float_frames, attack], src.size


# ---------------------------------------------------------------- 시트

def echo(image):
    """분신: 밝기를 은빛·청록으로 바꾸고 조금 투명하게 (주인공 분신과 같은 색)."""
    out = image.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a:
                light = (r * 0.3 + g * 0.59 + b * 0.11) / 255
                px[x, y] = (int(70 + 170 * light), int(96 + 150 * light), int(130 + 125 * light), int(a * 0.88))
    return out


def save(name, rows, crop):
    """rows: 동작별 프레임 목록. crop: 원본에서 잘라 쓸 (x0, y0, x1, y1)."""
    w, h = crop[2] - crop[0], crop[3] - crop[1]
    sheet = Image.new('RGBA', (w * max(len(r) for r in rows), h * len(rows)))
    for r, frames in enumerate(rows):
        for c, f in enumerate(frames):
            sheet.alpha_composite(f.crop(crop), (w * c, h * r))
    sheet.save(TARGET / f'{name}.png')
    echo(sheet).save(TARGET / f'{name}_echo.png')
    return w, h


def main():
    TARGET.mkdir(exist_ok=True)
    meta = {}
    rows, _ = spider_frames()
    crop = (0, 66, 112, 150)
    w, h = save('spider', rows, crop)
    meta['crawler'] = {'sheet': 'spider', 'size': [w, h], 'rows': [len(r) for r in rows],
                       'feet': SPIDER_FEET + 1 - crop[1], 'center': 52 - crop[0]}
    rows, _ = watcher_frames()
    crop = (16, 30, 112, 154)
    w, h = save('watcher', rows, crop)
    meta['watcher'] = {'sheet': 'watcher', 'size': [w, h], 'rows': [len(r) for r in rows],
                       'feet': WATCHER_BOTTOM + 1 - crop[1], 'center': 62 - crop[0]}
    (TARGET / 'monster_sheets.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')
    print('saved', meta)


if __name__ == '__main__':
    main()
