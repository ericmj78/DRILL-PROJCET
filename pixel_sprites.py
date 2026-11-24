"""1스테이지 장식물을 이미지 없이 4px 도트로 찍는다 (주인공 hero_sprite.py, 몬스터 monster_sprite.py).

몸을 머리·몸통·팔다리·망토·무기 같은 부품으로 나누고, 프레임마다 자세(관절 각도)를 정해
도트 격자(Grid)에 찍는다. 부품마다 빛 방향(왼쪽 위)에 따라 밝은 면·기본·그늘 세 단계로 칠하고,
마지막에 바깥 테두리를 한 도트 두께로 두른다. 만든 프레임은 텍스처로 캐시한다.

좌표는 도트 단위이고, 원점은 발밑 가운데, x는 바라보는 쪽(앞), y는 위다.
각도: 팔다리는 0이 아래, 양수가 앞으로 든다. 무기는 player_attack.py처럼 0이 위, 90이 앞이다.
"""
from math import atan2, cos, hypot, pi, sin

import sdl2
from pico2d import pico2d as canvas

from poison_fx import make_texture

DOT = 4
LIGHT = (-0.55, 0.83)   # 왼쪽 위에서 오는 빛

OUTLINE = (22, 16, 26)


class Grid:
    def __init__(self, width, height, origin_x):
        self.width, self.height, self.origin_x = width, height, origin_x
        self.cells = [[None] * width for _ in range(height)]

    def _paint(self, bounds, inside, colors):
        """bounds 안에서 inside(x, y)가 (거리 비율, 빛 쪽 정도)를 돌려주는 칸을 칠한다."""
        left, bottom, right, top = bounds
        base, shade, high = colors
        for gy in range(max(0, int(bottom) - 1), min(self.height, int(top) + 2)):
            for gx in range(max(0, int(left + self.origin_x) - 1), min(self.width, int(right + self.origin_x) + 2)):
                x, y = gx - self.origin_x + 0.5, gy + 0.5
                hit = inside(x, y)
                if hit is None:
                    continue
                if hit > 0.45 and high:
                    self.cells[gy][gx] = high
                elif hit < -0.35 and shade:
                    self.cells[gy][gx] = shade
                else:
                    self.cells[gy][gx] = base

    def capsule(self, a, b, radius, colors):
        (ax, ay), (bx, by) = a, b
        dx, dy = bx - ax, by - ay
        length = dx * dx + dy * dy or 1e-9

        def inside(x, y):
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length))
            vx, vy = x - (ax + dx * t), y - (ay + dy * t)
            d = hypot(vx, vy)
            if d > radius:
                return None
            return (vx * LIGHT[0] + vy * LIGHT[1]) / radius if d else 0.0

        self._paint((min(ax, bx) - radius, min(ay, by) - radius, max(ax, bx) + radius, max(ay, by) + radius),
                    inside, _tones(colors))

    def ellipse(self, center, rx, ry, colors):
        cx, cy = center

        def inside(x, y):
            u, v = (x - cx) / rx, (y - cy) / ry
            if u * u + v * v > 1:
                return None
            return u * LIGHT[0] + v * LIGHT[1]

        self._paint((cx - rx, cy - ry, cx + rx, cy + ry), inside, _tones(colors))

    def poly(self, points, colors):
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        span = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 or 1

        def inside(x, y):
            hit = False
            for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
                if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                    hit = not hit
            if not hit:
                return None
            return ((x - cx) * LIGHT[0] + (y - cy) * LIGHT[1]) / span

        self._paint((min(xs), min(ys), max(xs), max(ys)), inside, _tones(colors))

    def dot(self, x, y, color):
        gx, gy = int(x + self.origin_x), int(y)
        if 0 <= gx < self.width and 0 <= gy < self.height:
            self.cells[gy][gx] = color

    def outline(self, color=OUTLINE):
        filled = [[cell is not None for cell in row] for row in self.cells]
        for gy in range(self.height):
            for gx in range(self.width):
                if filled[gy][gx]:
                    continue
                if any(0 <= gx + dx < self.width and 0 <= gy + dy < self.height and filled[gy + dy][gx + dx]
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    self.cells[gy][gx] = color

    def texture(self):
        pixels = bytearray(self.width * self.height * 4)
        for gy, row in enumerate(self.cells):
            for gx, color in enumerate(row):
                if color is not None:
                    offset = ((self.height - 1 - gy) * self.width + gx) * 4
                    pixels[offset:offset + 4] = bytes((*color[:3], color[3] if len(color) > 3 else 255))
        return make_texture(pixels, self.width, self.height)


def _tones(colors):
    """색 하나면 그늘·밝은 면을 자동으로 만든다."""
    if isinstance(colors[0], int):
        base = colors
        return base, _scale(base, 0.72), _scale(base, 1.22)
    return colors


def _scale(color, k):
    return tuple(max(0, min(255, int(v * k))) for v in color[:3])


class PixelSprites:
    def __init__(self):
        self.cache = {}

    def _frame(self, key, build):
        if key not in self.cache:
            grid = build()
            self.cache[key] = (grid.texture(), grid.width, grid.height, grid.origin_x)
        return self.cache[key]

    def blit(self, frame, x, floor_y, facing, opacity=255, tint=(255, 255, 255)):
        texture, width, height, origin = frame
        height_px = height * DOT
        left = x - origin * DOT if facing >= 0 else x - (width - origin) * DOT
        rect = sdl2.SDL_Rect(int(round(left)), int(canvas.get_canvas_height() - floor_y - height_px),
                             width * DOT, height_px)
        sdl2.SDL_SetTextureAlphaMod(texture, opacity)
        sdl2.SDL_SetTextureColorMod(texture, *tint)
        sdl2.SDL_RenderCopyEx(canvas.renderer, texture, None, rect, 0, None,
                              sdl2.SDL_FLIP_HORIZONTAL if facing < 0 else sdl2.SDL_FLIP_NONE)
        sdl2.SDL_SetTextureColorMod(texture, 255, 255, 255)
        sdl2.SDL_SetTextureAlphaMod(texture, 255)


# ---------------------------------------------------------------- 1스테이지 장식물

STONE = ((104, 108, 130), (72, 76, 96), (140, 144, 164))
STONE_DARK = ((70, 74, 94), (50, 52, 70), (92, 96, 118))
IRON = ((78, 76, 86), (52, 50, 60), (124, 120, 130))
GOLD = ((226, 176, 84), (170, 124, 54), (252, 220, 140))
RUNE_ON = ((110, 240, 230), (60, 190, 190), (210, 255, 250))
WOOD = ((126, 88, 56), (90, 62, 40), (160, 116, 76))


def draw_lift():
    """승강기 발판: 나무판에 쇠 테두리와 금 장식."""
    grid = Grid(20, 6, 10)
    grid.poly([(-8.6, 0.6), (8.6, 0.6), (8.6, 3.4), (-8.6, 3.4)], WOOD)
    for x in range(-8, 9, 4):
        grid.dot(x, 2.0, WOOD[1])
    grid.capsule((-8.6, 3.6), (8.6, 3.6), 0.6, IRON)
    for x in (-8.0, 8.0):
        grid.dot(x, 2.0, GOLD[0])
    grid.outline()
    return grid


def draw_exit(frame):
    """출구: 돌 아치 안에서 청록 빛이 소용돌이친다. frame은 0~5."""
    grid = Grid(20, 28, 10)
    t = frame / 6 * 2 * pi
    for y in range(0, 26):
        for x10 in range(-60, 61, 5):
            x = x10 / 10
            top = 18 + 6 * max(0.0, 1 - (x / 7.0) ** 2) ** 0.5
            if abs(x) > 6.2 or y > top - 1.2:
                continue
            swirl = sin(hypot(x, (y - 11) * 0.8) * 0.9 - t + atan2(y - 11, x) * 2)
            color = RUNE_ON[2] if swirl > 0.7 else RUNE_ON[0] if swirl > -0.1 else RUNE_ON[1]
            grid.dot(x, y, color)
    for side in (-1, 1):
        grid.poly([(side * 6.6, 0), (side * 8.6, 0), (side * 8.6, 18), (side * 6.6, 18)], STONE)
    for index in range(13):   # 아치 돌
        a = pi * index / 12
        grid.capsule((cos(a) * 7.6, 18 + sin(a) * 7.0), (cos(a) * 7.6, 18 + sin(a) * 7.0), 1.1,
                     STONE if index % 2 else STONE_DARK)
    grid.outline()
    return grid


def _prop(self, key, build):
    return self._frame(('prop',) + key, build)


PixelSprites.prop = _prop
