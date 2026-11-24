import json
import sdl2
from copy import copy
from ctypes import byref, c_int
from math import cos, hypot, pi, sin
from os import environ
from pathlib import Path
from time import perf_counter

from pico2d import draw_line, draw_rectangle, load_font, load_image
from pico2d import pico2d as canvas

from animation import WalkCycle, draw_region
from asset_paths import asset_path
import boss_skills
import late_monster_motion
from monster_attack import attack_pose, draw_attack_effect, draw_posed, draw_sheet, load_attack_fx, skill_pose
from monster_walk import MONSTER_GAITS, MonsterWalk
import player_attack
from poison_fx import PoisonFx
import pixel_sprites
from pixel_sprites import PixelSprites
from hero_sprite import HeroSprite
import monster_sprite
from monster_sprite import MonsterSprite
from title_menu import CONTROLS, PAGE_TITLES
from stages import LEFT
from stages import BOSS_KINDS, ENEMY_KINDS, GATE_HALF_WIDTH, RIGHT, STAGES, STAGE_GROUPS, STAGE_TITLES, STEP, WEAPONS, stage_group_index
from stages import PLATE_RANGE, Point
from world import JUMP_DURATION, LIGHT_BELOW, POTION_GRAVITY, SPIDER_AIM_REACH, WATCH_RANGE, potion_launch


WIDTH, HEIGHT = 1120, 720
# 물약 슬라임이 이만큼 움직일 때마다 자국을 남기고, 자국은 이만큼 뒤 사라진다 (마지막 40% 동안 흐려진다).
# 슬라임이 느리고 몸에 가려지니 수명을 넉넉히 둔다.
PUDDLE_GAP, PUDDLE_SECONDS = 34, 8.0
INK = (7, 14, 27)
PANEL = (13, 26, 44)
LINE = (52, 76, 101)
WHITE = (231, 241, 248)
MUTED = (158, 183, 206)
CYAN = (96, 233, 223)
GOLD = (245, 181, 100)
RED = (249, 107, 109)
PURPLE = (203, 145, 238)
ASSETS = Path(__file__).resolve().parent / 'assets'
# Pixel rows of the floor surfaces in each full-stage image, lowest floor first.
MAP_ART = {
    1: ('map_sections/stage-01-detailed.png', (773,)),
    3: ('map_sections/stage-10-detailed.png', (775, 547, 327)),
}
PLATE_FRAMES = ((110, 316, 850, 176), (1207, 316, 850, 176))
GATE_FRAMES = ((322, 14, 384, 820), (1135, 14, 384, 820))
EXIT_FRAME = (40, 34, 908, 1504)
LADDER_FRAME = (263, 4, 361, 1766)
LEVER_FRAMES = ((210, 132, 646, 535), (1324, 132, 646, 535))
# Separate objects in the existing puzzle concept sheet (top-left image coordinates).
PUZZLE_PROPS = {
    'watch': (35, 36, 375, 390),
    'guard': (477, 12, 346, 415),
    'sensor': (875, 260, 405, 165),
    'locked_gate': (1310, 0, 340, 425),
    'lever': (1646, 265, 100, 156),
    'bridge': (20, 576, 420, 225),
    'hazard': (435, 608, 450, 222),
    'sync': (895, 470, 350, 360),
    'lift_platform': (1302, 681, 290, 100),
    'lift_weight': (1505, 775, 245, 103),
}
WEAPON_SPRITES = {
    1: ((247, 111, 143, 461), 32, 0.81),
    2: ((335, 48, 355, 1450), 65, 0.84),
    3: ((173, 703, 299, 466), 43, 0.72),
    4: ((884, 625, 126, 601), 62, 0.76),
}
JUMP_FRAMES = (
    (90, 146, 246, 280), (523, 66, 248, 358), (967, 24, 228, 362), (1410, 10, 230, 302),
    (76, 459, 238, 354), (519, 465, 228, 392), (955, 533, 240, 340), (1430, 467, 196, 406),
)
# Keep the face aligned when cape and body widths change between jump poses.
JUMP_FACE_X = (285, 715, 1145, 1595, 275, 708, 1150, 1560)
JUMP_HEAD_LIFT = (0, 10, 9, 21, 13, 4, 12, 0)
# Frame 0 is a grounded take-off crouch. The jump leaves the floor on its first
# step, so it starts from the standing pose (7) and frame 0 is intentionally unused.
JUMP_POSE_ORDER = (7, 1, 2, 3, 4, 5, 6, 7)


def box(left, bottom, right, top, color, filled=True):
    draw_rectangle(left, bottom, right, top, *color, filled=filled)


def line(x1, y1, x2, y2, color):
    draw_line(x1, y1, x2, y2, *color)


def load_asset(name):
    return load_image(str(asset_path(name)))


def text_width(font, text):
    width, height = c_int(), c_int()
    canvas.TTF_SizeUTF8(font.font, text.encode('utf-8'), byref(width), byref(height))
    return width.value


MONSTER_NAMES = {
    'beast': '뿔짐승', 'warden': '돌 수호자', 'watcher': '외눈 유령', 'crawler': '거미',
    'tier_ghost': '떠도는 유령',
    'jailer_boss': '쇠사슬 간수', 'magic_book': '마법책', 'potion_slime': '물약 슬라임',
    'magic_armor': '마법 갑옷', 'magic_armor_guard': '갑옷 경비병', 'witch': '마녀', 'grand_witch': '대마녀',
    'echo_knight': '뒤틀린 잔향의 기사', 'time_thief': '시간 도둑',
    'cursed_lantern': '저주받은 등불', 'broken_jester': '부서진 광대 인형',
}


# assets/ui_concepts/echo_hud_concept.png의 막대 픽셀 (원본 좌표).
# 안쪽 영역은 (left, top, right, bottom), 조각은 (x, y, width, height)이다.
HUD_HP_INNER = (405, 246, 1146, 299)  # 그려진 "HP 3 / 3" 글자와 양 끝의 빨간 부분까지 덮는다.
HUD_HP_FILL = (420, 248, 240, 47)    # 빨간 천 질감. 가운데의 글자를 피해 왼쪽만 쓴다.
HUD_XP_INNER = (409, 331, 1110, 346)
HUD_XP_FILL = (420, 331, 300, 15)    # 금색 경험치 질감
HUD_EMPTY = (760, 331, 340, 15)      # 경험치 막대 오른쪽의 빈 홈. 체력 막대의 빈 칸에도 쓴다.


def draw_grounded(image, region, x, y, height):
    width = round(height * region[2] / region[3])
    draw_region(image, region, x - width / 2, y, width, height)


