"""독 웅덩이를 통째로 4px 도트로 찍는다. 이미지 파일은 쓰지 않는다.

웅덩이(draw_pool): 돌 테두리·바닥, 쉬어 가는 돌판, 독물을 도트 한 점 = 텍셀 하나로 찍은
작은 텍스처 24장을 처음 한 번 만들어 두고, 4배로 키워(최근접 보간) 번갈아 보여 준다.
- 독물: 깊을수록 어두운 층에 빛 무늬가 일렁이고, 수면 물결 마루가 흘러간다.
- 돌: 블록마다 색이 조금씩 다르고, 줄눈·윗면 하이라이트·금·이끼가 있다.

그 위에 매 프레임 찍는 도트(draw):
- 거품: 바닥에서 올라와 커지다가 수면에서 터지며 물방울이 튄다.
- 독기: 수면 위로 연기 도트가 피어오르다 흐려진다.
- 반응: 독 안에 서 있으면 발밑에서 물결이 퍼지고, 뛰었다 떨어지면 물방울이 튄다.
같은 색의 도트를 모아 SDL_RenderFillRects로 한 번에 그린다.
"""
from math import pi, sin

import sdl2
from pico2d import pico2d as canvas

DOT = 4
SURFACE = 8           # 바닥선에서 독 수면까지 내려간 거리 (도트 2칸)
FRAMES, FPS = 24, 8   # 웅덩이 애니메이션 한 바퀴 3초
RIM = 11              # 양옆 돌 테두리 폭 (도트)
LIP = 2               # 바닥선 위로 올라오는 도트 행 (쉬는 돌판 윗부분)
ROWS = 26             # 웅덩이 텍스처 높이 (도트). 바닥선 아래로 96px
BOTTOM = 2            # 바닥 돌 행
LIQUID = [(120, 176, 48), (60, 90, 26), (46, 70, 21), (36, 55, 17),
          (28, 43, 14), (22, 34, 12), (17, 26, 10)]   # 수면 → 깊은 곳
GLOW_LINE, GLOW_HOT = (98, 128, 38), (146, 182, 60)  # 독물 속 일렁이는 빛 무늬
CREST, FOAM = (176, 226, 84), (226, 250, 160)
STONE_HI, STONE_LIGHT = (128, 134, 156), (96, 102, 126)
STONE, STONE_MID = (74, 79, 102), (62, 66, 88)
STONE_DARK, MORTAR = (44, 46, 64), (26, 27, 40)
MOSS, MOSS_DARK = (88, 132, 52), (58, 92, 38)
LIME = (176, 255, 92)
GREEN = (104, 214, 58)
DARK = (40, 112, 36)
GLOW = (232, 255, 170)
SPLASH_LIFE = 0.6


def _rand(*keys):
    """keys로 정해지는 0~1 사이 값. 프레임마다 같은 도트가 같은 자리에 나오도록 상태 없이 쓴다."""
    h = 2166136261
    for key in keys:
        h = ((h ^ (int(key) & 0xffffffff)) * 16777619) & 0xffffffff
    h ^= h >> 13
    h = (h * 1274126177) & 0xffffffff
    return (h ^ (h >> 16)) / 0xffffffff


def make_texture(pixels, width, height):
    """RGBA 바이트(도트 한 점 = 텍셀 하나)로 최근접 보간 텍스처를 만든다. 키우면 도트가 또렷하다."""
    texture = sdl2.SDL_CreateTexture(canvas.renderer, sdl2.SDL_PIXELFORMAT_ABGR8888,
                                     sdl2.SDL_TEXTUREACCESS_STATIC, width, height)
    sdl2.SDL_UpdateTexture(texture, None, bytes(pixels), width * 4)
    sdl2.SDL_SetTextureBlendMode(texture, sdl2.SDL_BLENDMODE_BLEND)
    sdl2.SDL_SetTextureScaleMode(texture, sdl2.SDL_ScaleModeNearest)
    return texture


