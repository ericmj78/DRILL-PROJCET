"""1스테이지 배경을 이미지 없이 4px 도트로 찍는다 (독 웅덩이 poison_fx.py와 같은 화풍).

층마다 가로 560 × 세로 100 도트(2240 × 400px) 텍스처를 처음 한 번 만들고 4배로 키워 그린다.
한 층의 구성 (월드 x):
- 아치 구역 셋: 왼쪽 60~570, 가운데 670~1570, 오른쪽 1670~2180. 안쪽 벽은 한 단 어둡다.
- 횃불 기둥 둘: 620, 1620. 기둥 주변 벽이 횃불빛으로 따뜻하게 물든다. 불꽃은 매 프레임 도트로 일렁인다.
- 쇠창살 창문 넷: 왼쪽·오른쪽 구역에 두 개씩.
- 바닥 턱과 그 아래 어두운 층. 구덩이(stage.pits) 구간은 턱이 끊긴다.
- 조각상(stage.web_beams) 아래에는 받침 돌을 찍는다.
맨 위층은 위로 천장 돌을 더 찍어 빈 화면이 보이지 않게 한다.
"""
from math import hypot, sin

from pico2d import pico2d as canvas
import sdl2

from poison_fx import _rand, make_texture

DOT = 4
COLS, ROWS = 560, 100
BELOW = 23                 # 바닥선 아래 도트 행 (92px)
CEILING = 48               # 맨 위층 위로 더 찍는 천장 행
BAYS = ((60, 570), (670, 1570), (1670, 2180))
PILLARS = (620, 1620)
PILLAR_HALF = 50
WINDOWS = (200, 430, 1810, 2040)
WINDOW_HALF = 62
TORCH_HEIGHT = 170         # 바닥에서 횃불 받침까지

WALL = ((50, 56, 84), (44, 49, 74), (38, 42, 64), (58, 64, 94))
MORTAR = (24, 26, 40)
ARCH, ARCH_HI = (76, 82, 112), (96, 102, 134)
PILLAR, PILLAR_HI, PILLAR_DARK = (82, 84, 104), (104, 104, 124), (56, 58, 76)
LEDGE, LEDGE_HI, LEDGE_LINE = (84, 90, 118), (124, 130, 156), (40, 44, 62)
UNDER = (14, 17, 30)
WINDOW_IN, BAR, BAR_HI = (9, 11, 20), (66, 50, 40), (118, 86, 56)
IRON = (52, 46, 46)
MOSS = (62, 92, 52)


def _wall(gx, r, recess):
    """벽돌 한 도트. 벽돌은 10 × 5 도트, 단마다 반 칸씩 엇갈린다."""
    course, inside = divmod(r, 5)
    block, col = divmod(gx + (5 if course % 2 else 0), 10)
    if inside == 4 or col == 9:
        color = MORTAR
    else:
        tint = _rand(block, course, 3)
        color = WALL[0] if tint < 0.4 else WALL[1] if tint < 0.75 else WALL[2] if tint < 0.93 else WALL[3]
        if inside == 0 and col < 8 and tint < 0.75:
            color = WALL[3]                       # 벽돌 윗변 하이라이트
        elif _rand(gx, r, 7) > 0.965:
            color = WALL[2]                       # 잔금
        elif r < 12 and _rand(gx, r, 8) > 0.92:
            color = MOSS                          # 바닥 가까이 낀 이끼
    if recess:
        color = tuple(int(v * 0.78) for v in color)
    return color


def _arch_top(x, left, right):
    """아치 구역의 안쪽 높이 (바닥에서 px)."""
    center, half = (left + right) / 2, (right - left) / 2
    t = min(1.0, abs(x - center) / half)
    return 200 + 70 * (1 - t * t) ** 0.5