class View:
    def __init__(self):
        fallback = Path(environ['PICO2D_DATA_PATH']) / 'ConsolaMalgun.ttf'
        font_dir = Path(environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        regular = font_dir / 'malgun.ttf'
        bold = font_dir / 'malgunbd.ttf'
        self.small = load_font(str(regular if regular.exists() else fallback), 15)
        self.body = load_font(str(regular if regular.exists() else fallback), 19)
        self.heading = load_font(str(bold if bold.exists() else fallback), 25)
        self.display = load_font(str(bold if bold.exists() else fallback), 47)
        stage_font = font_dir / 'Hancom Gothic Bold.ttf'
        self.stage_title = load_font(str(stage_font if stage_font.exists() else bold if bold.exists() else fallback), 38)
        self.current_world = None
        self.slime_puddle = load_asset('PixelLab/몬스터/slime_puddle.png')
        self.slime_trail, self.slime_last = [], {}   # 물약 자국 (x, 층, 생긴 시각), 슬라임별 마지막 자국 x
        self.free_camera = False
        self.free_camera_x = 0.0
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.floor_view_texture = None
        self.last_floor = None
        self.floor_transition_at = 0.0
        self.camera_lift = 0.0   # 통합방에서 화면을 위로 올린 거리 (층별 화면 자르기에도 쓴다)
        self.shake_base = None
        self.stage_started_at = 0.0
        self.background = load_asset('dungeon.png')
        self.hud_concept = load_asset('ui_concepts/echo_hud_concept.png')
        self.echo_selection_panel = load_asset('ui_concepts/echo_selection_panel.png')
        self.boss_bars = {
            'jailer_boss': load_asset('ui_concepts/boss_bar_jailer_named.png'),
            'grand_witch': load_asset('ui_concepts/boss_bar_witch_named.png'),
            'echo_knight': load_asset('ui_concepts/boss_health_bar_concept.png'),
        }
        self.title_art = load_asset('title_art.png')
        self.guide_background = load_asset('game_guide_background.png')
        self.settings_background = load_asset('settings_background.png')
        self.title_screen_echo = load_asset('title_screen_echo_concept.png')
        self.title_button_gold = load_asset('title_menu_button_gold.png')
        self.title_button_scales = [1.0] * 5
        self.title_button_updated_at = perf_counter()
        self.stage_art = {}
        for floor_count, (name, rows) in MAP_ART.items():
            image = load_asset(name)
            self.stage_art[floor_count] = (image, tuple(HEIGHT - round(row * HEIGHT / image.h) for row in rows))
        self.wizard_art = load_asset('wizard_castle/castle-dark.png')
        self.sky_library_art = load_asset('층별맵/3스테이지_마법도서관_통합배경.png')
        sdl2.SDL_SetTextureScaleMode(self.sky_library_art.texture, sdl2.SDL_ScaleModeLinear)
        # 하늘 섬 날갯짓 (PixelLab, tools/monster_pixel/pixellab_sky_island.py): 가로 8칸, 한 칸 176 × 80, 돌 윗면 35줄
        self.sky_island_art = load_asset('PixelLab/스테이지/sky_island.png')
        sdl2.SDL_SetTextureScaleMode(self.sky_island_art.texture, sdl2.SDL_ScaleModeNearest)
        self.late_three_floor_art = load_asset('map_sections/echo-knight-approach-three-floors-concept.png')
        self.late_arcane_castle = load_asset('map_sections/late_arcane_castle.png')
        self.late_arcane_arena = load_asset('map_sections/late_arcane_arena.png')
        self.witch_boss_arena = load_asset('map_sections/stage-07-witch-boss-arena.png')
        floor_counts = (3, 3, 4, 4, 4, 4, 6, 3, 3)
        self.floor_images = {
            index: [load_asset(f'층별맵/구간{index + 1:02d}_{floor + 1}층.png')
                    for floor in range(count)]
            for index, count in enumerate(floor_counts)
        }
        self.floor_images[0][1] = load_asset('층별맵/구간01_2층_조각상.png')
        self.stage1_pixel_image = load_asset('층별맵/1스테이지_감옥_고화질.png')
        sdl2.SDL_SetTextureScaleMode(self.stage1_pixel_image.texture, sdl2.SDL_ScaleModeLinear)
        self.stage1_second_floor = load_asset('층별맵/1스테이지_2층_수로배경.png')
        sdl2.SDL_SetTextureScaleMode(self.stage1_second_floor.texture, sdl2.SDL_ScaleModeLinear)
        self.beast_jump_backgrounds = (
            load_asset('층별맵/2스테이지_뿔짐승_도약실.png'),
            load_asset('층별맵/2스테이지_숨겨진_관측실.png'),
        )
        for background in self.beast_jump_backgrounds:
            sdl2.SDL_SetTextureScaleMode(background.texture, sdl2.SDL_ScaleModeLinear)
        self.floor_arenas = {
            index: load_asset(f'층별맵/구간{index + 1:02d}_보스방.png')
            for index in (2, 5, 8)
        }
        self.wizard_book = load_asset('wizard_castle/book.png')
        self.wizard_fx = {}
        for name in ('rain', 'storm', 'potion'):
            data = json.loads((ASSETS / 'wizard_castle' / f'{name}.json').read_text(encoding='utf-8'))
            self.wizard_fx[name] = (load_asset(f'wizard_castle/{name}.png'), data)
        self.plate_art = load_asset('dungeon_props/pressure-plate.png')
        self.gate_art = load_asset('dungeon_props/portcullis.png')
        self.web_beam_art = load_asset('dungeon_props/spider_web_beam.png')
        self.pixel_statue_art = load_asset('1스테이지_굵은도트_가고일.png')
        sdl2.SDL_SetTextureScaleMode(self.pixel_statue_art.texture, sdl2.SDL_ScaleModeNearest)
        self.statue_chain_art = load_asset('1스테이지_조각상_쇠사슬.png')
        sdl2.SDL_SetTextureScaleMode(self.statue_chain_art.texture, sdl2.SDL_ScaleModeNearest)
        self.poison_rest_art = load_asset('2층_수로_돌발판.png')
        self.poison_wall_art = load_asset('2층_수로_돌벽.png')
        self.poison_fx = PoisonFx()
        self.pixel_sprites = PixelSprites()   # 1스테이지 장식물 도트
        self.hero_sprite = HeroSprite(load_asset)   # 모든 스테이지의 도트 주인공 (PixelLab)
        self.monster_sprite = MonsterSprite(load_asset)   # 1스테이지 도트 거미·외눈 유령
        self.stage1_folder_monsters = monster_sprite.StageOneFolderMonsters(load_asset)
        self.exit_art = load_asset('dungeon_props/exit-portal.png')
        self.ladder_art = load_asset('dungeon_props/ladder.png')
        self.lever_art = load_asset('dungeon_props/lever.png')
        self.puzzle_art = load_asset('puzzle_concepts/echo-puzzle-props-concept.png')
        self.jester_walk = load_asset('monster_concepts/broken-jester-walk-16.png')
        self.knight_sheets = {
            name: load_asset(f'monster_concepts/echo-knight-{name}-sheet.png')
            for name in ('walk', 'attack', 'charge', 'orb', 'bolts')
        }
        self.echo = load_asset('echo_silver_gold.png')
        self.enemies = {name: load_asset(kind.image) for name, kind in ENEMY_KINDS.items()}
        walk_data = json.loads((ASSETS / 'walk_sheets.json').read_text(encoding='utf-8'))
        actors = walk_data['actors']
        detailed_echo = load_asset('echo_detailed_sheet.png')
        detailed_width = detailed_echo.w // 8
        detailed_height = detailed_echo.h // 3
        detailed_frames = [(index * detailed_width, detailed_height, detailed_width, detailed_height)
                           for index in range(8)]
        self.echo_walk = WalkCycle(detailed_echo, detailed_frames, 96, actors['echo']['stride_per_frame'])
        # 본체 점프 시트와 포즈·배치가 같은 분신판. _draw_jump_pose가 같은 프레임 표로 그린다.
        self.echo_jump_art = load_asset('echo_jump_sheet.png')
        echo_files = {
            'beast': 'hornbeast', 'warden': 'stone_warden', 'watcher': 'watcher',
            'crawler': 'spider', 'magic_book': 'magic_book', 'potion_slime': 'potion_slime',
            'magic_armor': 'magic_armor', 'magic_armor_guard': 'magic_armor', 'witch': 'witch',
            'time_thief': 'time_thief', 'cursed_lantern': 'cursed_lantern', 'broken_jester': 'broken_jester',
        }
        self.monster_echo_walk = {}
        for name, filename in echo_files.items():
            sheet = load_asset(f'monster_echo_concepts/{filename}_echo_walk.png')
            width, height = sheet.w // 4, sheet.h // 2
            frames = [(column * width, row * height, width, height)
                      for row in range(2) for column in range(4)]
            self.monster_echo_walk[name] = WalkCycle(sheet, frames, ENEMY_KINDS[name].size, 9)
        self.attack_fx = load_attack_fx(ASSETS / 'attack_fx')
        self.enemy_walk = {
            name: MonsterWalk(load_asset(gait.sheet), gait)
            for name, gait in MONSTER_GAITS.items()
            if asset_path(gait.sheet).exists()   # 새 시트로 바꾸려고 지운 부위 그림은 건너뛰고 서 있는 그림으로 그린다
        }
        watcher = actors['watcher']
        self.enemy_walk['watcher'] = WalkCycle(
            load_asset(watcher['sheet']), watcher['frames'],
            watcher['draw_height'], watcher['stride_per_frame'],
        )
        spider = load_asset('monster_spider_walk_sheet.png')
        cell_w, cell_h = spider.w // 4, spider.h // 2
        spider_frames = [(column * cell_w, row * cell_h + round(cell_h * 0.20),
                          cell_w, round(cell_h * 0.65))
                         for row in range(2) for column in range(4)]
        self.enemy_walk['crawler'] = WalkCycle(spider, spider_frames, 70, 9)
        self.enemy_walk['tier_ghost'] = self.enemy_walk['watcher']
        for name, asset in (
            ('jailer_boss', 'prison-jailer-boss'), ('magic_armor', 'magic-armor'),
            ('magic_armor_guard', 'magic-armor'),
            ('witch', 'witch'), ('grand_witch', 'grand-witch-boss'),
        ):
            suffix = '-walk-transparent.png' if name == 'grand_witch' else '-walk.png'
            sheet = load_asset(f'monster_concepts/{asset}{suffix}')
            width, height = sheet.w // 4, sheet.h // 2
            frames = [(column * width, row * height, width, height)
                      for row in range(2) for column in range(4)]
            self.enemy_walk[name] = WalkCycle(sheet, frames, ENEMY_KINDS[name].size, 9)
        self.enemies['magic_book'] = load_asset('monster_concepts/magic-book-sprite.png')
        self.enemies['potion_slime'] = load_asset('monster_concepts/potion-slime-sprite.png')

    def _shake(self, world, screen):
        """world.shake가 남아 있는 동안 화면 전체를 흔든다."""
        renderer = canvas.renderer
        if screen == 'intro' or world.shake <= 0:
            if self.shake_base is not None:
                canvas.SDL_RenderSetViewport(renderer, self.shake_base)
                self.shake_base = None
            return
        if self.shake_base is None:
            # 전체 화면 여백이 든 원래 뷰포트를 기억했다가 흔들림이 끝나면 되돌린다.
            self.shake_base = canvas.SDL_Rect()
            canvas.SDL_RenderGetViewport(renderer, byref(self.shake_base))
        base, time = self.shake_base, perf_counter()
        power = 7 * min(1, world.shake / 0.25)
        canvas.SDL_RenderSetViewport(renderer, canvas.SDL_Rect(
            base.x + round(sin(time * 83) * power), base.y + round(sin(time * 67) * power), base.w, base.h))

    def toggle_free_camera(self):
        self.free_camera = not self.free_camera
        if self.free_camera:
            self.free_camera_x = self.camera_x
            if self.current_world is not None:
                self.move_free_camera(self.current_world, 0, 0, 0)
        self.camera_updated_at = perf_counter()

    def move_free_camera(self, world, horizontal, vertical, elapsed):
        if not self.free_camera:
            return
        speed = 700
        self.free_camera_x = min(WIDTH, max(0, self.free_camera_x + horizontal * speed * elapsed))
        if world.stage.floor_height > 400:
            maximum_y = ((world.stage.floors - 1) * world.stage.floor_height
                         + world.stage.floor_height - 465)
        else:
            maximum_y = max(0, (world.stage.floors - 1) * 410)
        self.camera_y = min(maximum_y, max(0, self.camera_y + vertical * speed * elapsed))

    def draw(self, world, screen, menu=None):
        self._shake(world, screen)
        if screen == 'intro':
            self.background.draw(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT)
            self._draw_title(menu)
            return
        if world is not self.current_world:
            self.current_world = world
            self.slime_trail, self.slime_last = [], {}
            self.stage_started_at = perf_counter()
            self.camera_y = 0.0
            self.camera_updated_at = perf_counter()
            self.last_floor = None
        focus = world.recording.preview if world.recording else world.player
        single_floor = not self.free_camera and world.stage.floors > 1
        if single_floor:
            if self.last_floor is not None and self.last_floor != focus.floor:
                self.floor_transition_at = perf_counter()
            self.last_floor = focus.floor
            if self.floor_view_texture is None:
                self.floor_view_texture = sdl2.SDL_CreateTexture(
                    canvas.renderer, sdl2.SDL_PIXELFORMAT_RGBA8888,
                    sdl2.SDL_TEXTUREACCESS_TARGET, WIDTH, HEIGHT)
                if not self.floor_view_texture:
                    raise RuntimeError('층별 화면을 만들 수 없습니다.')
            sdl2.SDL_SetRenderTarget(canvas.renderer, self.floor_view_texture)
            sdl2.SDL_SetRenderDrawColor(canvas.renderer, 7, 14, 27, 255)
            sdl2.SDL_RenderClear(canvas.renderer)
        self.camera_x = self.free_camera_x if self.free_camera else min(WIDTH, max(0, focus.x - WIDTH * 0.60))
        if world.stage.floor_height == 400:
            self.camera_lift = 0.0
        if world.index in (0, 1, 3, 4, 9):
            # Follow the active character and keep all floor positions in world space.
            now = perf_counter()
            elapsed = min(0.1, max(0, now - self.camera_updated_at))
            self.camera_updated_at = now
            gap = world.stage.floor_height
            if gap > 400 and focus.elevator_target is None:
                # 두 층을 합친 통합방: 캐릭터가 올라가면 화면도 위로 따라간다.
                self.camera_lift = max(0.0, min(gap - 360.0, focus.jump_height - 100))
            target = gap * (focus.floor if single_floor else focus.floor + focus.elevator_offset) + self.camera_lift
            if not self.free_camera:
                self.camera_y = target if single_floor else self.camera_y + max(-850 * elapsed, min(850 * elapsed, target - self.camera_y))
            self.floor_y = tuple(160 + floor * gap - self.camera_y
                                 for floor in range(world.stage.floors))
            if world.index == 0:
                for floor, floor_y in enumerate(self.floor_y):
                    image = self.stage1_second_floor if floor == 1 else self.stage1_pixel_image
                    floor_row = round(image.h * (600 if floor == 1 else 610) / 724)
                    draw_region(image, (0, 0, image.w, floor_row),
                                -self.camera_x, floor_y, WIDTH * 2, 308)
                    holes = sorted((left, right) for level, left, right
                                   in (*world.stage.pits, *world.stage.poison_zones) if level == floor)
                    start = 0
                    for left, right in (*holes, (WIDTH * 2, WIDTH * 2)):
                        end = min(WIDTH * 2, left)
                        if end > start:
                            source_left = round(start * image.w / (WIDTH * 2))
                            source_right = round(end * image.w / (WIDTH * 2))
                            draw_region(image, (source_left, floor_row, source_right - source_left,
                                                image.h - floor_row), start - self.camera_x,
                                        floor_y - 92, end - start, 92)
                        start = max(start, right)
            elif world.index == 1:
                for floor, floor_y in enumerate(self.floor_y):
                    background = self.beast_jump_backgrounds[floor]
                    wall_height = background.h - 20 if floor == 0 else background.h
                    draw_region(background, (0, 0, background.w, wall_height),
                                -self.camera_x, floor_y, WIDTH * 2, gap)
                    floor_image = self.stage1_pixel_image
                    floor_row = round(floor_image.h * 610 / 724)
                    holes = sorted((left, right) for level, left, right in world.stage.pits if level == floor)
                    start = 0
                    for left, right in (*holes, (WIDTH * 2, WIDTH * 2)):
                        end = min(WIDTH * 2, left)
                        if end > start:
                            sx = round(start * floor_image.w / (WIDTH * 2))
                            ex = round(end * floor_image.w / (WIDTH * 2))
                            draw_region(floor_image, (sx, floor_row, ex - sx, floor_image.h - floor_row),
                                        start - self.camera_x, floor_y - 92, end - start, 92)
                        start = max(start, right)
            elif world.stage.sky:
                floor_y = self.floor_y[0]
                image = self.sky_library_art
                floor_row = round(image.h * 839 / 903)
                draw_region(image, (0, 0, image.w, floor_row),
                            -self.camera_x, floor_y, WIDTH * 2, 1000)
                draw_region(image, (0, floor_row, image.w, image.h - floor_row),
                            -self.camera_x, floor_y - 160, WIDTH * 2, 160)
                for i in range(9):
                    x = 580 + i * 120 - self.camera_x
                    rain, data = self.wizard_fx['rain']
                    rain_frame = data['frames'][int(world.time * 4) % len(data['frames'])]['frame']
                    canvas.SDL_SetTextureAlphaMod(rain.texture, 65)
                    draw_region(rain, (rain_frame['x'], rain_frame['y'], rain_frame['w'],
                                       round(rain_frame['h'] * 0.85)), x, floor_y + 85, 120, 840)
                    canvas.SDL_SetTextureAlphaMod(rain.texture, 255)
                if 9.0 <= world.time % 18 < 9.5:
                    storm, storm_data = self.wizard_fx['storm']
                    index = 12 + int((world.time % 18 - 9.0) * 4)
                    frame = storm_data['frames'][index]['frame']
                    canvas.SDL_SetTextureAlphaMod(storm.texture, 150)
                    draw_region(storm, (frame['x'] + 150, frame['y'] + 20, 120, frame['h'] - 40),
                                1260 - self.camera_x, floor_y + 300, 260, 520)
                    canvas.SDL_SetTextureAlphaMod(storm.texture, 255)
            else:
                for floor, floor_y in enumerate(self.floor_y):
                    corridor = self.floor_images[world.index][floor]
                    source_height = corridor.h
                    bottom = floor_y - (724 - 675) * 400 / source_height
                    draw_region(corridor, (0, 0, corridor.w, source_height),
                                -self.camera_x, bottom, WIDTH * 2, 400)
                self._draw_wizard_tower_effects(world.time)
        elif world.index in (6, 7, 8):
            # Follow the actual floor positions in the three-floor background.
            box(0, 0, WIDTH, HEIGHT, INK)
            now = perf_counter()
            elapsed = min(0.1, max(0, now - self.camera_updated_at))
            self.camera_updated_at = now
            image = self.late_three_floor_art
            scale_y = 400 / 231
            levels = (0, (690 - 455) * scale_y, (690 - 228) * scale_y,
                      (690 - 228) * scale_y + 400,
                      (690 - 228) * scale_y + 400 + (690 - 455) * scale_y)
            floor = focus.floor
            offset = 0 if single_floor else focus.elevator_offset
            target = levels[floor]
            if offset > 0 and floor + 1 < len(levels):
                target += offset * (levels[floor + 1] - levels[floor])
            elif offset < 0 and floor > 0:
                target += offset * (levels[floor] - levels[floor - 1])
            if not self.free_camera:
                self.camera_y = target if single_floor else self.camera_y + max(-850 * elapsed, min(850 * elapsed, target - self.camera_y))
            self.floor_y = tuple(160 + level - self.camera_y for level in levels[:world.stage.floors])
            bottom = self.floor_y[0] - (image.h - 690) * scale_y
            rows = ((455, 724), (228, 455), (0, 228))
            for floor, (top, lower) in enumerate(rows):
                layer = self.late_arcane_castle
                draw_region(layer, (0, top, layer.w, lower - top), -self.camera_x,
                            bottom + (image.h - lower) * scale_y,
                            WIDTH * 2, (lower - top) * scale_y)
            if world.index == 6:
                # The five-floor stage continues the same background above floor 3.
                for floor, (top, lower) in enumerate(rows, start=3):
                    layer = self.late_arcane_castle
                    draw_region(layer, (0, top, layer.w, lower - top), -self.camera_x,
                                bottom + levels[3] + (image.h - lower) * scale_y,
                                WIDTH * 2, (lower - top) * scale_y)
            elif world.index == 8:
                arena = self.late_arcane_arena
                draw_region(arena, (0, 0, arena.w, arena.h), -self.camera_x,
                            self.floor_y[3] - 95, WIDTH * 2, 560)
        elif world.index in (2, 5):
            now = perf_counter()
            elapsed = min(0.1, max(0, now - self.camera_updated_at))
            self.camera_updated_at = now
            lift_offset = world.lift_progress if world.index == 5 and world.lift_riding and focus is world.player else 0
            target = 400 * (focus.floor if single_floor else focus.floor + focus.elevator_offset + lift_offset)
            if not self.free_camera:
                self.camera_y = target if single_floor else self.camera_y + max(-850 * elapsed, min(850 * elapsed, target - self.camera_y))
            self.floor_y = tuple(160 + floor * 400 - self.camera_y for floor in range(5))
            if world.index == 2:
                for floor in range(4):
                    corridor = self.floor_images[world.index][floor]
                    floor_y = self.floor_y[floor]
                    bottom = floor_y - (corridor.h - 773) * 400 / corridor.h
                    draw_region(corridor, (0, 0, corridor.w, corridor.h),
                                -self.camera_x, bottom, WIDTH * 2, 400)
                arena = self.floor_arenas[world.index]
            else:
                for floor in range(4):
                    corridor = self.floor_images[world.index][floor]
                    source_height = corridor.h
                    bottom = self.floor_y[floor] - (724 - 675) * 400 / source_height
                    draw_region(corridor, (0, 0, corridor.w, source_height),
                                -self.camera_x, bottom, WIDTH * 2, 400)
                arena = self.floor_arenas[world.index]
            draw_region(arena, (0, 0, arena.w, arena.h), -self.camera_x,
                        self.floor_y[4] - 95, WIDTH * 2, 560)
            if world.index == 5:
                self._draw_wizard_tower_effects(world.time)
        elif world.index == 1:
            # Stack the same prison corridor for each playable floor.
            image, _ = self.stage_art[1]
            floor_y = []
            for floor in range(world.stage.floors):
                bottom = 105 + floor * 520 // world.stage.floors
                top = 105 + (floor + 1) * 520 // world.stage.floors
                height = top - bottom
                draw_region(image, (0, 0, image.w, image.h),
                            -self.camera_x, bottom, WIDTH * 2, height)
                floor_y.append(bottom + round((image.h - 773) * height / image.h))
            self.floor_y = tuple(floor_y)
        elif 3 <= world.index <= 5:
            single_floor = world.stage.floors == 1
            source_top = 330 if single_floor else 0
            source_height = self.wizard_art.h - source_top
            rows = (675,) if single_floor else (675, 330)
            self.floor_y = tuple(105 + round((self.wizard_art.h - row) * 520 / source_height)
                                 for row in rows)
            draw_region(self.wizard_art, (0, source_top, self.wizard_art.w, source_height),
                        -self.camera_x, 105, WIDTH * 2, 520)
            self._draw_wizard_effects(world.time, single_floor)
        elif world.index == 6:
            image = self.late_three_floor_art
            source_height = 480
            self.floor_y = tuple(105 + round((source_height - row) * 520 / source_height)
                                 for row in (455, 228))
            draw_region(image, (0, 0, image.w, source_height),
                        -self.camera_x, 105, WIDTH * 2, 520)
        elif world.index == 7:
            image = self.late_three_floor_art
            self.floor_y = tuple(105 + round((image.h - row) * 520 / image.h)
                                 for row in (690, 455, 228))
            draw_region(image, (0, 0, image.w, image.h),
                        -self.camera_x, 105, WIDTH * 2, 520)
        else:
            image, self.floor_y = self.stage_art[world.stage.floors]
            # Crop the picture frame and draw the corridor as one wide image.
            edge = 38 if world.stage.floors > 1 else 0
            draw_region(image, (edge, 0, image.w - edge * 2, image.h),
                        -self.camera_x, 0, WIDTH * 2, HEIGHT)
        self.animation_time = world.time
        for i in range(24):
            x = (i * 137 + world.time * (7 + i % 4)) % (RIGHT + 48) - self.camera_x
            y = 130 + (i * 83 + sin(world.time * 0.7 + i) * 9) % 460
            box(x, y, x + 2, y + 2, (118, 174, 187))
        self._draw_map(world)
        self._draw_characters(world)
        if single_floor:
            sdl2.SDL_SetRenderTarget(canvas.renderer, None)
            floor_y = self.floor_y[focus.floor] + self.camera_lift
            source = sdl2.SDL_Rect(0, round(HEIGHT - (floor_y + 308)), WIDTH, 400)
            destination = sdl2.SDL_Rect(0, 95, WIDTH, 521)
            sdl2.SDL_RenderCopy(canvas.renderer, self.floor_view_texture, source, destination)
            if focus.elevator_target is not None:
                fade = max(0.0, (abs(focus.elevator_offset) - 0.65) / 0.35)
            else:
                fade = max(0.0, 1.0 - (perf_counter() - self.floor_transition_at) / 0.3)
            if fade > 0:
                box(0, 104, WIDTH, 625, (7, 14, 27, round(220 * fade)))
        self._draw_hud(world)
        if self.free_camera:
            box(345, 587, 775, 620, INK)
            self.small.draw(360, 600, '맵 둘러보기  ·  방향키 이동  ·  + 키로 돌아가기', WHITE)
        stage_title = STAGE_TITLES[stage_group_index(world.index)]
        if perf_counter() - self.stage_started_at < 3.5 and world.result == 'playing':
            width = text_width(self.stage_title, stage_title)
            self.stage_title.draw((WIDTH - width) / 2, HEIGHT / 2, stage_title, WHITE)
        if world.result == 'defeated':
            self._card('다시 도전', stage_title, '분신의 경로나 본체의 출발 시점을 바꿔 보세요.', 'R   스테이지 재시작')
        elif world.result == 'cleared':
            if world.index == len(STAGES) - 1:
                self._card('탈출 성공', 'ECHO ESCAPE', f'{len(STAGE_GROUPS)}개 스테이지의 봉인을 모두 통과했습니다.', 'ENTER   처음부터 다시')
            else:
                self._card('스테이지 완료', stage_title, '다음 스테이지에서 분신의 새로운 역할을 준비하세요.', 'ENTER   다음 스테이지')

    def _wizard_fx_frame(self, name, frame, left, bottom, width, height, alpha=255):
        image, data = self.wizard_fx[name]
        rect = data['frames'][frame % len(data['frames'])]['frame']
        canvas.SDL_SetTextureAlphaMod(image.texture, alpha)
        draw_region(image, (rect['x'], rect['y'], rect['w'], rect['h']), left, bottom, width, height)
        canvas.SDL_SetTextureAlphaMod(image.texture, 255)

    def _draw_wizard_effects(self, time, single_floor=False):
        # Window positions refer to the shared, full-width castle artwork.
        sx = WIDTH * 2 / self.wizard_art.w
        sy = 520 / (self.wizard_art.h - (330 if single_floor else 0))
        for x0, x1 in ((715, 880), (950, 1110), (1180, 1340), (1405, 1555), (1610, 1765)):
            window_rows = ((410, 570),) if single_floor else ((85, 250), (410, 570))
            for top, bottom in window_rows:
                x = x0 * sx - self.camera_x
                y = 105 + (self.wizard_art.h - bottom) * sy
                width, height = (x1 - x0) * sx, (bottom - top) * sy
                self._wizard_fx_frame('rain', int(time * 4), x, y, width, height, 115)
                # A brief distant flash shares the same time on both floors.
                if 9.0 <= time % 18 < 9.5:
                    storm_frame = 12 + int((time % 18 - 9.0) * 4)
                    self._wizard_fx_frame('storm', storm_frame, x, y, width, height, 110)
        if not single_floor:
            book_frame = min(3, int((time % 7) * 5)) if time % 7 < 0.8 else 0
            book_width = self.wizard_book.w // 4
            draw_region(self.wizard_book, (book_frame * book_width, 0, book_width, self.wizard_book.h),
                        455 * sx - self.camera_x, 105 + (self.wizard_art.h - 260) * sy, 70, 50)
        self._wizard_fx_frame('potion', int(time * 8), 380 * sx - self.camera_x,
                              105 + (self.wizard_art.h - 600) * sy, 48, 62)

    def _polygon(self, points, colors):
        """삼각형들을 꼭짓점 색으로 채워 그린다. points는 게임 좌표(아래가 0)이고 3개씩 한 삼각형이다."""
        height = canvas.get_canvas_height()
        vertices = (canvas.SDL_Vertex * len(points))()
        for vertex, (x, y), (r, g, b, a) in zip(vertices, points, colors):
            vertex.position = canvas.SDL_FPoint(x, height - y)
            vertex.color = canvas.SDL_Color(r, g, b, a)
        canvas.SDL_RenderGeometry(canvas.renderer, None, vertices, len(points), None, 0)

    def _draw_sky_puzzle(self, world):
        """하늘 땅 퍼즐: 염력 범위, 날개 달린 땅, 1·2·3 스위치. 출구 잠금은 출구 그림에서 그린다."""
        sky, floor_y, time = world.stage.sky, self.floor_y[0], world.time
        book = world._sky_book()
        if book is not None:
            # 마법책 분신의 염력이 닿는 원
            x, y = book.x - self.camera_x, floor_y + book.jump_height + 30
            points, colors = [], []
            for i in range(40):
                a, b = i / 40 * 6.2832, (i + 1) / 40 * 6.2832
                points += [(x, y), (x + sky.reach * cos(a), y + sky.reach * sin(a)),
                           (x + sky.reach * cos(b), y + sky.reach * sin(b))]
                colors += [(190, 120, 255, 10), (190, 120, 255, 46), (190, 120, 255, 46)]
            self._polygon(points, colors)
        half = sky.width / 2
        for index, (bx, height) in enumerate(world.sky_blocks):
            x, y = bx - self.camera_x, floor_y + height
            frame = int(time * 9 + index * 3) % 8   # 섬마다 날갯짓 박자를 어긋나게
            draw_region(self.sky_island_art, (frame * 176, 0, 176, 80), x - 88, y - 45, 176, 80)
            if index == world.sky_hold:
                box(x - half - 3, y - 33, x + half + 3, y + 3, CYAN, filled=False)
            elif book is not None and hypot(bx - book.x, height - book.jump_height - 30) <= sky.reach:
                box(x - half - 2, y - 32, x + half + 2, y + 2, (214, 176, 255), filled=False)
        for index, (sx, height) in enumerate(sky.switches):
            on = index < world.sky_progress
            x, y = sx - self.camera_x, floor_y + height
            draw_grounded(self.lever_art, LEVER_FRAMES[on], x, y, 34)
            self.heading.draw(x - 7, y + 52, str(index + 1), CYAN if on else GOLD)

    def _draw_potions(self, world):
        """물약 슬라임: 결계 금고, 포털 한 쌍(파랑·주황), 날아가는 물약, F로 모으는 동안의 예상 궤적."""
        colors = ((80, 170, 255), (255, 150, 60))
        for left, bottom, right, top in world.stage.seals:
            # 결계 금고: 돌 벽과 천장, 안쪽은 청록 결계가 일렁인다.
            x1, x2 = left - self.camera_x, right - self.camera_x
            y1, y2 = self.floor_y[0] + bottom, self.floor_y[0] + top
            alpha = 34 + int(14 * sin(world.time * 3))
            self._polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y1), (x2, y2), (x1, y2)], [(110, 230, 230, alpha)] * 6)
            box(x1, y2, x2, y2 + 18, (70, 62, 96))
            box(x2 - 14, y1, x2, y2, (70, 62, 96))
            box(x1, y1, x2, y2 + 18, GOLD, filled=False)
            for k in range(6):
                yy = y1 + 20 + k * (y2 - y1 - 30) / 5
                line(x1, yy, x1 + 8, yy + 8, CYAN)
            self.small.draw(x1 + 10, y2 + 34, '봉인 금고 · 물약은 결계에 깨진다', GOLD)
        for index in range(2):
            if world.portals[index] is None:
                continue
            floor, px, height = world.portal_point(index)
            cx, cy = px - self.camera_x, self.floor_y[floor] + height + 30
            for grow in (6, 3, 0):
                ring = [(cx + (14 + grow) * cos(a / 12 * pi), cy + (30 + grow) * sin(a / 12 * pi)) for a in range(25)]
                for (ax, ay), (bx, by) in zip(ring, ring[1:]):
                    line(ax, ay, bx, by, colors[index] if grow == 0 else tuple(c // 2 for c in colors[index]))
        for x, floor, height, vx, vh in world.potions:
            self._disc(x - self.camera_x, self.floor_y[floor] + height, 6, colors[world.portal_next])
        recording = world.recording
        if recording is not None and recording.monster_kind == 'potion_slime' and recording.preview.potion_charge > 0:
            x, floor, height, vx, vh = potion_launch(recording.preview)
            for k in range(1, 60):
                t = k * 0.04
                h = height + vh * t - POTION_GRAVITY * t * t / 2
                if h < -40:
                    break
                if k % 2 == 0:
                    self._disc(x + vx * t - self.camera_x, self.floor_y[floor] + h, 2.5,
                               colors[world.portal_next], sides=6)

    def _disc(self, x, y, radius, color, sides=14):
        points, colors = [], []
        for i in range(sides):
            a, b = i / sides * 6.2832, (i + 1) / sides * 6.2832
            points += [(x, y), (x + radius * cos(a), y + radius * sin(a)), (x + radius * cos(b), y + radius * sin(b))]
            colors += [(*color[:3], 255)] * 3
        self._polygon(points, colors)

    def _gear(self, x, y, radius, angle, lit):
        """톱니바퀴. lit이면 금빛으로 빛난다."""
        rim = (255, 190, 96) if lit else (112, 86, 56)
        teeth = 10
        points, colors = [], []
        for i in range(teeth * 2):
            a, b = angle + i / (teeth * 2) * 6.2832, angle + (i + 1) / (teeth * 2) * 6.2832
            r1 = radius if i % 2 == 0 else radius * 0.78
            points += [(x, y), (x + r1 * cos(a), y + r1 * sin(a)), (x + r1 * cos(b), y + r1 * sin(b))]
            colors += [(*rim, 255)] * 3
        self._polygon(points, colors)
        self._disc(x, y, radius * 0.42, (34, 26, 20))

    def _pipe(self, points, lit, time):
        """수평·수직 구간으로 이은 파이프. lit이면 금빛이 흐른다."""
        glow, dark = (226, 150, 66), (70, 54, 36)
        segments = list(zip(points, points[1:]))
        for (x1, y1), (x2, y2) in segments:
            left, right = sorted((x1, x2))
            bottom, top = sorted((y1, y2))
            box(left - 2, bottom - 2, right + 2, top + 2, (22, 16, 12))
            box(left - 1, bottom - 1, right + 1, top + 1, glow if lit else dark)
        if not lit:
            return
        lengths = [abs(x2 - x1) + abs(y2 - y1) for (x1, y1), (x2, y2) in segments]
        total = sum(lengths)
        for k in range(3):
            distance = (time * 140 + k * total / 3) % total if total else 0
            for ((x1, y1), (x2, y2)), length in zip(segments, lengths):
                if distance <= length and length:
                    t = distance / length
                    box(x1 + (x2 - x1) * t - 2, y1 + (y2 - y1) * t - 2,
                        x1 + (x2 - x1) * t + 2, y1 + (y2 - y1) * t + 2, (255, 236, 190))
                    break
                distance -= length

    def _draw_puzzle_prop(self, name, x, y, width, height, active=True):
        tint = (255, 255, 255) if active else (120, 120, 135)
        canvas.SDL_SetTextureColorMod(self.puzzle_art.texture, *tint)
        draw_region(self.puzzle_art, PUZZLE_PROPS[name], x - width / 2, y, width, height)
        canvas.SDL_SetTextureColorMod(self.puzzle_art.texture, 255, 255, 255)

    def _draw_wizard_tower_effects(self, time):
        sx = WIDTH * 2 / self.wizard_art.w
        scale_y = 400 / (self.wizard_art.h - 330)
        for floor in range(min(4, len(self.floor_y))):
            y = self.floor_y[floor] + (675 - 570) * scale_y
            for x0, x1 in ((715, 880), (950, 1110), (1180, 1340), (1405, 1555), (1610, 1765)):
                x = x0 * sx - self.camera_x
                width, height = (x1 - x0) * sx, 160 * scale_y
                self._wizard_fx_frame('rain', int(time * 4), x, y, width, height, 115)
                if 9.0 <= time % 18 < 9.5:
                    self._wizard_fx_frame('storm', 12 + int((time % 18 - 9.0) * 4), x, y, width, height, 110)
        if len(self.floor_y) < 5:
            return
        # The arena image is a separate, full-height room; keep rain on its windows.
        arena = self.witch_boss_arena
        arena_y = self.floor_y[4] - 95
        for x0, x1 in ((460, 700), (720, 950), (970, 1200), (1220, 1450), (1470, 1710)):
            x = x0 * WIDTH * 2 / arena.w - self.camera_x
            y = arena_y + (arena.h - 475) * 560 / arena.h
            self._wizard_fx_frame('rain', int(time * 4), x, y,
                                  (x1 - x0) * WIDTH * 2 / arena.w, 310 * 560 / arena.h, 90)
            if 9.0 <= time % 18 < 9.5:
                self._wizard_fx_frame('storm', 12 + int((time % 18 - 9.0) * 4), x, y,
                                      (x1 - x0) * WIDTH * 2 / arena.w, 310 * 560 / arena.h, 90)

    def _draw_map(self, world):
        stage = world.stage
        for floor, y in enumerate(self.floor_y):
            box(31, y + 108, 57, y + 127, INK)
            self.small.draw(34, y + 117, f'{floor + 1}F', MUTED)

        # 분신 퍼즐 장치. 기획서 10~14쪽 그림을 따라 파이프·빛·발판으로 연결 관계가 보이게 그린다.
        cam, floor_y, now = self.camera_x, self.floor_y, world.time
        echo = world.echo.actor if world.echo is not None else None

        if stage.sequence is not None:
            sequence = stage.sequence
            door_x, door_y = sequence.door.x - cam, floor_y[sequence.door.floor]
            for index, sensor in enumerate(sequence.sensors):
                x, y = sensor.x - cam, floor_y[sensor.floor]
                lit = world.sequence_unlocked or index < world.sequence_progress
                # 발판마다 바닥 아래 파이프가 보안문으로 이어진다. 순서대로 밟은 발판의 파이프에 불이 들어온다.
                depth = 10 + index * 7
                end_x = door_x - 16 + index * 16
                self._pipe(((x, y - 4), (x, y - depth), (end_x, y - depth), (end_x, door_y + 4)), lit, now)
                self._draw_puzzle_prop('sensor', x, y - 8, 58, 24, lit)
                self.small.draw(x - 4, y + 24, str(index + 1), CYAN if lit else GOLD)
            draw_grounded(self.gate_art, GATE_FRAMES[world.sequence_unlocked], door_x, door_y, 112)
            for index in range(len(sequence.sensors)):
                lamp = CYAN if world.sequence_unlocked or index < world.sequence_progress else (60, 52, 44)
                self._disc(door_x - 16 + index * 16, door_y + 124, 5, lamp)
            self.small.draw(door_x - 30, door_y + 142, '순서 보안문', CYAN if world.sequence_unlocked else GOLD)

        if stage.sync_gate is not None:
            gate = stage.sync_gate
            door_x, door_y = gate.door.x - cam, floor_y[gate.door.floor]
            junction_x = (door_x + gate.player_sensor.x - cam) / 2
            junction_y = door_y + 40
            for sensor, pressed, label in ((gate.player_sensor, world.sync_pressed[0], '본체 발판'),
                                           (gate.echo_sensor, world.sync_pressed[1], '분신 발판')):
                x, y = sensor.x - cam, floor_y[sensor.floor]
                lit = pressed or world.sync_unlocked
                self._pipe(((x, y + 4), (junction_x, y + 4), (junction_x, junction_y)), lit, now)
                draw_grounded(self.plate_art, PLATE_FRAMES[lit], x, y, 13)
                self.small.draw(x - 28, y + 26, label, CYAN if lit else GOLD)
            self._pipe(((junction_x, junction_y), (door_x + 24, junction_y)), world.sync_unlocked, now)
            self._gear(junction_x, junction_y, 13, now * (5 if world.sync_unlocked else 0.3), all(world.sync_pressed) or world.sync_unlocked)
            draw_grounded(self.gate_art, GATE_FRAMES[world.sync_unlocked], door_x, door_y, 112)
            self.small.draw(door_x - 30, door_y + 125, '동시 발판문', CYAN if world.sync_unlocked else GOLD)

        if stage.hidden_hazards and echo is not None and echo.elevator_target is None:
            # 분신의 빛: 같은 층은 곁을, 바로 위층에서는 아래층 바닥을 원뿔 모양으로 비춘다.
            ex, ey = echo.x - cam, floor_y[echo.floor]
            light = (130, 240, 230)
            if any(h.floor == echo.floor for h in stage.hidden_hazards):
                self._polygon(((ex, ey + 70), (ex - 120, ey), (ex + 120, ey)),
                              ((*light, 90), (*light, 12), (*light, 12)))
            if echo.floor > 0 and any(h.floor == echo.floor - 1 for h in stage.hidden_hazards):
                below = floor_y[echo.floor - 1]
                self._polygon(((ex, ey + 40), (ex - LIGHT_BELOW, below), (ex + LIGHT_BELOW, below)),
                              ((*light, 110), (*light, 18), (*light, 18)))
        for hazard in stage.hidden_hazards:
            if world.hazard_lit(hazard):
                x, y = hazard.x - cam, floor_y[hazard.floor]
                self._draw_puzzle_prop('hazard', x, y - 6, 48, 24)
                self.small.draw(x - 15, y + 24, '가시', RED)

        plate = world.taunt_plate()
        if plate is not None and any(enemy.spawn.point == stage.guard for enemy in world.enemies):
            px, py = plate.x - cam, floor_y[plate.floor]
            gx = stage.guard.x - cam
            taunted = echo is not None and world._near(echo, plate, PLATE_RANGE)
            # 도발 발판은 파이프로 수호자 발밑 톱니에 이어진다. 분신이 서면 톱니가 돌고 수호자가 분신을 노린다.
            self._pipe(((px, py - 8), (gx, py - 8)), taunted, now)
            self._gear(gx, py - 8, 15, now * (5 if taunted else 0.3), taunted)
            draw_grounded(self.plate_art, PLATE_FRAMES[taunted], px, py, 13)
            self.small.draw(px - 28, py - 22, '도발 발판', CYAN if taunted else GOLD)

        if (stage.guard is not None and world.index != 2
                and any(enemy.spawn.point == stage.guard for enemy in world.enemies)):
            x, y = stage.guard.x - cam, floor_y[stage.guard.floor]
            color = CYAN if world.guard_open_time > 0 else RED
            self.small.draw(x - 40, y + 180, '지나가세요!' if world.guard_open_time > 0 else '경비 구간', color)

        if stage.watch_gate is not None:
            gate = stage.watch_gate
            lamp_x = (gate.focus.x + gate.door.x) / 2 - cam
            lamp_y = floor_y[gate.door.floor] + 105
            if world.watch_active and echo is not None:
                # 분신을 따라 빛이 돌아간다. 지키던 길은 어두워진다.
                target_x, target_y, half = echo.x - cam, floor_y[echo.floor], 55
                color = (255, 214, 120)
            else:
                target_x = gate.door.x - cam + sin(now * 1.6) * gate.zone * 0.35
                target_y, half = floor_y[gate.door.floor], gate.zone
                color = (255, 196, 96)
            self._polygon(((lamp_x, lamp_y), (target_x - half, target_y), (target_x + half, target_y)),
                          ((*color, 150), (*color, 34), (*color, 34)))
            self._draw_puzzle_prop('watch', lamp_x, lamp_y - 30, 62, 64, True)
            fx, fy = gate.focus.x - cam, floor_y[gate.focus.floor]
            line(fx - WATCH_RANGE, fy + 2, fx + WATCH_RANGE, fy + 2, CYAN if world.watch_active else PURPLE)
            self.small.draw(fx - 35, fy + 24, '감시 구역', CYAN if world.watch_active else PURPLE)
            dx, dy = gate.door.x - cam, floor_y[gate.door.floor]
            self.small.draw(dx - 40, dy + 150, '빛이 비추는 길' if not world.watch_active else '지나가세요!',
                            GOLD if not world.watch_active else CYAN)

        if stage.isolation is not None:
            room = stage.isolation
            x, y = room.door.x - cam, floor_y[room.door.floor]
            # 레버를 당기면 도르래가 돌며 격리실 철창이 떨어진다.
            moving = min(1.0, (now - world.isolation_changed_at) / 0.28)
            lowered = moving if world.isolation_closed else 1 - moving
            lx, ly = room.lever.x - cam, floor_y[room.lever.floor]
            winch_y = y + 140
            self._pipe(((lx + 12, ly + 14), (x, ly + 14), (x, winch_y)), world.isolation_closed, now)
            draw_grounded(self.gate_art, GATE_FRAMES[True], x, y, 112)
            if lowered > 0.02:
                draw_grounded(self.gate_art, GATE_FRAMES[False], x, y + (1 - lowered) * 112, 112)
            self._gear(x, winch_y, 16, lowered * 9, world.isolation_closed)
            line(x, winch_y, x, y + 112 * (2 - lowered), (70, 70, 80))
            self.small.draw(x - 25, y + 165, '격리실', CYAN if world.isolation_closed else GOLD)
            self._draw_puzzle_prop('lever', lx, ly, 25, 39, world.isolation_closed)
            self.small.draw(lx - 25, ly + 45, 'E 격리', CYAN if world.isolation_closed else GOLD)
            gx, gy = room.exit_gate.x - cam, floor_y[room.exit_gate.floor]
            if world.isolation_closed:
                draw_grounded(self.gate_art, GATE_FRAMES[True], gx, gy, 112)
            else:
                self._draw_puzzle_prop('locked_gate', gx, gy, 90, 112)
            self.small.draw(gx - 25, gy + 125, '보안문', CYAN if world.isolation_closed else GOLD)

        if stage.bridge is not None:
            bridge = stage.bridge
            y = floor_y[bridge.floor]
            left, right = bridge.left - cam, bridge.right - cam
            # 바닥이 없는 낭떠러지. 분신이 지나간 칸에만 빛 발판이 생겼다가 흐려지며 사라진다.
            box(left, y - 90, right, y + 4, (3, 5, 11))
            box(left, y - 90, right, y - 60, (9, 14, 28))
            line(left, y + 4, right, y + 4, (30, 44, 66))
            texture = self.puzzle_art.texture
            for index, remaining in enumerate(world.bridge_tiles):
                if remaining <= 0:
                    continue
                x = bridge.left + (index + 0.5) * bridge.tile - cam
                fade = min(1.0, remaining / 0.6)
                canvas.SDL_SetTextureAlphaMod(texture, round(255 * fade))
                self._draw_puzzle_prop('bridge', x, y - 30 + (1 - fade) * 8, bridge.tile + 6, 34)
                canvas.SDL_SetTextureAlphaMod(texture, 255)
            preview = world.recording.preview if world.recording is not None else None
            if preview is not None and preview.floor == bridge.floor and world.bridge_tile_at(preview.x) is not None:
                # 녹화 중에는 분신이 만들 발판 자리를 점선으로 미리 보여 준다.
                tile = world.bridge_tile_at(preview.x)
                x = bridge.left + tile * bridge.tile - cam
                box(x + 4, y - 4, x + bridge.tile - 4, y, CYAN)
            self.small.draw(left + 10, y + 24, '낭떠러지 · 분신의 빛 발판만 밟을 수 있음', CYAN)

        if stage.lift is not None:
            lift = stage.lift
            wx, px = lift.weight.x - cam, lift.platform.x - cam
            low, high = floor_y[lift.platform.floor], floor_y[lift.platform.floor + 1]
            weighted = echo is not None and world._near(echo, lift.weight, 22)
            progress = world.lift_progress
            platform_y = low + (high - low) * progress
            weight_y = low - 6 * (1 if weighted else 0) - 10 * progress
            # 도르래 저울: 분신이 균형 발판(추)을 누르면 사슬이 당겨져 본체 쪽 발판이 위층으로 오른다.
            pulley_x, pulley_y = (wx + px) / 2, high + 150
            for end_x, end_y in ((wx, weight_y + 22), (px, platform_y + 20)):
                line(pulley_x, pulley_y, end_x, end_y, (92, 92, 104))
                line(pulley_x + 1, pulley_y, end_x + 1, end_y, (40, 40, 48))
            self._gear(pulley_x, pulley_y, 18, progress * 12 + (now * 0.5 if weighted else 0), weighted)
            self._draw_puzzle_prop('lift_weight', wx, weight_y - 3, 60, 25, weighted)
            self.small.draw(wx - 32, weight_y + 26, '균형 발판', CYAN if weighted else GOLD)
            self._draw_puzzle_prop('lift_platform', px, platform_y - 19, 74, 26, weighted or world.lift_riding)
            self.small.draw(px - 22, platform_y + 18, '승강', CYAN if weighted else GOLD)

        for elevator in stage.elevators:
            x = elevator.x - self.camera_x
            low, high = self.floor_y[elevator.lower], self.floor_y[elevator.lower + 1]
            line(x - 27, low, x - 27, high + 75, GOLD)
            line(x + 27, low, x + 27, high + 75, GOLD)
            pixel = world.index == 0
            for floor, y, direction in ((elevator.lower, low, '↑'), (elevator.lower + 1, high, '↓')):
                if pixel:
                    self.pixel_sprites.blit(self.pixel_sprites.prop(('lift',), pixel_sprites.draw_lift), x, y - 16, 1)
                else:
                    self._draw_puzzle_prop('lift_platform', x, y - 18, 70, 24)
                self.small.draw(x - 22, y + 22, f'{direction} 승강', GOLD)
            for actor in (world.player, world.echo.actor if world.echo else None,
                          world.recording.preview if world.recording else None):
                if actor and actor.elevator_target is not None and abs(actor.x - elevator.x) < 1 and min(actor.floor, actor.elevator_target) == elevator.lower:
                    y = self._actor_floor_y(actor)
                    if pixel:
                        self.pixel_sprites.blit(self.pixel_sprites.prop(('lift',), pixel_sprites.draw_lift), x, y - 16, 1)
                    else:
                        self._draw_puzzle_prop('lift_platform', x, y - 18, 70, 24)

        for stair in stage.stairs:
            x = stair.x - self.camera_x
            y = self.floor_y[stair.lower]
            upper = self.floor_y[stair.lower + 1]
            draw_grounded(self.ladder_art, LADDER_FRAME, x, y, upper - y + 8)
            self.small.draw(x + 20, y + 17, '↑', GOLD)
            self.small.draw(x + 20, upper + 17, '↓', GOLD)

        for wall in stage.walls:
            y = self.floor_y[wall.floor]
            x = wall.x - self.camera_x
            box(x - GATE_HALF_WIDTH, y, x + GATE_HALF_WIDTH, y + 119, (42, 61, 82))
            for offset in range(12, 120, 15):
                line(x - GATE_HALF_WIDTH, y + offset, x + GATE_HALF_WIDTH, y + offset, LINE)

        # 그레이박스: 구덩이, 숨은 발판, 외눈 유령 분신의 레이더. 구조가 정해지면 그림으로 바꾼다.
        for floor, left, right in stage.pits:
            y = self.floor_y[floor]
            box(left - self.camera_x, y - 90, right - self.camera_x, y + 2, (8, 6, 16))
        for index, platform in enumerate(stage.platforms):
            if not world.platform_visible(index):
                continue
            y = self.floor_y[platform.floor] + platform.height
            left, right = (edge - self.camera_x for edge in world.platform_span(index))
            # 숨은 발판은 보라색, 늘 보이는 점프맵 발판은 돌색
            fill, edge = ((124, 82, 178), (214, 176, 255)) if platform.hidden else ((88, 92, 112), (150, 156, 178))
            box(left, y - 10, right, y, fill)
            box(left, y - 10, right, y, edge, filled=False)
        if stage.lens is not None:
            # 렌즈 건축물: 놋쇠 테 안의 유리. 켜지면 청록 빛이 방 전체로 퍼진다.
            lens = stage.lens
            x, y = lens.x - self.camera_x, self.floor_y[lens.floor] + lens.height
            box(x - 4, self.floor_y[lens.floor], x + 4, y - 18, (96, 80, 60))
            self._disc(x, y, 20, (150, 118, 64))
            self._disc(x, y, 14, (110, 240, 230) if world.lens_lit else (60, 84, 110))
            if world.lens_lit:
                for i in range(8):
                    a = i / 8 * 6.2832 + world.time
                    line(x + 22 * cos(a), y + 22 * sin(a), x + 60 * cos(a), y + 60 * sin(a), CYAN)
            self.small.draw(x - 14, y + 30, '렌즈', CYAN if world.lens_lit else GOLD)
        for switch, on in zip(stage.switches, world.switched):
            # 공중 턱의 스위치와 그것이 여는 잠긴 문
            sx, sy = switch.x - self.camera_x, self.floor_y[switch.floor] + switch.height
            draw_grounded(self.lever_art, LEVER_FRAMES[on], sx, sy, 34)
            self.small.draw(sx - 22, sy + 45, '스위치', CYAN if on else GOLD)
            if switch.door is None:
                continue   # 출구 포탈 스위치: 문 대신 출구에 포탈이 생긴다
            dx, dy = switch.door.x - self.camera_x, self.floor_y[switch.door.floor]
            draw_grounded(self.gate_art, GATE_FRAMES[on], dx, dy, 112)
            self.small.draw(dx - 22, dy + 124, '열린 문' if on else '잠긴 문', CYAN if on else GOLD)
        if stage.sky:
            self._draw_sky_puzzle(world)
        self._draw_potions(world)
        for actor in world._watchers():
            if actor.radar and actor.elevator_target is None:
                x = actor.x - self.camera_x
                y = self._actor_floor_y(actor) + actor.jump_height + 55
                points, colors = [], []
                for i in range(32):
                    a, b = i / 32 * 6.2832, (i + 1) / 32 * 6.2832
                    points += [(x, y), (x + 220 * cos(a), y + 220 * sin(a)), (x + 220 * cos(b), y + 220 * sin(b))]
                    colors += [(255, 244, 170, 70), (255, 244, 170, 18), (255, 244, 170, 18)]
                self._polygon(points, colors)

        for block in stage.jump_blocks:
            # 점프 블록: 쌓인 돌 더미. 윗면 금색 선이 넘어야 하는 높이다.
            y = self.floor_y[block.floor]
            x, half = block.x - self.camera_x, block.width / 2
            box(x - half, y, x + half, y + block.height, (58, 52, 64))
            box(x - half, y, x + half, y + block.height, (24, 20, 30), filled=False)
            for offset in range(14, block.height, 14):
                shift = 8 if (offset // 14) % 2 else 0
                line(x - half, y + offset, x + half, y + offset, (34, 30, 40))
                line(x - half + 10 + shift, y + offset - 14, x - half + 10 + shift, y + offset, (34, 30, 40))
            line(x - half, y + block.height, x + half, y + block.height, GOLD)

        if stage.poison_zones:
            # 독 웅덩이는 이미지 없이 4px 도트로 찍는다 (poison_fx.py).
            if world.index == 0:
                for floor in sorted({zone[0] for zone in stage.poison_zones}):
                    zones = [zone for zone in stage.poison_zones if zone[0] == floor]
                    y = self.floor_y[floor]
                    box(min(z[1] for z in zones) - self.camera_x, y - 92,
                        max(z[2] for z in zones) - self.camera_x, y, (12, 22, 12))
            self.poison_fx.draw_pool(stage.poison_zones, stage.poison_platforms,
                                     self.floor_y, self.camera_x, world.time,
                                     draw_stone=world.index != 0)
            if world.index == 0:
                for floor in sorted({zone[0] for zone in stage.poison_zones}):
                    zones = [zone for zone in stage.poison_zones if zone[0] == floor]
                    left, right = min(z[1] for z in zones), max(z[2] for z in zones)
                    y = self.floor_y[floor]
                    wall = self.poison_wall_art
                    for x in (left - 16, right):
                        draw_region(wall, (250, 200, 500, 1180), x - self.camera_x,
                                    y - 92, 16, 92)
                    for level, start, end in stage.poison_platforms:
                        if level == floor:
                            art = self.poison_rest_art
                            draw_region(art, (0, 250, art.w, 255), start - self.camera_x,
                                        y - 26, end - start, 28)
            self.poison_fx.draw(stage.poison_zones, self.floor_y, self.camera_x, world.time,
                                [world.player, *world.echo_actors()])

        for beam in stage.web_beams:
            image = self.web_beam_art
            scale = 0.85 if world.index == 0 and beam.floor == 1 else 1.0
            width = (beam.right - beam.left) * scale
            left = (beam.left + beam.right - width) / 2 - self.camera_x
            if world.index == 0:
                height = beam.height * scale
                sprite_width = height
                if beam.floor in (0, 1):
                    chain_bottom = self.floor_y[beam.floor] + beam.underside + height - 4
                    chain_top = self.floor_y[beam.floor] + 308
                    if chain_top > chain_bottom:
                        draw_region(self.statue_chain_art, (400, 0, 224, self.statue_chain_art.h),
                                    left + width / 2 - 5, chain_bottom, 10, chain_top - chain_bottom)
                draw_region(self.pixel_statue_art, (0, 0, self.pixel_statue_art.w, self.pixel_statue_art.h),
                            left + (width - sprite_width) / 2,
                            self.floor_y[beam.floor] + beam.underside, sprite_width, height)
                continue
            draw_region(image, (0, 0, image.w, image.h), left,
                        self.floor_y[beam.floor] + beam.underside,
                        width, beam.height * scale)

        for gate, state in zip(stage.gates, world.doors):
            px, py = gate.plate.x - self.camera_x, self.floor_y[gate.plate.floor]
            gx, gy = gate.door.x - self.camera_x, self.floor_y[gate.door.floor]
            draw_grounded(self.plate_art, PLATE_FRAMES[state.pressed], px, py, 13)
            draw_grounded(self.gate_art, GATE_FRAMES[state.open], gx, gy, 112)
            self.small.draw(px - 23, py - 12, f'{gate.label} 발판', CYAN if state.pressed else GOLD)
            box(gx - 21, gy + 114, gx + 21, gy + 134, PANEL)
            self.small.draw(gx - 15, gy + 124, f'{gate.label} 문', CYAN if state.open else GOLD)
            if gate.lever is not None:
                lx, ly = gate.lever.x - self.camera_x, self.floor_y[gate.lever.floor]
                draw_grounded(self.lever_art, LEVER_FRAMES[state.latched], lx, ly, 34)
                self.small.draw(lx - 20, ly + 45, 'E 레버', CYAN if state.latched else GOLD)

        x, y = stage.exit.x - self.camera_x, self.floor_y[stage.exit.floor]
        if any(switch.door is None for switch in stage.switches):
            # 출구 포탈: 스위치를 누르면 민트색 포탈(pixelfx arcane/portal)이 열린다. 그 전엔 아무것도 없다.
            if world.portal_open:
                draw_sheet(self.attack_fx['portal'], world.time, x, y, 1, 2)
            return
        if world.index == 0:
            frame = int(world.time * 8) % 6
            self.pixel_sprites.blit(self.pixel_sprites.prop(('exit', frame), lambda: pixel_sprites.draw_exit(frame)),
                                    x, y, 1)
        elif stage.sky and world.sky_progress < len(stage.sky.switches):
            draw_grounded(self.gate_art, GATE_FRAMES[0], x, y, 112)   # 세 스위치를 밟기 전엔 닫힌 문
        else:
            draw_grounded(self.exit_art, EXIT_FRAME, x, y, 105)
        locked = any(enemy.spawn.kind in BOSS_KINDS for enemy in world.enemies)
        sky_locked = stage.sky and world.sky_progress < len(stage.sky.switches)
        self.small.draw(x - 35 if locked or sky_locked else x - 15, y + 116,
                        '보스 처치 필요' if locked else '1→2→3 스위치' if sky_locked else '출구',
                        RED if locked or sky_locked else CYAN)

    def _draw_slime_trail(self, world):
        """물약 슬라임이 지나간 자리에 물약 자국을 남긴다. 자국은 PUDDLE_SECONDS 동안 옅어지며 사라진다."""
        for enemy in world.enemies:
            if enemy.spawn.kind == 'potion_slime' and enemy.actor.moving:
                last = self.slime_last.get(id(enemy))
                if last is None or abs(enemy.actor.x - last) >= PUDDLE_GAP:
                    self.slime_last[id(enemy)] = enemy.actor.x
                    self.slime_trail.append((enemy.actor.x, enemy.actor.floor, world.time))
        self.slime_trail = [p for p in self.slime_trail if world.time - p[2] < PUDDLE_SECONDS]
        image = self.slime_puddle
        for x, floor, born in self.slime_trail:
            left = 1 - (world.time - born) / PUDDLE_SECONDS
            canvas.SDL_SetTextureAlphaMod(image.texture, round(255 * min(1.0, left / 0.4)))
            draw_region(image, (0, 0, image.w, image.h), x - self.camera_x - image.w / 2,
                        self.floor_y[floor] - 7, image.w, image.h)   # 바닥 위에 살짝 묻히게
        canvas.SDL_SetTextureAlphaMod(image.texture, 255)

    def _draw_characters(self, world):
        recording = world.recording
        self._draw_slime_trail(world)
        if world.echo is not None:
            self._draw_selected_echo(world.echo.actor, world.echo.monster_kind, 145 if recording else 228)
        for enemy in world.enemies:
            screen_enemy = copy(enemy)
            screen_enemy.actor = self._screen_actor(enemy.actor)
            kind = ENEMY_KINDS[enemy.spawn.kind]
            y = self.floor_y[enemy.actor.floor] + enemy.actor.jump_height
            x = screen_enemy.actor.x
            feet = 0.30 if enemy.spawn.kind in ('beast', 'crawler') else 0.47
            tint = (255, 166, 156) if enemy.flash > 0 else (255, 255, 255)
            pose = attack_pose(enemy.spawn.kind, enemy.windup, enemy.recovery)
            skill_phase = boss_skills.phase(enemy)
            if skill_phase is not None:
                pose = skill_pose(enemy.spawn.kind, *skill_phase)
            if world.index == 0 and enemy.spawn.kind in monster_sprite.KINDS:
                self.stage1_folder_monsters.draw(enemy.spawn.kind, screen_enemy.actor, y, world.time,
                                                enemy.windup, enemy.recovery, tint=tint)
            elif enemy.spawn.kind in monster_sprite.ANYWHERE:   # PixelLab 시트: 이동·공격이 시트 안에 있다
                self.monster_sprite.draw(enemy.spawn.kind, screen_enemy.actor, y, world.time,
                                         enemy.windup, enemy.recovery, tint=tint,
                                         skill=(enemy.skill, *skill_phase) if skill_phase else None)
            elif enemy.spawn.kind == 'echo_knight':
                self._draw_echo_knight(screen_enemy, y, kind.size, skill_phase, tint)
                if skill_phase is None and pose is not None:
                    draw_attack_effect(self.attack_fx, enemy.spawn.kind, x, y, screen_enemy.actor.facing,
                                       enemy.windup, enemy.recovery)
            elif enemy.spawn.kind in late_monster_motion.KINDS:
                image = self.jester_walk if enemy.spawn.kind == 'broken_jester' else self.enemies[enemy.spawn.kind]
                late_monster_motion.draw(image, screen_enemy.actor, y, kind.size, world.time,
                                         enemy.spawn.kind, pose, tint)
                if pose is not None:
                    draw_attack_effect(self.attack_fx, enemy.spawn.kind, x, y, screen_enemy.actor.facing,
                                       enemy.windup, enemy.recovery)
            elif pose is not None:
                # 공격 중에는 monster_attack.py의 자세 스크립트대로 그린다.
                actor = screen_enemy.actor
                walk = self.enemy_walk.get(enemy.spawn.kind)
                if isinstance(walk, MonsterWalk):
                    actor.x += actor.facing * pose.dx
                    walk.draw(actor, y + pose.dy, faces=-1, tint=tint, lean=pose.angle)
                elif walk is not None:
                    frame = walk.frames[int(actor.walk_distance / walk.stride_per_frame) % len(walk.frames)]
                    draw_posed(walk.image, frame, x, y, walk.draw_height, actor.facing, pose, tint)
                else:
                    image = self.enemies[enemy.spawn.kind]
                    draw_posed(image, (0, 0, image.w, image.h), x, y, kind.size, actor.facing, pose, tint)
                draw_attack_effect(self.attack_fx, enemy.spawn.kind, x, y, actor.facing, enemy.windup, enemy.recovery)
            elif enemy.spawn.kind in ('jailer_boss', 'magic_armor', 'magic_armor_guard', 'witch', 'grand_witch'):
                self.enemy_walk[enemy.spawn.kind].draw(screen_enemy.actor, y, faces=-1, tint=tint)
            elif enemy.actor.moving and enemy.spawn.kind in self.enemy_walk:
                self.enemy_walk[enemy.spawn.kind].draw(
                    screen_enemy.actor, y, faces=-1, tint=tint,
                )
            else:
                self._sprite(self.enemies[enemy.spawn.kind], screen_enemy.actor, kind.size, world.time, feet=feet, faces=-1, tint=tint)
            # 머리 위에 이름과 체력바. 벨 수 없는 적은 이름만 흐리게 보인다.
            boss = enemy.spawn.kind in BOSS_KINDS
            bar_y = y + (kind.size + 25 if enemy.spawn.kind in late_monster_motion.KINDS
                         else kind.size + 8 if boss else 73 if feet == 0.30 else 103)
            half = 45 if boss else 24
            if enemy.health is not None:
                box(x - half - 1, bar_y - 1, x + half + 1, bar_y + 5, INK)
                box(x - half, bar_y, x - half + 2 * half * min(1, enemy.health / enemy.max_health), bar_y + 4, RED if boss else PURPLE)
            name = MONSTER_NAMES[enemy.spawn.kind]
            self.small.draw(x - text_width(self.small, name) / 2, bar_y + 14, name,
                            GOLD if boss else WHITE if enemy.health is not None else MUTED)
            if enemy.target is not None:
                color = RED if enemy.windup > 0 else CYAN if world.echo and enemy.target is world.echo.actor else GOLD
                self.small.draw(x - 3, bar_y + 32, '!', color)

        for x, floor, age, text, on_player in world.damage_texts:
            # 피해 숫자는 위로 떠오르며 사라진다. 받은 피해는 빨간색이다.
            font = self.heading if on_player else self.body
            y = self.floor_y[floor] + (120 if on_player else 95) + age * 40
            screen_x = x - self.camera_x - text_width(font, text) / 2
            font.draw(screen_x + 1, y - 1, text, INK)
            font.draw(screen_x, y, text, RED if on_player else WHITE)
        self._draw_boss_bar(world)

        for effect in world.boss_effects:
            if effect.age < 0:
                continue
            x, y = effect.x - self.camera_x, self.floor_y[effect.floor] + effect.lift
            if effect.drop:
                # 낙석: 점점 빨라지며 떨어지고, 떨어질 자리에 그림자가 커진다.
                fall = min(1, effect.age / effect.life)
                box(x - 8 - 26 * fall, y - 3, x + 8 + 26 * fall, y + 3, (0, 0, 0, round(70 + 110 * fall)))
                y += effect.drop * (1 - fall * fall)
            draw_sheet(self.attack_fx[effect.sheet], effect.age, x, y, effect.facing, effect.scale)

        field = world.gravity_field
        if field is not None:
            x = field.x - self.camera_x
            y = self.floor_y[field.floor]
            warning = field.age < field.warning
            if warning:
                line(x - field.radius, y + 3, x + field.radius, y + 3, PURPLE)
                self.small.draw(x - 28, y + 30, '중력 예고', PURPLE)
            draw_sheet(self.attack_fx['black-hole'], field.age, x, y, 1, 1.6,
                       100 if warning else 255)
            if field.captured:
                self.small.draw(x - 80, y + 130, '반대 방향키로 탈출!', WHITE)

        player_alpha = 170 if recording else 255
        if world.invulnerable > 0 and int(world.time * 18) % 2:
            player_alpha = 130
        player = self._screen_actor(world.player)
        normal_floors = self.floor_y
        if world.lift_riding:
            lower = world.stage.lift.platform.floor
            floors = list(self.floor_y)
            floors[lower] += (floors[lower + 1] - floors[lower]) * world.lift_progress
            self.floor_y = tuple(floors)
        floor = self._actor_floor_y(world.player) + world.player.jump_height
        attack = None
        if world.attack_flash > 0:
            attack = (world.attack_kind, 1 - world.attack_flash / world.attack_duration)
        self.hero_sprite.draw(player, floor, world.weapon_index, player_alpha, world.time, attack)
        player_attack.draw_attack_effect(
            self.attack_fx, world.attack_kind, world.attack_age, world.attack_duration,
            WEAPONS[world.weapon_index].reach, player.x, floor, player.facing)
        for spark_x, spark_floor, age in world.hit_sparks:
            player_attack.draw_hit_spark(self.attack_fx, age, spark_x - self.camera_x,
                                         self.floor_y[spark_floor], world.player.facing)
        self.floor_y = normal_floors
        if recording is not None:
            actor = self._screen_actor(recording.preview)
            self._draw_selected_echo(recording.preview, recording.monster_kind)
            marker = 'REC'
        else:
            actor = player
            marker = 'YOU'
        x, y = actor.x, self._actor_floor_y(actor) + actor.jump_height + 104
        color = CYAN if recording else WHITE
        box(x - 19, y - 7, x + 19, y + 13, INK)
        self.small.draw(x - 15, y + 3, marker, color)

    def _draw_selected_echo(self, actor, monster_kind, opacity=228):
        world_actor = actor
        actor = self._screen_actor(actor)
        pixel = self.current_world is not None and self.current_world.index == 0
        if monster_kind is None:   # 기본 분신은 모든 스테이지에서 PixelLab 주인공의 은빛 시트
            self.hero_sprite.draw(actor, self._actor_floor_y(actor) + actor.jump_height,
                                  2, opacity, self.animation_time, echo=True)
            return
        if monster_kind not in self.monster_echo_walk:
            self._avatar(self.echo, self.echo_walk, actor, opacity=255)
            return
        floor = self._actor_floor_y(actor) + actor.jump_height
        if monster_kind == 'beast' and actor.beast_charge_active:
            # 슈퍼 점프를 모으는 동안 공격 준비 칸(머리를 낮추고 웅크림)을 모은 만큼 보여 준다. 날아가는 동안은 아래에서 그린다.
            windup = monster_sprite.WINDUP * max(0.01, 1 - actor.beast_charge)
            self.monster_sprite.draw('beast', actor, floor, self.animation_time, windup=windup,
                                     opacity=opacity, echo=True)
            return
        if monster_kind == 'crawler' and actor.web_time > 0 and not actor.web_flying:
            # 천장에 붙인 거미줄. 감으면 짧아지고 몸이 올라간다.
            anchor_x = actor.web_anchor_x - self.camera_x
            anchor_y = self._actor_floor_y(actor) + actor.web_anchor_height + 34
            line(anchor_x, anchor_y, actor.x, floor + 34, WHITE)
            line(anchor_x + 1, anchor_y, actor.x + 1, floor + 34, MUTED)
            box(anchor_x - 4, anchor_y - 2, anchor_x + 4, anchor_y + 4, WHITE)
        if monster_kind == 'crawler' and actor.web_aiming:
            target = self.current_world.spider_web_target(world_actor, actor.web_aim_x)
            if target:
                tx, ty, color = target[0] - self.camera_x, self._actor_floor_y(actor) + target[1], GOLD
            else:
                scale = SPIDER_AIM_REACH / (2 ** 0.5 if actor.web_aim_x else 1)
                tx, ty, color = actor.x + actor.web_aim_x * scale, floor + 34 + scale, RED
            for index in range(0, 12, 2):
                a, b = index / 12, (index + 1) / 12
                line(actor.x + (tx - actor.x) * a, floor + 34 + (ty - floor - 34) * a,
                     actor.x + (tx - actor.x) * b, floor + 34 + (ty - floor - 34) * b, color)
            box(tx - 4, ty - 4, tx + 4, ty + 4, color)
        if pixel and monster_kind in monster_sprite.KINDS or monster_kind in monster_sprite.ANYWHERE:
            self.monster_sprite.draw(monster_kind, actor, floor, self.animation_time,
                                     opacity=opacity, echo=True)
            return
        faces = 1 if monster_kind == 'broken_jester' else -1
        walk = self.monster_echo_walk[monster_kind]
        # 거미 시트의 발 아래 투명 여백만큼 내려 바닥에 발을 맞춘다.
        draw_floor = floor - walk.draw_height * 0.21 if monster_kind == 'crawler' else floor
        if monster_kind == 'beast':
            frame = int(actor.walk_distance / walk.stride_per_frame) % len(walk.frames)
            foot_rows = (350, 349, 348, 348, 340, 345, 349, 350)
            draw_floor -= walk.draw_height * (443 - foot_rows[frame]) / 443
        walk.draw(actor, draw_floor, opacity=opacity, faces=faces)

    def _draw_echo_knight(self, enemy, floor_y, size, skill_phase, tint):
        actor = enemy.actor
        if skill_phase is not None:
            name = enemy.skill
            phase, progress = skill_phase
            if phase == 'telegraph':
                frame = min(2, int(progress * 3))
            elif phase == 'active':
                frame = 3 + min(2, int(progress * 3))
            else:
                frame = 6 + min(1, int(progress * 2))
        elif enemy.windup > 0:
            name = 'attack'
            frame = min(3, max(0, int((1 - enemy.windup / 0.31) * 4)))
        elif enemy.recovery > 0:
            name = 'attack'
            frame = 4 + min(3, max(0, int((1 - enemy.recovery / 0.65) * 4)))
        else:
            name = 'walk'
            frame = int(actor.walk_distance / 9) % 16 if actor.moving else 0

        image = self.knight_sheets[name]
        columns, rows = (4, 4) if name == 'walk' else (4, 2)
        width, height = image.w // columns, image.h // rows
        region = ((frame % columns) * width, (frame // columns) * height, width, height)
        draw_width = size * width / height
        canvas.SDL_SetTextureColorMod(image.texture, *tint)
        draw_region(image, region, actor.x - draw_width / 2, floor_y, draw_width, size,
                    flip=actor.facing != -1)
        canvas.SDL_SetTextureColorMod(image.texture, 255, 255, 255)

    def _screen_actor(self, actor):
        screen_actor = copy(actor)
        screen_actor.x -= self.camera_x
        return screen_actor

    def _actor_floor_y(self, actor):
        if actor.elevator_target is None:
            return self.floor_y[actor.floor]
        start = self.floor_y[actor.floor]
        end = self.floor_y[actor.elevator_target]
        return start + (end - start) * abs(actor.elevator_offset)

    def _avatar(self, idle, walk, actor, opacity=255, jump_art=None):
        if actor.jump_time > 0:
            if jump_art is None:
                jump_art = self.echo_jump_art
            progress = min(7.999, actor.jump_time * 8 / JUMP_DURATION)
            phase = int(progress)
            # Blend briefly into the next pose instead of abruptly replacing it.
            blend = max(0.0, (progress - phase - 0.65) / 0.35) if phase < 7 else 0.0
            self._draw_jump_pose(actor, JUMP_POSE_ORDER[phase], opacity, jump_art)
            if blend:
                self._draw_jump_pose(actor, JUMP_POSE_ORDER[phase + 1], round(opacity * blend), jump_art)
        elif actor.moving:
            walk.draw(actor, self._actor_floor_y(actor) - (4 if idle is self.echo else 0), opacity)
        else:
            breathing = sin(self.animation_time * 2.1) * 1.5
            self._sprite(idle, actor, 91 + breathing, 0, opacity=opacity)

    def _draw_jump_pose(self, actor, index, opacity, image):
        region = JUMP_FRAMES[index]
        scale = 91 / 406
        width, height = region[2] * scale, region[3] * scale
        face_offset = (JUMP_FACE_X[index] - region[0]) * scale - width / 2
        face_alignment = (7 - face_offset) * actor.facing
        left = actor.x - width / 2 + face_alignment
        bottom = self._actor_floor_y(actor) + actor.jump_height + JUMP_HEAD_LIFT[index]
        flip = actor.facing < 0
        # 분신 시트의 망토 끝·빛 번짐은 몸 둘레 영역 밖으로 나간다. 같은 비율로 프레임 칸 전체를 그려 잘리지 않게 한다.
        cell_w, cell_h = image.w // 4, image.h // 2
        cell_x, cell_y = index % 4 * cell_w, index // 4 * cell_h
        pad_left, pad_right = region[0] - cell_x, cell_x + cell_w - region[0] - region[2]
        pad_bottom = cell_y + cell_h - region[1] - region[3]
        left -= (pad_right if flip else pad_left) * scale
        bottom -= pad_bottom * scale
        region = (cell_x, cell_y, cell_w, cell_h)
        width, height = cell_w * scale, cell_h * scale
        canvas.SDL_SetTextureAlphaMod(image.texture, opacity)
        draw_region(image, region, left, bottom, width, height, flip)
        canvas.SDL_SetTextureAlphaMod(image.texture, 255)

    def _sprite(self, image, actor, size, time, feet=0.49, faces=1, opacity=255, tint=(255, 255, 255)):
        bob = abs(sin(time * 21)) * 4 if actor.moving else 0
        canvas.SDL_SetTextureAlphaMod(image.texture, opacity)
        canvas.SDL_SetTextureColorMod(image.texture, *tint)
        image.composite_draw(0, 'h' if actor.facing != faces else '', actor.x,
                             self._actor_floor_y(actor) + size * feet + bob, size, size)
        canvas.SDL_SetTextureColorMod(image.texture, 255, 255, 255)
        canvas.SDL_SetTextureAlphaMod(image.texture, 255)

    def _draw_hud(self, world):
        box(0, 625, WIDTH, HEIGHT, INK)
        line(28, 626, WIDTH - 28, 626, LINE)
        # 왼쪽 위: 레벨, 체력바, 경험치바
        # Use the concept artwork for the portrait and frames; draw live values on top.
        draw_region(self.hud_concept, (30, 80, 360, 400), 27, 632, 76, 84)
        draw_region(self.hud_concept, (380, 210, 850, 110), 105, 668, 220, 30)
        draw_region(self.hud_concept, (390, 319, 750, 48), 108, 648, 210, 17)
        health, top = world.health, world.max_health
        health_ratio = max(0.0, min(1.0, health / top if top else 0.0))
        # 체력이 30% 아래면 빨간 막대가 깜빡인다.
        danger = health < top * 0.3 and int(perf_counter() * 4) % 2
        self._fill_bar((380, 210, 850, 110), (105, 668, 220, 30), HUD_HP_INNER,
                       HUD_HP_FILL, health_ratio, 120 if danger else 255)
        label = f'HP  {health} / {top}'
        self.small.draw(213 - text_width(self.small, label) / 2, 682, label, WHITE)
        self.small.draw(110, 708, f'Lv.{world.level}', GOLD)
        gained, needed = world.xp_progress()
        xp_ratio = max(0.0, min(1.0, gained / needed if needed else 1.0))
        self._fill_bar((390, 319, 750, 48), (108, 648, 210, 17), HUD_XP_INNER, HUD_XP_FILL, xp_ratio)
        self.small.draw(118, 638, f'EXP  {gained} / {needed}' if needed else 'EXP  MAX', MUTED)
        self._draw_minimap(world)
        self.small.draw(340, 684, '상태', MUTED)
        color, label = (CYAN, '녹화 중 · 게임 진행') if world.recording else (WHITE, '본체 조작 · 일반 진행')
        self.body.draw(340, 653, label, color)
        self.small.draw(557, 684, '무기', MUTED)
        self.small.draw(557, 653, WEAPONS[world.weapon_index].name, GOLD)
        if world.recording is not None:
            seconds = len(world.recording.inputs) * STEP
            limit = world.stage.echo_seconds
            value = seconds / limit
            status = f'{seconds:04.1f} / {limit:g}초'
        elif world.echo is not None:
            remaining = len(world.echo.inputs) - world.echo.cursor
            value = remaining / len(world.echo.inputs)
            status = f'분신 재현 {remaining * STEP:.1f}초 남음'
        else:
            value = 0
            status = 'C 키로 분신 녹화'
        self.small.draw(650, 684, status, CYAN if value else MUTED)
        box(650, 648, 881, 657, PANEL)
        if value > 0:
            box(650, 648, 650 + 231 * value, 657, CYAN)

        box(0, 0, WIDTH, 104, INK)
        line(28, 103, WIDTH - 28, 103, LINE)
        if world.message_time > 0:
            self.body.draw((WIDTH - text_width(self.body, world.message)) / 2, 52, world.message, GOLD)
        if world.revealed and world.reveal_time < world.stage.reveal_seconds:
            label = f'발판 사라지기까지 {world.reveal_time:.1f}초'
            self.body.draw((WIDTH - text_width(self.body, label)) / 2, 150, label,
                           RED if world.reveal_time < 3 else GOLD)
        if world.recording is not None and world.recording.monster_kind in MONSTER_NAMES:
            # C로 몬스터 분신을 녹화하는 동안은 어떤 분신인지만 작게 보여 준다.
            label = f'C  {MONSTER_NAMES[world.recording.monster_kind]} 분신'
            width = text_width(self.small, label)
            box((WIDTH - width) / 2 - 12, 112, (WIDTH + width) / 2 + 12, 136, (7, 14, 27, 200))
            self.small.draw((WIDTH - width) / 2, 124, label, CYAN)

    def _draw_boss_bar(self, world):
        boss = next((enemy for enemy in world.enemies if enemy.spawn.kind in BOSS_KINDS
                     and enemy.actor.floor == world.player.floor), None)
        if boss is None:
            return
        image = self.boss_bars[boss.spawn.kind]
        left, bottom, width = 310, 454, 500
        height = width * image.h / image.w
        scale = width / image.w
        draw_region(image, (0, 0, image.w, image.h), left, bottom, width, height)
        if boss.spawn.kind == 'echo_knight':
            name = MONSTER_NAMES[boss.spawn.kind]
            self.small.draw(left + width / 2 - text_width(self.small, name) / 2,
                            bottom + height * 0.67, name, GOLD)

        # Darken the original bar texture to make an empty track, then reveal the
        # same red pixels in proportion to the current health.
        bar_x, bar_y, bar_width, bar_height = 183, 355, 1806, 96
        x = left + bar_x * scale
        y = bottom + (image.h - bar_y - bar_height) * scale
        canvas.SDL_SetTextureColorMod(image.texture, 55, 48, 56)
        draw_region(image, (bar_x, bar_y, bar_width, bar_height), x, y,
                    bar_width * scale, bar_height * scale)
        canvas.SDL_SetTextureColorMod(image.texture, 255, 255, 255)
        ratio = max(0.0, min(1.0, boss.health / boss.max_health if boss.max_health else 0.0))
        filled = round(bar_width * ratio)
        if filled:
            draw_region(image, (bar_x, bar_y, filled, bar_height), x, y,
                        filled * scale, bar_height * scale)
        label = f'{boss.health} / {boss.max_health}'
        self.small.draw(left + width / 2 - text_width(self.small, label) / 2,
                        y + bar_height * scale / 2, label, WHITE)

    def _fill_bar(self, frame, target, inner, fill, ratio, alpha=255):
        """HUD 이미지의 막대 안쪽을 빈 홈 픽셀로 덮고, 채움 픽셀을 ratio만큼 이어 붙인다.

        frame은 원본에서 잘라 target(left, bottom, width, height)에 그린 영역이다.
        inner는 원본 좌표의 막대 안쪽 (left, top, right, bottom)이다.
        """
        scale_x, scale_y = target[2] / frame[2], target[3] / frame[3]
        left, top, right, bottom = inner
        x = target[0] + (left - frame[0]) * scale_x
        y = target[1] + (frame[1] + frame[3] - bottom) * scale_y
        width, height = (right - left) * scale_x, (bottom - top) * scale_y
        self._tile_hud(HUD_EMPTY, x, y, width, height, scale_x)
        if ratio > 0:
            self._tile_hud(fill, x, y, width * ratio, height, scale_x, alpha)

    def _tile_hud(self, source, x, y, width, height, scale, alpha=255):
        """원본 픽셀 조각을 원래 가로 비율 그대로 반복해서 가로로 채운다. 마지막 조각은 잘린다."""
        texture = self.hud_concept.texture
        canvas.SDL_SetTextureAlphaMod(texture, alpha)
        step = source[2] * scale
        done = 0.0
        while width - done > 0.5:
            part = min(step, width - done)
            start, end = round(x + done), round(x + done + part)  # 정수 경계라 조각 사이에 틈이 없다.
            if end > start:
                crop = max(1, round(source[2] * part / step))
                draw_region(self.hud_concept, (source[0], source[1], crop, source[3]),
                            start, y, end - start, height)
            done += part
        canvas.SDL_SetTextureAlphaMod(texture, 255)

    def _draw_minimap(self, world):
        """????? ?? ?? ???? ??? ???? ????."""
        stage = world.stage
        left, width, row = 32, 210, 16
        top = 614
        bottom = top - stage.floors * row - 10
        scale = (width - 20) / (RIGHT - LEFT)

        def spot(point_x, floor):
            # ? ??? ??? ???? ?? ??? ?? ??? ???.
            x = max(LEFT, min(RIGHT, point_x))
            return left + 10 + (x - LEFT) * scale, bottom + 7 + floor * row

        def marker(point, color, size=2):
            x, y = spot(point.x, point.floor)
            box(x - size, y + 1, x + size, y + 1 + size * 2, color)

        box(left, bottom, left + width, top, (7, 14, 27, 225))
        box(left, bottom, left + width, top, LINE, filled=False)
        for floor in range(stage.floors):
            _, y = spot(LEFT, floor)
            # ?? ????? ? ?? ?? ??? ?? ??? ????.
            line(left + 10, y, left + width - 10, y, MUTED)

        # ???? ???? ??? ? ? ??? ????.
        for stair in stage.stairs:
            x, y = spot(stair.x, stair.lower)
            line(x, y, x, y + row, GOLD)
            line(x - 2, y + row / 2, x + 2, y + row / 2, GOLD)
        for elevator in stage.elevators:
            x, y = spot(elevator.x, elevator.lower)
            line(x, y, x, y + row, CYAN)
            box(x - 2, y + row / 2 - 1, x + 2, y + row / 2 + 1, CYAN)

        for wall in stage.walls:
            x, y = spot(wall.x, wall.floor)
            line(x, y, x, y + 8, MUTED)
        for block in stage.jump_blocks:
            x, y = spot(block.x, block.floor)
            line(x, y, x, y + 5, GOLD)
        for gate, state in zip(stage.gates, world.doors):
            marker(gate.plate, GOLD)
            if gate.lever is not None:
                marker(gate.lever, PURPLE)
            x, y = spot(gate.door.x, gate.door.floor)
            line(x, y, x, y + 9, CYAN if state.open else GOLD)

        # ?? ??? ??? ?? ? ???? ????? ????.
        if stage.sequence:
            for sensor in stage.sequence.sensors:
                marker(sensor, GOLD)
            marker(stage.sequence.door, CYAN if world.sequence_unlocked else GOLD)
        if stage.sync_gate:
            marker(stage.sync_gate.player_sensor, GOLD)
            marker(stage.sync_gate.echo_sensor, CYAN)
            marker(stage.sync_gate.door, CYAN if world.sync_unlocked else GOLD)
        if stage.watch_gate:
            marker(stage.watch_gate.focus, PURPLE)
            marker(stage.watch_gate.door, CYAN if world.watch_active else GOLD)
        if stage.isolation:
            marker(stage.isolation.lever, PURPLE)
            marker(stage.isolation.door, GOLD)
            marker(stage.isolation.exit_gate, GOLD)
        if stage.bridge:
            for x in range(stage.bridge.left, stage.bridge.right, stage.bridge.tile):
                marker(Point(x + stage.bridge.tile / 2, stage.bridge.floor), (40, 60, 90), 1)
        if stage.lift:
            marker(stage.lift.platform, CYAN)
            marker(stage.lift.weight, GOLD)

        marker(stage.exit, CYAN, 3)
        for enemy in world.enemies:
            x, y = spot(enemy.actor.x, enemy.actor.floor + enemy.actor.elevator_offset)
            size = 3 if enemy.spawn.kind in BOSS_KINDS else 2
            box(x - size, y + 1, x + size, y + 1 + size * 2, RED)
        if world.echo is not None:
            actor = world.echo.actor
            x, y = spot(actor.x, actor.floor + actor.elevator_offset)
            box(x - 2, y + 1, x + 2, y + 5, CYAN)
        if world.recording is not None:
            actor = world.recording.preview
            x, y = spot(actor.x, actor.floor + actor.elevator_offset)
            box(x - 2, y + 1, x + 2, y + 5, CYAN, filled=False)
        actor = world.player
        x, y = spot(actor.x, actor.floor + actor.elevator_offset)
        blink = 1 if int(perf_counter() * 3) % 2 else 0
        box(x - 3 - blink, y, x + 3 + blink, y + 6 + blink, WHITE)
        box(x - 3 - blink, y, x + 3 + blink, y + 6 + blink, INK, filled=False)

    def _draw_title(self, menu):
        if menu.page == 'controls':
            self._draw_guide(menu)
            return
        if menu.page == 'settings':
            self._draw_settings(menu)
            return
        if menu.page == 'main':
            self.title_screen_echo.draw(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT)
            now = perf_counter()
            elapsed = min(0.1, max(0.0, now - self.title_button_updated_at))
            self.title_button_updated_at = now
        else:
            height = WIDTH * self.title_art.h / self.title_art.w
            self.title_art.draw(WIDTH / 2, HEIGHT / 2, WIDTH, height)
            box(0, 0, WIDTH, HEIGHT, (2, 8, 17, 215))
            line(90, 640, 175, 640, CYAN)
            self.heading.draw(90, 610, PAGE_TITLES[menu.page], WHITE)
        for index, (action, label, (left, bottom, right, top)) in enumerate(menu.buttons()):
            chosen = index == menu.index
            middle = (bottom + top) / 2
            if menu.page == 'main':
                target = 1.08 if chosen else 1.0
                scale = self.title_button_scales[index]
                scale += (target - scale) * min(1.0, elapsed * 12)
                self.title_button_scales[index] = scale
                canvas.SDL_SetTextureAlphaMod(self.title_button_gold.texture, 255 if chosen else 165)
                self.title_button_gold.draw((left + right) / 2, middle,
                                            (right - left) * scale, (top - bottom) * scale)
                canvas.SDL_SetTextureAlphaMod(self.title_button_gold.texture, 255)
                width = text_width(self.body, label)
                self.body.draw((left + right - width) / 2, middle, label, WHITE if chosen else MUTED)
                continue
            box(left, bottom, right, top, (23, 60, 71) if chosen else PANEL)
            box(left, bottom, right, top, CYAN if chosen else LINE, filled=False)
            if action.startswith('stage:'):
                number, name = label.split(maxsplit=1)
                self.display.draw(left + 16, top - 40, number, CYAN if chosen else WHITE)
                self.small.draw(left + 16, bottom + 24, name, WHITE if chosen else MUTED)
            elif action == 'fullscreen':
                self.body.draw(left + 20, middle, label, WHITE)
                value = '전체 화면' if menu.fullscreen else '창 모드'
                self.body.draw(right - 170, middle, f'◀  {value}  ▶', CYAN if chosen else GOLD)
            else:
                self.body.draw(left + 20, middle, label, CYAN if chosen else MUTED)
        if menu.page != 'main':
            self.small.draw(62, 26, '↑ ↓ ← →  선택     Enter  결정     Esc  뒤로     마우스로 가리키고 클릭', MUTED)

    def _draw_settings(self, menu):
        self.settings_background.draw(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT)
        self.heading.draw(245, 605, '설정', WHITE)
        self.body.draw(245, 464, '전체 음량', WHITE)
        box(530, 458, 730, 470, (36, 46, 59))
        if menu.volume:
            box(530, 458, 530 + 2 * menu.volume, 470, GOLD)
        value = '음소거' if menu.muted else f'{menu.volume}%'
        self.body.draw(835, 464, value, MUTED if menu.muted else WHITE)
        for index, (action, label, (left, bottom, right, top)) in enumerate(menu.buttons()):
            selected = index == menu.index
            canvas.SDL_SetTextureAlphaMod(self.title_button_gold.texture, 255 if selected else 160)
            self.title_button_gold.draw((left + right) / 2, (bottom + top) / 2,
                                        (right - left) * (1.04 if selected else 1), top - bottom)
            canvas.SDL_SetTextureAlphaMod(self.title_button_gold.texture, 255)
            if action == 'mute':
                label = '음소거  :  켜짐' if menu.muted else '음소거  :  꺼짐'
            elif action == 'fullscreen':
                label = '화면 모드  :  전체 화면' if menu.fullscreen else '화면 모드  :  창 모드'
            width = text_width(self.body, label)
            self.body.draw((left + right - width) / 2, (bottom + top) / 2,
                           label, WHITE if selected else MUTED)
        self.small.draw(245, 195, '현재 게임에는 배경음과 효과음이 아직 없습니다.', MUTED)
        self.small.draw(245, 165, '음량 선택 후 좌우 방향키 또는 + / − 클릭', MUTED)

    def _draw_guide(self, menu):
        self.guide_background.draw(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT)
        self.heading.draw(85, 635, '게임 안내 및 조작법', WHITE)
        for index, (action, label, (left, bottom, right, top)) in enumerate(menu.buttons()):
            selected = index == menu.index
            active = action == f'guide:{menu.guide_page}'
            middle = (bottom + top) / 2
            canvas.SDL_SetTextureAlphaMod(self.title_button_gold.texture, 255 if active or selected else 145)
            scale = 1.05 if selected else 1.0
            self.title_button_gold.draw((left + right) / 2, middle,
                                        (right - left) * scale, (top - bottom) * scale)
            canvas.SDL_SetTextureAlphaMod(self.title_button_gold.texture, 255)
            width = text_width(self.small, label)
            self.small.draw((left + right - width) / 2, middle, label, WHITE if active or selected else MUTED)

        if menu.guide_page == 0:
            for i, (keys, what) in enumerate(CONTROLS):
                col, row = divmod(i, 6)
                x, y = 105 + col * 480, 480 - row * 52
                self.body.draw(x, y, keys, GOLD)
                self.body.draw(x + 140, y, what, WHITE)
        elif menu.guide_page == 1:
            lines = (
                ('분신 녹화', 'C로 행동을 녹화합니다. 녹화 중에도 적과 장치가 움직입니다.'),
                ('분신 재현', '녹화한 움직임이 재현되는 동안 본체를 따로 조작하세요.'),
                ('분신 피격', '분신이 맞으면 사라지지 않고 피해의 30%가 본체에 전달됩니다.'),
                ('함께 돌파', '분신으로 발판을 누르고 적을 유인하거나 감지 장치를 작동하세요.'),
                ('전투와 출구', 'A는 강한 근거리 베기, S는 약하지만 더 긴 찌르기입니다.'),
                ('몬스터 분신', '일반 몬스터 분신은 최대 2종 보유하며 기본 분신은 항상 사용할 수 있습니다.'),
                ('거미 분신', 'F를 누르고 방향을 정한 뒤 떼어 발사합니다. Space로 줄을 놓습니다.'),
                ('알아두기', '다른 몬스터 고유 능력은 아직 없으며 보스는 분신으로 얻을 수 없습니다.'),
            )
            for row, (label, description) in enumerate(lines):
                y = 490 - row * 50
                self.body.draw(105, y, label, GOLD)
                self.small.draw(260, y, description, WHITE)
        else:
            groups = (
                (('crawler', '거미형 적. 감옥 통로를 순찰합니다.'),
                 ('beast', '빠르게 추격하는 뿔짐승입니다.'),
                 ('watcher', '감옥 구역을 순찰하는 외눈 적입니다.'),
                 ('warden', '돌로 된 몸을 가진 수호자입니다.'),
                 ('jailer_boss', '보스. 쇠사슬, 낙석, 돌진을 사용합니다.')),
                (('magic_book', '성을 순찰하는 마법책입니다.'),
                 ('potion_slime', '물약 모양의 슬라임입니다.'),
                 ('magic_armor', '마법으로 움직이는 갑옷입니다.'),
                 ('magic_armor_guard', '격리실로 유인할 수 있는 갑옷 경비병입니다.'),
                 ('witch', '마법사의 성에 있는 마녀입니다.'),
                 ('grand_witch', '보스. 중력장, 낙뢰, 마력 구체를 사용합니다.')),
                (('time_thief', '후반 구역을 지키는 시간 도둑입니다.'),
                 ('cursed_lantern', '후반 구역을 순찰하는 저주받은 등불입니다.'),
                 ('broken_jester', '후반 구역을 순찰하는 광대 인형입니다.'),
                 ('echo_knight', '보스. 돌진, 마력 구체, 낙뢰를 사용합니다.')),
            )
            for i, (kind, description) in enumerate(groups[menu.guide_page - 2]):
                col, row = i % 2, i // 2
                x, y = 95 + col * 485, 475 - row * 105
                image = self.enemies[kind]
                image.draw(x + 35, y, 68, 78)
                self.body.draw(x + 85, y + 16, MONSTER_NAMES.get(kind, '갑옷 경비병'), GOLD)
                self.small.draw(x + 85, y - 14, description, WHITE)
            self.small.draw(100, 145, '일반 몬스터 분신: 외형이 바뀌며 기본 분신과 같은 기능을 사용합니다.', MUTED)
            self.small.draw(100, 119, '거미 분신: F 누른 채 방향 조준, 떼면 발사 · Space 줄 놓기 / 보스 획득 불가', MUTED)

    def draw_echo_selector(self, world):
        box(0, 0, WIDTH, HEIGHT, (2, 8, 17, 188))
        self.echo_selection_panel.draw(WIDTH / 2, HEIGHT / 2, 1000, 510)
        heading = '분신 선택'
        self.heading.draw((WIDTH - text_width(self.heading, heading)) / 2, 554, heading, WHITE)
        positions = (275, 560, 845)
        self.echo.draw(positions[0], 360, 155, 175)
        for index, center in enumerate(positions):
            if index == 0:
                label, number, color = '기본 분신', '1', CYAN
            elif index <= len(world.monster_echoes):
                kind = world.monster_echoes[index - 1]
                walk = self.monster_echo_walk[kind]
                draw_region(walk.image, walk.frames[0], center - 85, 295, 170, 150)
                label, number, color = MONSTER_NAMES[kind], str(index + 1), GOLD
            else:
                label, number, color = '빈 슬롯', str(index + 1), MUTED
                self.body.draw(center - text_width(self.body, '+') / 2, 360, '+', MUTED)
            self.body.draw(center - text_width(self.body, number) / 2, 488, number, color)
            self.body.draw(center - text_width(self.body, label) / 2, 255, label, color)
        hint = '숫자키 1 ~ 3 선택   ·   Esc / Backspace 취소'
        self.small.draw((WIDTH - text_width(self.small, hint)) / 2, 157, hint, WHITE)

    def draw_echo_replacement(self, world):
        box(0, 0, WIDTH, HEIGHT, (2, 8, 17, 188))
        box(265, 180, 855, 520, INK)
        box(265, 180, 855, 520, LINE, filled=False)
        self.heading.draw(300, 480, '몬스터 분신 교체', WHITE)
        self.body.draw(300, 435, f'새 분신: {MONSTER_NAMES[world.pending_monster_echo]}', GOLD)
        self.small.draw(300, 400, '교체할 몬스터 분신을 선택하세요.', WHITE)
        for slot, kind in enumerate(world.monster_echoes):
            self.body.draw(310, 355 - slot * 42, f'{slot + 1}. {MONSTER_NAMES[kind]} 교체', WHITE)
        self.body.draw(310, 260, '3. 새 분신 포기', CYAN)
        self.small.draw(300, 215, '기본 분신은 교체되지 않습니다.  Esc 포기', MUTED)

    def draw_boss_selector(self, selector):
        box(0, 0, WIDTH, HEIGHT, (2, 8, 17, 188))
        box(300, 210, 820, 510, INK)
        box(300, 210, 820, 510, LINE, filled=False)
        self.heading.draw(335, 470, '보스방 선택', WHITE)
        for option, stage_index in enumerate(selector.stages):
            stage = STAGES[stage_index]
            boss = next(enemy for enemy in stage.enemies if enemy.kind in BOSS_KINDS)
            y = 410 - option * 48
            color = CYAN if option == selector.index else WHITE
            self.body.draw(345, y, f'{option + 1}. {MONSTER_NAMES[boss.kind]}  ·  {stage_group_index(stage_index) + 1}스테이지', color)
        if not selector.stages:
            self.body.draw(345, 410, '이동할 보스방이 없습니다.', MUTED)
        self.small.draw(335, 250, '↑ ↓ 선택   Enter 이동   숫자키 바로 이동   Esc 취소', GOLD)

    def draw_stage_selector(self, entry):
        box(0, 0, WIDTH, HEIGHT, (2, 8, 17, 188))
        box(300, 225, 820, 495, INK)
        box(300, 225, 820, 495, LINE, filled=False)
        self.heading.draw(335, 452, '스테이지 바로 이동', WHITE)
        self.body.draw(335, 401, f'이동할 번호를 입력하세요 (1~{len(STAGE_GROUPS)})', MUTED)
        self.display.draw(335, 340, entry if entry else '_', CYAN)
        if entry and not 1 <= int(entry) <= len(STAGE_GROUPS):
            self.small.draw(335, 300, '범위 안의 번호를 입력하세요.', RED)
        self.small.draw(335, 255, 'Enter 이동   Backspace 지우기   Esc 취소', GOLD)

    def draw_floor_selector(self, entry, floors):
        box(0, 0, WIDTH, HEIGHT, (2, 8, 17, 188))
        box(300, 225, 820, 495, INK)
        box(300, 225, 820, 495, LINE, filled=False)
        self.heading.draw(335, 452, '층 바로 이동', WHITE)
        self.body.draw(335, 401, f'이동할 층을 입력하세요 (1~{floors})', MUTED)
        self.display.draw(335, 340, f'{entry}층' if entry else '_', CYAN)
        if entry and not 1 <= int(entry) <= floors:
            self.small.draw(335, 300, '이 스테이지에 없는 층입니다.', RED)
        self.small.draw(335, 255, 'Enter 이동   Backspace 지우기   Esc 또는 - 취소', GOLD)

    def _card(self, title, subtitle, description, action):
        box(0, 0, WIDTH, HEIGHT, (2, 8, 17, 188))
        box(243, 216, 877, 497, INK)
        box(243, 216, 877, 497, LINE, filled=False)
        box(243, 492, 877, 497, CYAN)
        self.small.draw(281, 454, subtitle, CYAN)
        self.display.draw(277, 392, title, WHITE)
        self.body.draw(281, 327, description, MUTED)
        box(281, 244, 524, 291, (25, 65, 74))
        self.body.draw(297, 268, action, CYAN)