def _stone(gx, row, tint_key=0):
    """돌 블록 무늬. gx는 월드 기준 도트 열, row는 돌 윗면부터 센 행."""
    course, inside = divmod(row, 3)
    shift = 3 if course % 2 else 0
    block, col = divmod(gx + shift, 6)
    if inside == 2 or col == 5:
        return MORTAR
    if row == 0:
        return MOSS if _rand(gx, 21, tint_key) > 0.82 else STONE_HI
    if _rand(gx, row, 5, tint_key) > 0.94:
        return STONE_DARK                       # 금
    if inside == 0 and col < 4:
        return STONE_LIGHT                      # 블록 윗부분 하이라이트
    if col == 4:
        return STONE_MID                        # 블록 오른쪽 그늘
    return STONE if _rand(block, course, 11, tint_key) > 0.35 else STONE_MID


DEPTH_BAND = (0, 1, 2, 3, 3, 4, 4, 5, 5, 5)   # 화면에 보이는 위쪽 14줄 안에서 어두워진다


def _liquid(tx, depth, t):
    """독물 한 도트. depth는 수면에서 내려간 행, t는 0~2π (한 바퀴에 딱 맞게 반복)."""
    if depth == 0:
        wave = sin(tx * 0.21 + t) + 0.5 * sin(tx * 0.47 - 2 * t)
        return FOAM if wave > 1.25 else CREST if wave > 0.75 else LIQUID[0]
    band = DEPTH_BAND[depth] if depth < len(DEPTH_BAND) else 6
    if depth in (3, 5, 7) and (tx * 3 + depth) % 4 == 0:
        band -= 1                               # 층 경계를 성기게 섞는다
    if depth >= 2:
        glow = (sin(tx * 0.23 + depth * 0.45 + t) + sin(tx * 0.09 - depth * 0.7 + 2 * t)
                + 0.6 * sin(tx * 0.05 + depth * 0.3 - t))
        if abs(glow) < 0.09:
            return GLOW_HOT if depth < 6 else GLOW_LINE   # 일렁이는 빛 무늬
        if abs(glow) < 0.2:
            return GLOW_LINE if depth < 8 else LIQUID[3]
    return LIQUID[max(1, band)]


