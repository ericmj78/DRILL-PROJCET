"""도트 주인공(보라 망토) 시트를 그린다. 시트는 tools/hero_pixel/make_hero.py로 만든다.

assets/주인공_도트/hero_w{무기}.png: 한 칸 160 × 160, 그림 한 칸 = 화면 1px.
줄 순서는 대기 24, 걷기 8, 점프 8, 베기 10, 찌르기 10. 발밑은 122줄, 몸 가운데는 71칸.
걷기는 사용자가 그린 걷기 그림(hero_walk.png, tools/hero_pixel/make_walk.py)을 쓴다:
한 칸 128 × 128, 발밑 124줄, 몸 가운데 66칸. 이 그림에는 무기가 없다.
한손검(무기 2)과 분신은 PixelLab 시트(PixelLab/주인공/hero_{동작}_sheet.png, tools/hero_pixel/pixellab_hero_anims.py)를 쓴다:
동작마다 가로 9칸, 한 칸 160 × 160(찌르기·대시는 224 × 160), 발밑 156줄, 몸 가운데 86칸(대시 150칸).
1단 점프·2단 점프(공중제비)·대시는 tools/hero_pixel/pixellab_hero_moves.py로 만든다.
베기(A)는 attack 시트, 찌르기(S)는 thrust 시트.
"""
from pico2d import pico2d as canvas

from animation import draw_region
from world import DASH_TIME

SIZE, FEET, CENTER = 160, 122, 71
ROWS = {'idle': (0, 24), 'walk': (1, 8), 'jump': (2, 8), 'slash': (3, 10), 'thrust': (4, 10)}
IDLE_SECONDS = 2.88     # 대기 24프레임 × 0.12초
STRIDE = 88             # 걷기 한 바퀴(8프레임)에 걷는 거리
WALK_SIZE, WALK_FEET, WALK_CENTER = 128, 124, 66
SWORD = 2
SWORD_FRAMES, SWORD_FEET, SWORD_CENTER = 9, 156, 86
SWORD_SHEETS = ('idle', 'walk', 'jump', 'double_jump', 'dash', 'attack', 'thrust')
SWORD_CENTERS = {'dash': SWORD_CENTER + 64}   # 대시 시트는 뒤(왼쪽)에 효과 자리를 두고 캐릭터를 64 오른쪽에 그렸다
SWORD_ATTACK = {'slash': 'attack', 'thrust': 'thrust'}


class HeroSprite:
    def __init__(self, load):
        self.sheets = [load(f'주인공_도트/hero_w{index}.png') for index in range(5)]
        self.walk = load('주인공_도트/hero_walk.png')
        self.sword = {name: load(f'PixelLab/주인공/hero_{name}_sheet.png') for name in SWORD_SHEETS}
        self.sword_echo = {name: load(f'PixelLab/주인공/hero_{name}_echo.png') for name in SWORD_SHEETS}

    def draw(self, actor, floor_y, weapon_index, opacity, time, attack=None, echo=False):
        """attack: (종류, 진행도) 또는 None. echo면 은빛 분신 시트(한손검)를 쓴다."""
        if attack is not None:
            state, phase = attack
        elif actor.dash_time > 0:
            state, phase = 'dash', 1 - actor.dash_time / DASH_TIME
        elif actor.jump_time > 0:   # 2단 점프를 쓴 뒤의 점프는 공중제비 시트
            state, phase = 'double_jump' if actor.air_jumped else 'jump', actor.jump_time / actor.jump_duration
        elif actor.moving:
            state, phase = 'walk', (actor.walk_distance / STRIDE) % 1
        else:
            state, phase = 'idle', (time / IDLE_SECONDS) % 1
        if echo or weapon_index == SWORD:
            sheet = SWORD_ATTACK[state] if attack is not None else state
            image = (self.sword_echo if echo else self.sword)[sheet]
            count, row = SWORD_FRAMES, 0
            size, feet, center = SIZE, SWORD_FEET, SWORD_CENTERS.get(sheet, SWORD_CENTER)
            width = image.w // SWORD_FRAMES     # 찌르기 시트만 224로 넓다 (캐릭터 위치는 같음)
        elif state in ('walk', 'dash'):   # 옛 무기 시트에는 대시·2단 점프 그림이 없다
            image, count, row = self.walk, ROWS['walk'][1], 0
            size, feet, center = WALK_SIZE, WALK_FEET, WALK_CENTER
            width = size
        else:
            image = self.sheets[weapon_index]
            row, count = ROWS['jump' if state == 'double_jump' else state]
            size, feet, center = SIZE, FEET, CENTER
            width = size
        column = max(0, min(count - 1, int(phase * count)))
        flip = actor.facing < 0
        left = actor.x - (width - center if flip else center)
        canvas.SDL_SetTextureAlphaMod(image.texture, opacity)
        draw_region(image, (column * width, row * size, width, size), left, floor_y - (size - feet),
                    width, size, flip)
        canvas.SDL_SetTextureAlphaMod(image.texture, 255)