def _pixel(gx, r, stage, floor):
    """한 층에서 도트 (gx 열, 바닥선 위 r 행)의 색. r < 0이면 바닥선 아래."""
    x, y = gx * DOT + 2, r * DOT + 2          # 월드 x, 바닥에서 높이(px)
    pit = any(f == floor and left < x < right for f, left, right in stage.pits)
    if r < 0:   # 바닥 턱과 그 아래
        if pit:
            return (6, 6, 14)
        if r >= -3:
            if r == -1:
                return LEDGE_HI
            return LEDGE_LINE if gx % 24 == 0 else LEDGE
        if (gx % 35) in (16, 17, 18) and r >= -8 + abs(gx % 35 - 17):
            return IRON                            # 턱 아래 쇠 받침
        shade = max(0.45, 1 + r / 30)
        return tuple(int(v * shade) for v in UNDER)

    for beam in stage.web_beams:   # 조각상 받침
        if beam.floor != floor:
            continue
        scale = 0.85 if floor == 1 else 1.0
        width = (beam.right - beam.left) * scale
        center = (beam.left + beam.right) / 2
        top = beam.underside
        if top - 10 <= y < top and abs(x - center) <= width / 2:
            return LEDGE_HI if y >= top - 4 else LEDGE
        taper = (top - 10 - y) * 0.9
        if top - 34 <= y < top - 10 and abs(x - center) <= width / 2 - 8 - taper:
            return PILLAR_DARK if abs(x - center) > width / 2 - 14 - taper else PILLAR

    for center in PILLARS:   # 횃불 기둥
        dx = abs(x - center)
        wide = 8 if y < 14 or 236 <= y < 252 else 0   # 주춧돌과 기둥머리는 넓다
        if dx <= PILLAR_HALF + wide and y < 252:
            if y < 14 or 236 <= y < 252:
                return PILLAR_HI if y in (10, 11, 12, 13, 248, 249, 250, 251) or (y // 4) % 4 == 3 else PILLAR
            course = int(y // 28)
            joint = (y % 28) < 4 or (dx > 24 and (int(x - center + 100) // 25 + course) % 2 == 0 and abs(dx - 25) < 3)
            if joint:
                return PILLAR_DARK
            if dx > PILLAR_HALF - 8:
                return PILLAR_DARK                 # 기둥 가장자리 그늘
            return PILLAR_HI if _rand(gx, r, 12) > 0.9 else PILLAR
        if abs(y - TORCH_HEIGHT) < 6 and dx < 10:
            return IRON                            # 횃불 받침

    for left, right in BAYS:
        if not left <= x <= right:
            continue
        top = _arch_top(x, left, right)
        if y < top:
            for center in WINDOWS:   # 쇠창살 창문
                dx = abs(x - center)
                window_top = 100 + 40 * max(0.0, 1 - (dx / WINDOW_HALF) ** 2) ** 0.5
                if dx <= WINDOW_HALF + 8 and 0 <= y < window_top + 8:
                    if dx > WINDOW_HALF or y >= window_top or y < 8:
                        return ARCH_HI if y < 8 or y >= window_top + 4 else ARCH   # 창틀
                    if (int(x - center + WINDOW_HALF) % 22) < 4 or 62 <= y < 66:
                        return BAR_HI if (int(x - center + WINDOW_HALF) % 22) < 2 else BAR
                    glow = 1 + 0.6 * (y / 140)    # 위로 갈수록 희미한 달빛
                    return tuple(int(v * glow) for v in WINDOW_IN)
            return _wall(gx, r, recess=True)
        if y < top + 14:
            stone = int((x - left) // 28)
            return ARCH_HI if y >= top + 10 else MORTAR if int(x - left) % 28 < 3 else ARCH
        break
    return _wall(gx, r, recess=False)


def _light(color, gx, r):
    """횃불빛과 위쪽 그늘을 입힌다."""
    x, y = gx * DOT, r * DOT
    warm = 0.0
    for center in PILLARS:
        d = hypot(x - center, (y - TORCH_HEIGHT - 20) * 1.3)
        warm = max(warm, max(0.0, 1 - d / 300) ** 2)
    shade = 1.0 if y < 240 else max(0.6, 1 - (y - 240) / 400)
    red, green, blue = color
    return (min(255, int(red * shade + warm * 120)), min(255, int(green * shade + warm * 58)),
            max(0, int(blue * shade - warm * 6)))


def _bake(stage, floor, top_floor):
    rows = ROWS + (CEILING if top_floor else 0)
    pixels = bytearray(COLS * rows * 4)
    for row in range(rows):
        r = rows - 1 - row - BELOW               # 바닥선 위 행
        for gx in range(COLS):
            if r >= ROWS - BELOW:   # 맨 위층 천장: 큰 돌이 위로 갈수록 어둠에 묻힌다
                fade = max(0.15, 1 - (r - (ROWS - BELOW)) / CEILING)
                color = tuple(int(v * 0.7 * fade) for v in _wall(gx // 2, r // 2, False))
            else:
                color = _pixel(gx, r, stage, floor)
                if r >= 0:
                    color = _light(color, gx, r)
            offset = (row * COLS + gx) * 4
            alpha = 255
            if 0 <= r < ROWS - BELOW:
                x, y = gx * DOT + 2, r * DOT + 2
                on_support = False
                for beam in stage.web_beams:
                    if beam.floor != floor or floor in (0, 1):
                        continue
                    width = (beam.right - beam.left) * (0.85 if floor == 1 else 1.0)
                    center = (beam.left + beam.right) / 2
                    top = beam.underside
                    if top - 10 <= y < top and abs(x - center) <= width / 2:
                        on_support = True
                    taper = (top - 10 - y) * 0.9
                    if top - 34 <= y < top - 10 and abs(x - center) <= width / 2 - 8 - taper:
                        on_support = True
                if not on_support:
                    alpha = 0
            pixels[offset:offset + 4] = bytes((*color, alpha))
    return make_texture(pixels, COLS, rows), rows


class PixelBackdrop:
    def __init__(self):
        self.floors = {}   # 스테이지 → [(텍스처, 행 수)]

    def draw(self, stage, floor_y, camera_x, time):
        if stage not in self.floors:
            self.floors[stage] = [_bake(stage, floor, floor == stage.floors - 1)
                                  for floor in range(stage.floors)]
        height = canvas.get_canvas_height()
        for (texture, rows), y in zip(self.floors[stage], floor_y):
            top = y - BELOW * DOT + rows * DOT
            rect = sdl2.SDL_Rect(int(-camera_x), int(height - top), COLS * DOT, rows * DOT)
            sdl2.SDL_RenderCopy(canvas.renderer, texture, None, rect)
        self._flames(floor_y, camera_x, time)

    @staticmethod
    def _flames(floor_y, camera_x, time):
        """횃불 불꽃: 도트 기둥이 들쭉날쭉 타오르고 불똥이 튄다."""
        height = canvas.get_canvas_height()
        for y in floor_y:
            for center in PILLARS:
                base_x = int((center - camera_x) // 1)
                base_y = y + TORCH_HEIGHT + 4
                for column in range(-2, 3):
                    flick = sin(time * 13 + column * 1.7 + center) + sin(time * 7.3 - column)
                    tall = 4 - abs(column) + int(flick * 0.8 + 1)
                    for level in range(max(1, tall)):
                        heat = level / max(1, tall)
                        color = ((255, 246, 190) if heat < 0.25 and abs(column) < 1 else
                                 (255, 196, 72) if heat < 0.6 else (232, 96, 36))
                        rect = sdl2.SDL_Rect(base_x + column * DOT - 2, int(height - base_y - (level + 1) * DOT),
                                             DOT, DOT)
                        sdl2.SDL_SetRenderDrawColor(canvas.renderer, *color, 255)
                        sdl2.SDL_RenderFillRect(canvas.renderer, rect)
                spark = (time * 1.6 + center * 0.01) % 1
                sx = base_x + int(sin(time * 3 + center) * 6)
                sdl2.SDL_SetRenderDrawColor(canvas.renderer, 255, 180, 80, int(255 * (1 - spark)))
                sdl2.SDL_RenderFillRect(canvas.renderer, sdl2.SDL_Rect(sx, int(height - base_y - 24 - spark * 40), DOT, DOT))