def _bake(floor, zones, rests, draw_stone=True):
    """한 층의 독 웅덩이 텍스처 FRAMES장을 만든다."""
    left = min(zone[1] for zone in zones) - RIM * DOT
    right = max(zone[2] for zone in zones) + RIM * DOT
    width = (right - left) // DOT
    origin = left // DOT
    slabs = [(l // DOT - origin, r // DOT - origin) for f, l, r in rests if f == floor]
    surface = LIP + SURFACE // DOT

    def static(tx, ty):
        gx = origin + tx
        for l, r in slabs:   # 쉬어 가는 돌판
            if l <= tx < r and LIP - 2 <= ty <= LIP + 3:
                if not draw_stone:
                    return None
                if ty == LIP + 3:
                    return STONE_DARK
                if tx in (l, r - 1) and ty > LIP - 2:
                    return STONE_MID
                return _stone(gx, ty - (LIP - 2), 1)
        if tx < RIM or tx >= width - RIM:
            if not draw_stone:
                return None
            if ty < LIP:
                return None
            if tx in (RIM - 1, width - RIM):
                return STONE_DARK if ty > LIP else STONE_MID   # 안쪽 벽면 그늘
            return _stone(gx, ty - LIP)
        if ty >= ROWS - BOTTOM:
            return _stone(gx, ty - (ROWS - BOTTOM) + 1) if draw_stone else None
        if ty == ROWS - BOTTOM - 1 and _rand(gx, 31) > 0.7:
            return MOSS_DARK if draw_stone else 'liquid'
        return 'liquid' if ty >= surface - 1 else None

    layout = [[static(tx, ty) for tx in range(width)] for ty in range(ROWS)]
    frames = []
    for index in range(FRAMES):
        t = 2 * pi * index / FRAMES
        pixels = bytearray(width * ROWS * 4)
        for ty, row in enumerate(layout):
            for tx, color in enumerate(row):
                if color == 'liquid':
                    if ty == surface - 1:   # 물결 마루만 한 칸 솟는다
                        wave = sin(tx * 0.21 + t) + 0.5 * sin(tx * 0.47 - 2 * t)
                        color = CREST if wave > 0.95 else None
                    else:
                        color = _liquid(tx, ty - surface, t)
                if color is not None:
                    offset = (ty * width + tx) * 4
                    pixels[offset:offset + 4] = bytes((*color, 255))
        frames.append(make_texture(pixels, width, ROWS))
    return frames, left, width


class PoisonFx:
    def __init__(self):
        self.splashes = []   # [x, 층, 지난 시간]
        self.heights = {}    # 액터별 직전 높이. 착지 순간을 찾는다.
        self.time = None
        self.pools = {}      # (층, 웅덩이, 돌판) → 미리 찍어 둔 텍스처

    def draw_pool(self, zones, rests, floor_y, camera_x, time, draw_stone=True, cut=0):
        """독 웅덩이 전체(돌 테두리·돌판·독물)를 도트 텍스처로 그린다. cut(px)만큼 아래쪽을 잘라
        웅덩이를 낮춰 그려도 바닥 두께 아래(아래층 화면)로 비어져 나오지 않게 한다."""
        for floor in sorted({zone[0] for zone in zones}):
            mine = tuple(zone for zone in zones if zone[0] == floor)
            key = (floor, mine, tuple(rests), draw_stone)
            if key not in self.pools:
                self.pools[key] = _bake(floor, mine, rests, draw_stone)
            frames, left, width = self.pools[key]
            top = floor_y[floor] + LIP * DOT
            rows = ROWS - -(-cut // DOT)
            rect = sdl2.SDL_Rect(int(left - camera_x), int(canvas.get_canvas_height() - top),
                                 width * DOT, rows * DOT)
            sdl2.SDL_RenderCopy(canvas.renderer, frames[int(time * FPS) % FRAMES],
                                sdl2.SDL_Rect(0, 0, width, rows), rect)

    def draw(self, zones, floor_y, camera_x, time, actors):
        if self.time is None or time < self.time:   # 새 스테이지
            self.splashes, self.heights = [], {}
            self.time = time
        dt = min(0.1, time - self.time)
        self.time = time
        dots = {}

        def dot(x, y, color, alpha=255, size=1):
            # 월드 좌표 4px 격자에 맞춰 찍어 카메라가 움직여도 도트가 흔들리지 않는다.
            gx = int(x // DOT) * DOT
            gy = int(y // DOT) * DOT
            dots.setdefault((*color, alpha), []).append((gx - camera_x, gy, DOT * size))

        for floor, left, right in zones:
            surface = floor_y[floor] - SURFACE
            self._bubbles(dot, floor, left, right, surface, time)
            self._mist(dot, floor, left, right, surface, time)

        self._react(dot, zones, floor_y, time, dt, actors)
        self._flush(dots)

    @staticmethod
    def _bubbles(dot, floor, left, right, surface, time):
        width = right - left
        for index in range(max(2, width // 40)):
            period = 1.4 + _rand(floor, left, index, 1) * 1.6
            phase = time + _rand(floor, left, index, 2) * period
            cycle, local = divmod(phase, period)
            t = local / period
            x = left + 12 + _rand(floor, left, index, int(cycle)) * (width - 24)
            depth = 40 + _rand(floor, index, int(cycle), 3) * 30
            if t < 0.75:   # 바닥에서 흔들리며 올라오고, 수면에 가까울수록 커진다
                rise = t / 0.75
                y = surface - depth * (1 - rise)
                x += sin(time * 8 + index) * 3
                if rise < 0.5:
                    dot(x, y, GREEN, 200)
                else:
                    for dx, dy in ((0, 0), (DOT, 0), (0, DOT), (DOT, DOT)):
                        dot(x + dx, y + dy, GREEN, 210)
                    dot(x + DOT, y + DOT, GLOW, 240)   # 하이라이트
            else:          # 수면에서 터지며 물방울 여섯 개가 튄다
                age = (t - 0.75) * period
                fade = 1 - (t - 0.75) / 0.25
                for side in (-1, 1):
                    for speed, up in ((30, 170), (65, 130), (100, 80)):
                        y = surface + DOT + up * age - 500 * age * age
                        if y >= surface:
                            dot(x + side * speed * age, y, LIME, int(240 * fade))
                dot(x, surface + DOT, GLOW, int(220 * fade), 2)

    @staticmethod
    def _mist(dot, floor, left, right, surface, time):
        width = right - left
        for index in range(max(2, width // 45)):
            period = 2.0 + _rand(floor, left, index, 7) * 1.5
            phase = time + _rand(floor, left, index, 8) * period
            cycle, local = divmod(phase, period)
            t = local / period
            x = left + 6 + _rand(floor, left, index, int(cycle), 9) * (width - 12)
            alpha = int(150 * sin(t * 3.1416))
            y = surface + DOT * 2 + t * 60
            x += sin(time * 1.3 + index) * 8
            dot(x, y, LIME, alpha)
            if t < 0.5:   # 피어오르기 시작할 때는 두 도트짜리 김
                dot(x + DOT, y - DOT, GREEN, alpha // 2)

    def _react(self, dot, zones, floor_y, time, dt, actors):
        for actor in actors:
            if actor.elevator_target is not None:
                continue
            zone = next((zone for zone in zones if zone[0] == actor.floor and zone[1] <= actor.x <= zone[2]), None)
            height = actor.jump_height
            before = self.heights.get(id(actor))
            self.heights[id(actor)] = height
            if zone is None:
                continue
            surface = floor_y[actor.floor] - SURFACE
            if before is not None and before >= 12 > height:
                self.splashes.append([actor.x, actor.floor, 0.0])
            if height < 12:   # 발밑에서 퍼지는 물결
                for ring in range(3):
                    radius = (time * 60 + ring * 22) % 66
                    alpha = int(230 * (1 - radius / 66))
                    for side in (-1, 1):
                        x = actor.x + side * (12 + radius)
                        if zone[1] <= x <= zone[2]:
                            dot(x, surface + DOT, GLOW, alpha)
                            dot(x - side * DOT, surface, LIME, alpha // 2)

        for splash in self.splashes:
            splash[2] += dt
        self.splashes = [splash for splash in self.splashes if splash[2] < SPLASH_LIFE]
        for x, floor, age in self.splashes:
            surface = floor_y[floor] - SURFACE
            fade = 1 - age / SPLASH_LIFE
            for index in range(8):
                vx = (_rand(x, index, 1) - 0.5) * 160
                vy = 110 + _rand(x, index, 2) * 90
                y = surface + DOT + vy * age - 520 * age * age
                if y >= surface:
                    dot(x + vx * age, y, LIME if index % 2 else GLOW, int(240 * fade))
            radius = 10 + age * 110   # 수면을 따라 크게 퍼지는 물결
            for side in (-1, 1):
                dot(x + side * radius, surface + DOT, GLOW, int(200 * fade))

    @staticmethod
    def _flush(dots):
        height = canvas.get_canvas_height()
        for (r, g, b, a), points in dots.items():
            if a <= 0:
                continue
            rects = (canvas.SDL_Rect * len(points))()
            for rect, (x, y, size) in zip(rects, points):
                rect.x, rect.y, rect.w, rect.h = int(x), int(height - y - size), size, size
            canvas.SDL_SetRenderDrawColor(canvas.renderer, r, g, b, a)
            canvas.SDL_RenderFillRects(canvas.renderer, rects, len(points))
