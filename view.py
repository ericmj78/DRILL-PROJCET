import json
from copy import copy
from ctypes import byref, c_int
from math import sin
from os import environ
from pathlib import Path
from time import perf_counter

from pico2d import draw_line, draw_rectangle, load_font, load_image
from pico2d import pico2d as canvas

from animation import AttackCycle, WalkCycle, draw_region
import boss_skills
import late_monster_motion
from monster_attack import attack_pose, draw_attack_effect, draw_posed, draw_sheet, load_attack_fx, skill_pose
from monster_walk import MONSTER_GAITS, MonsterWalk
import player_attack
from title_menu import CONTROLS, PAGE_TITLES
from stages import LEFT
from stages import BOSS_KINDS, ENEMY_KINDS, GATE_HALF_WIDTH, RIGHT, STAGES, STEP, WEAPONS
from world import JUMP_DURATION


WIDTH, HEIGHT = 1120, 720
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
    return load_image(str(ASSETS / name))


def text_width(font, text):
    width, height = c_int(), c_int()
    canvas.TTF_SizeUTF8(font.font, text.encode('utf-8'), byref(width), byref(height))
    return width.value


MONSTER_NAMES = {
    'beast': '뿔짐승', 'warden': '돌 수호자', 'watcher': '외눈 유령', 'crawler': '거미',
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
        self.shake_base = None
        self.stage_started_at = 0.0
        self.background = load_asset('dungeon.png')
        self.hud_concept = load_asset('ui_concepts/echo_hud_concept.png')
        self.boss_bars = {
            'jailer_boss': load_asset('ui_concepts/boss_bar_jailer_named.png'),
            'grand_witch': load_asset('ui_concepts/boss_bar_witch_named.png'),
            'echo_knight': load_asset('ui_concepts/boss_health_bar_concept.png'),
        }
        self.title_art = load_asset('title_art.png')
        self.stage_art = {}
        for floor_count, (name, rows) in MAP_ART.items():
            image = load_asset(name)
            self.stage_art[floor_count] = (image, tuple(HEIGHT - round(row * HEIGHT / image.h) for row in rows))
        self.wizard_art = load_asset('wizard_castle/castle-dark.png')
        self.late_two_floor_art = load_asset('map_sections/stage-08-late-two-floors.png')
        self.late_three_floor_art = load_asset('map_sections/echo-knight-approach-three-floors-concept.png')
        self.echo_boss_arena = load_asset('map_sections/echo-knight-arena-concept.png')
        self.prison_boss_arena = load_asset('map_sections/stage-03-boss-arena.png')
        self.witch_boss_arena = load_asset('map_sections/stage-07-witch-boss-arena.png')
        self.wizard_book = load_asset('wizard_castle/book.png')
        self.wizard_fx = {}
        for name in ('rain', 'storm', 'potion'):
            data = json.loads((ASSETS / 'wizard_castle' / f'{name}.json').read_text(encoding='utf-8'))
            self.wizard_fx[name] = (load_asset(f'wizard_castle/{name}.png'), data)
        self.plate_art = load_asset('dungeon_props/pressure-plate.png')
        self.torch_art = load_asset('dungeon_props/wall-torch-32px-strip8.png')
        self.gate_art = load_asset('dungeon_props/portcullis.png')
        self.exit_art = load_asset('dungeon_props/exit-portal.png')
        self.ladder_art = load_asset('dungeon_props/ladder.png')
        self.lever_art = load_asset('dungeon_props/lever.png')
        self.puzzle_art = load_asset('puzzle_concepts/echo-puzzle-props-concept.png')
        self.weapon_art = load_asset('dungeon_props/weapon-atlas.png')
        self.hero_sword_art = load_asset('weapons/sword-slim.png')
        self.player = load_asset('player.png')
        self.player_jump = load_asset('player_jump_sheet.png')
        self.jailer_chain_slam = load_asset('monster_concepts/prison-jailer-long-chain-slam-concept.png')
        self.jester_walk = load_asset('monster_concepts/broken-jester-walk-16.png')
        self.knight_sheets = {
            name: load_asset(f'monster_concepts/echo-knight-{name}-sheet.png')
            for name in ('walk', 'attack', 'charge', 'orb', 'bolts')
        }
        self.echo = load_asset('echo.png')
        self.enemies = {name: load_asset(kind.image) for name, kind in ENEMY_KINDS.items()}
        walk_data = json.loads((ASSETS / 'walk_sheets.json').read_text(encoding='utf-8'))
        actors = walk_data['actors']
        self.player_walk = WalkCycle(
            load_asset(actors['player']['sheet']), actors['player']['frames'],
            actors['player']['draw_height'], actors['player']['stride_per_frame'],
        )
        self.player_attack = AttackCycle(
            load_asset('player_attack_sheet.png'),
            [
                [25, 33, 495, 658],
                [543, 33, 543, 658],
                [1086, 33, 543, 658],
                [1654, 33, 518, 658],
            ],
            draw_height=103,
        )
        self.echo_walk = WalkCycle(
            load_asset(actors['echo']['sheet']), actors['echo']['frames'],
            actors['echo']['draw_height'], actors['echo']['stride_per_frame'],
        )
        self.attack_fx = load_attack_fx(ASSETS / 'attack_fx')
        self.enemy_walk = {
            name: MonsterWalk(load_asset(gait.sheet), gait)
            for name, gait in MONSTER_GAITS.items()
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

    def draw(self, world, screen, menu=None):
        self._shake(world, screen)
        if screen == 'intro':
            self.background.draw(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT)
            self._draw_title(menu)
            return
        if world is not self.current_world:
            self.current_world = world
            self.stage_started_at = perf_counter()
            self.camera_y = 0.0
            self.camera_updated_at = perf_counter()
        focus = world.recording.preview if world.recording else world.player
        self.camera_x = min(WIDTH, max(0, focus.x - WIDTH * 0.60))
        if world.index in (0, 1, 3, 4):
            # Follow the active character and keep all floor positions in world space.
            now = perf_counter()
            elapsed = min(0.1, max(0, now - self.camera_updated_at))
            self.camera_updated_at = now
            target = 400 * (focus.floor + focus.elevator_offset)
            self.camera_y += max(-850 * elapsed, min(850 * elapsed, target - self.camera_y))
            self.floor_y = tuple(160 + floor * 400 - self.camera_y
                                 for floor in range(world.stage.floors))
            if world.index in (0, 1):
                corridor = self.stage_art[1][0]
                for floor_y in self.floor_y:
                    bottom = floor_y - (corridor.h - 773) * 400 / corridor.h
                    draw_region(corridor, (0, 0, corridor.w, corridor.h),
                                -self.camera_x, bottom, WIDTH * 2, 400)
            else:
                corridor = self.wizard_art
                source_top = 330
                source_height = corridor.h - source_top
                for floor_y in self.floor_y:
                    bottom = floor_y - (corridor.h - 675) * 400 / source_height
                    draw_region(corridor, (0, source_top, corridor.w, source_height),
                                -self.camera_x, bottom, WIDTH * 2, 400)
                self._draw_wizard_tower_effects(world.time)
        elif world.index == 8:
            # 세 층을 하나의 이미지로 그려 층 사이 배경이 끊기지 않는다.
            now = perf_counter()
            elapsed = min(0.1, max(0, now - self.camera_updated_at))
            self.camera_updated_at = now
            image = self.late_three_floor_art
            scale_y = 400 / 231
            levels = (0, (690 - 455) * scale_y, (690 - 228) * scale_y,
                      (690 - 228) * scale_y + 400)
            floor = focus.floor
            offset = focus.elevator_offset
            target = levels[floor]
            if offset > 0 and floor + 1 < len(levels):
                target += offset * (levels[floor + 1] - levels[floor])
            elif offset < 0 and floor > 0:
                target += offset * (levels[floor] - levels[floor - 1])
            self.camera_y += max(-850 * elapsed, min(850 * elapsed, target - self.camera_y))
            self.floor_y = tuple(160 + level - self.camera_y for level in levels)
            bottom = self.floor_y[0] - (image.h - 690) * scale_y
            draw_region(image, (0, 0, image.w, image.h), -self.camera_x,
                        bottom, WIDTH * 2, image.h * scale_y)
            arena = self.echo_boss_arena
            draw_region(arena, (0, 0, arena.w, arena.h), -self.camera_x,
                        self.floor_y[3] - 95, WIDTH * 2, 560)
        elif world.index in (2, 5):
            now = perf_counter()
            elapsed = min(0.1, max(0, now - self.camera_updated_at))
            self.camera_updated_at = now
            lift_offset = world.lift_progress if world.index == 5 and world.lift_riding and focus is world.player else 0
            target = 400 * (focus.floor + focus.elevator_offset + lift_offset)
            self.camera_y += max(-850 * elapsed, min(850 * elapsed, target - self.camera_y))
            self.floor_y = tuple(160 + floor * 400 - self.camera_y for floor in range(5))
            if world.index == 2:
                corridor = self.stage_art[1][0]
                for floor in range(4):
                    floor_y = self.floor_y[floor]
                    bottom = floor_y - (corridor.h - 773) * 400 / corridor.h
                    draw_region(corridor, (0, 0, corridor.w, corridor.h),
                                -self.camera_x, bottom, WIDTH * 2, 400)
                arena = self.prison_boss_arena
            else:
                corridor = self.wizard_art
                source_top = 330
                source_height = corridor.h - source_top
                for floor in range(4):
                    bottom = self.floor_y[floor] - (corridor.h - 675) * 400 / source_height
                    draw_region(corridor, (0, source_top, corridor.w, source_height),
                                -self.camera_x, bottom, WIDTH * 2, 400)
                arena = self.witch_boss_arena
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
        if world.index == 0:
            frame = int(world.time * 10) % 8
            for floor_y in self.floor_y:
                for x in (560, 1680):
                    draw_region(self.torch_art, (frame * 32, 0, 32, 32),
                                x - self.camera_x - 36, floor_y + 165, 72, 72)
        self.animation_time = world.time
        for i in range(24):
            x = (i * 137 + world.time * (7 + i % 4)) % (RIGHT + 48) - self.camera_x
            y = 130 + (i * 83 + sin(world.time * 0.7 + i) * 9) % 460
            box(x, y, x + 2, y + 2, (118, 174, 187))
        self._draw_map(world)
        self._draw_characters(world)
        self._draw_hud(world)
        if perf_counter() - self.stage_started_at < 3.5 and world.result == 'playing':
            width = text_width(self.stage_title, world.stage.title)
            self.stage_title.draw((WIDTH - width) / 2, HEIGHT / 2, world.stage.title, WHITE)
        if world.result == 'defeated':
            self._card('다시 도전', world.stage.title, '분신의 경로나 본체의 출발 시점을 바꿔 보세요.', 'R   스테이지 재시작')
        elif world.result == 'cleared':
            if world.index == len(STAGES) - 1:
                self._card('탈출 성공', 'ECHO ESCAPE', f'{len(STAGES)}개 스테이지의 봉인을 모두 통과했습니다.', 'ENTER   처음부터 다시')
            else:
                self._card('스테이지 완료', world.stage.title, '다음 스테이지에서 분신의 새로운 역할을 준비하세요.', 'ENTER   다음 스테이지')

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

        if stage.sequence is not None:
            for index, sensor in enumerate(stage.sequence.sensors):
                x = sensor.x - self.camera_x
                y = self.floor_y[sensor.floor]
                color = CYAN if index < world.sequence_progress else GOLD
                self._draw_puzzle_prop('sensor', x, y - 3, 42, 17, index < world.sequence_progress)
                self.small.draw(x - 4, y + 19, str(index + 1), color)
            x = stage.sequence.door.x - self.camera_x
            y = self.floor_y[stage.sequence.door.floor]
            draw_grounded(self.gate_art, GATE_FRAMES[world.sequence_unlocked], x, y, 112)
            self.small.draw(x - 35, y + 125, f'보안 {world.sequence_progress}/3', CYAN if world.sequence_unlocked else GOLD)

        if stage.sync_gate is not None:
            gate = stage.sync_gate
            for sensor, label, active in ((gate.player_sensor, '본체', world.sync_player_time),
                                          (gate.echo_sensor, '분신', world.sync_echo_time)):
                x, y = sensor.x - self.camera_x, self.floor_y[sensor.floor]
                color = CYAN if active is not None or world.sync_unlocked else GOLD
                self._draw_puzzle_prop('sync', x, y, 68, 72,
                                       active is not None or world.sync_unlocked)
                line(x, y, x, y + 70, color)
                self.small.draw(x - 15, y + 82, label, color)
            x, y = gate.door.x - self.camera_x, self.floor_y[gate.door.floor]
            draw_grounded(self.gate_art, GATE_FRAMES[world.sync_unlocked], x, y, 112)
            self.small.draw(x - 30, y + 125, '동시 통과', CYAN if world.sync_unlocked else GOLD)

        for hazard in stage.hidden_hazards:
            if world.hazard_lit(hazard):
                x, y = hazard.x - self.camera_x, self.floor_y[hazard.floor]
                self._draw_puzzle_prop('hazard', x, y - 4, 45, 22)
                self.small.draw(x - 15, y + 22, '함정', RED)

        if (stage.guard is not None and world.index != 2
                and any(enemy.spawn.point == stage.guard for enemy in world.enemies)):
            x, y = stage.guard.x - self.camera_x, self.floor_y[stage.guard.floor]
            color = CYAN if world.guard_open_time > 0 else RED
            self.small.draw(x - 40, y + 180, '지나가세요!' if world.guard_open_time > 0 else '경비 구간', color)

        if stage.watch_gate is not None:
            gate = stage.watch_gate
            x, y = gate.focus.x - self.camera_x, self.floor_y[gate.focus.floor]
            color = CYAN if world.watch_active else GOLD
            line(x - 65, y + 10, x + 65, y + 10, color)
            self._draw_puzzle_prop('watch', x, y + 34, 70, 70, world.watch_active)
            target_x = world.echo.actor.x - self.camera_x if world.watch_active else x + 50 * sin(world.time)
            line(x, y + 82, target_x, y + 35, color)
            self.small.draw(x - 35, y + 27, '감시 구역', color)
            gx, gy = gate.door.x - self.camera_x, self.floor_y[gate.door.floor]
            draw_grounded(self.gate_art, GATE_FRAMES[world.watch_active], gx, gy, 112)
            self.small.draw(gx - 35, gy + 125, '시선 분산', color)

        if stage.isolation is not None:
            room = stage.isolation
            for point, is_open, label in ((room.door, not world.isolation_closed, '격리실'),
                                          (room.exit_gate, world.isolation_closed, '보안문')):
                x, y = point.x - self.camera_x, self.floor_y[point.floor]
                if is_open:
                    draw_grounded(self.gate_art, GATE_FRAMES[True], x, y, 112)
                else:
                    self._draw_puzzle_prop('locked_gate', x, y, 90, 112)
                self.small.draw(x - 25, y + 125, label, CYAN if is_open else GOLD)
            x, y = room.lever.x - self.camera_x, self.floor_y[room.lever.floor]
            self._draw_puzzle_prop('lever', x, y, 25, 39, world.isolation_closed)
            self.small.draw(x - 25, y + 45, 'E 격리', CYAN if world.isolation_closed else GOLD)

        if stage.bridge is not None:
            for point, remaining in zip(stage.bridge.points, world.bridge_timers):
                x, y = point.x - self.camera_x, self.floor_y[point.floor]
                if remaining > 0:
                    self._draw_puzzle_prop('bridge', x, y - 27, 62, 34)
                else:
                    box(x - 28, y - 4, x + 28, y + 7, INK)
                self.small.draw(x - 22, y + 19, '발판' if remaining > 0 else '빈 길', CYAN if remaining > 0 else MUTED)

        if stage.lift is not None:
            lift = stage.lift
            x, y = lift.weight.x - self.camera_x, self.floor_y[lift.weight.floor]
            active = world.echo is not None and world._near(world.echo.actor, lift.weight, 22)
            self._draw_puzzle_prop('lift_weight', x, y - 3, 56, 23, active)
            self.small.draw(x - 32, y + 20, '균형 발판', CYAN if active else GOLD)
            x = lift.platform.x - self.camera_x
            low = self.floor_y[lift.platform.floor]
            high = self.floor_y[lift.platform.floor + 1]
            y = low + (high - low) * world.lift_progress
            self._draw_puzzle_prop('lift_platform', x, y - 19, 70, 24)
            self.small.draw(x - 22, y + 16, '승강', CYAN)

        for elevator in stage.elevators:
            x = elevator.x - self.camera_x
            low, high = self.floor_y[elevator.lower], self.floor_y[elevator.lower + 1]
            line(x - 27, low, x - 27, high + 75, GOLD)
            line(x + 27, low, x + 27, high + 75, GOLD)
            for floor, y, direction in ((elevator.lower, low, '↑'), (elevator.lower + 1, high, '↓')):
                self._draw_puzzle_prop('lift_platform', x, y - 18, 70, 24)
                self.small.draw(x - 22, y + 22, f'{direction} 승강', GOLD)
            for actor in (world.player, world.echo.actor if world.echo else None,
                          world.recording.preview if world.recording else None):
                if actor and actor.elevator_target is not None and abs(actor.x - elevator.x) < 1 and min(actor.floor, actor.elevator_target) == elevator.lower:
                    y = self._actor_floor_y(actor)
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

        for gate, state in zip(stage.gates, world.doors):
            px, py = gate.plate.x - self.camera_x, self.floor_y[gate.plate.floor]
            gx, gy = gate.door.x - self.camera_x, self.floor_y[gate.door.floor]
            draw_grounded(self.plate_art, PLATE_FRAMES[state.pressed], px, py, 13)
            self.small.draw(px - 23, py - 12, f'{gate.label} 발판', CYAN if state.pressed else GOLD)
            draw_grounded(self.gate_art, GATE_FRAMES[state.open], gx, gy, 112)
            box(gx - 21, gy + 114, gx + 21, gy + 134, PANEL)
            self.small.draw(gx - 15, gy + 124, f'{gate.label} 문', CYAN if state.open else GOLD)
            if gate.lever is not None:
                lx, ly = gate.lever.x - self.camera_x, self.floor_y[gate.lever.floor]
                draw_grounded(self.lever_art, LEVER_FRAMES[state.latched], lx, ly, 34)
                self.small.draw(lx - 20, ly + 45, 'E 레버', CYAN if state.latched else GOLD)

        x, y = stage.exit.x - self.camera_x, self.floor_y[stage.exit.floor]
        draw_grounded(self.exit_art, EXIT_FRAME, x, y, 105)
        locked = any(enemy.spawn.kind in BOSS_KINDS for enemy in world.enemies)
        self.small.draw(x - 35 if locked else x - 15, y + 116,
                        '보스 처치 필요' if locked else '출구', RED if locked else CYAN)

    def _draw_jailer_chain(self, actor, floor_y, phase, tint, size):
        # Source rectangles and foot anchors keep the boss fixed as the chain extends.
        frames = (
            (0, 160, 300, 398, 205),
            (300, 160, 270, 398, 470),
            (570, 160, 255, 398, 730),
            (825, 160, 465, 398, 1160),
            (1290, 160, 520, 398, 1680),
            (1810, 160, 362, 398, 2070),
        )
        name, progress = phase
        if name == 'telegraph':
            index = min(3, int(progress * 4))
        elif name == 'active':
            index = 4
        else:
            index = 5 if progress < 0.75 else 0
        left, top, width, height, anchor = frames[index]
        scale = size / 250
        # Source art faces left. Reflect both sprite and its anchor for facing right.
        flipped = actor.facing > 0
        offset = (left + width - anchor) if flipped else (anchor - left)
        x = actor.x - offset * scale
        y = floor_y - 10 * scale
        canvas.SDL_SetTextureColorMod(self.jailer_chain_slam.texture, *tint)
        draw_region(self.jailer_chain_slam, (left, top, width, height), x, y,
                    width * scale, height * scale, flipped)
        canvas.SDL_SetTextureColorMod(self.jailer_chain_slam.texture, 255, 255, 255)

    def _draw_characters(self, world):
        recording = world.recording
        if world.echo is not None:
            self._avatar(self.echo, self.echo_walk, self._screen_actor(world.echo.actor), opacity=145 if recording else 228)
        for enemy in world.enemies:
            screen_enemy = copy(enemy)
            screen_enemy.actor = self._screen_actor(enemy.actor)
            kind = ENEMY_KINDS[enemy.spawn.kind]
            y = self.floor_y[enemy.actor.floor]
            x = screen_enemy.actor.x
            feet = 0.30 if enemy.spawn.kind in ('beast', 'crawler') else 0.47
            tint = (255, 166, 156) if enemy.flash > 0 else (255, 255, 255)
            pose = attack_pose(enemy.spawn.kind, enemy.windup, enemy.recovery)
            skill_phase = boss_skills.phase(enemy)
            if skill_phase is not None:
                pose = skill_pose(enemy.spawn.kind, *skill_phase)
            if enemy.spawn.kind == 'echo_knight':
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
            elif enemy.spawn.kind == 'jailer_boss' and enemy.skill == 'chain' and skill_phase is not None:
                self._draw_jailer_chain(screen_enemy.actor, y, skill_phase, tint, kind.size)
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
            elif enemy.spawn.kind in ('magic_book', 'potion_slime'):
                image = self.enemies[enemy.spawn.kind]
                bob = 5 + sin(world.time * 3) * 4 if enemy.spawn.kind == 'magic_book' else 0
                squash = 1 + 0.07 * sin(world.time * 7) if enemy.spawn.kind == 'potion_slime' else 1
                height = kind.size * squash
                width = kind.size * image.w / image.h / squash
                canvas.SDL_SetTextureColorMod(image.texture, *tint)
                draw_region(image, (0, 0, image.w, image.h), x - width / 2, y + bob, width, height,
                            enemy.actor.facing != -1)
                canvas.SDL_SetTextureColorMod(image.texture, 255, 255, 255)
            elif enemy.actor.moving:
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
        if world.attack_flash > 0:
            # 공격 중에는 player_attack.py의 키프레임대로 몸을 내디디고 무기를 움직인다.
            progress = 1 - world.attack_flash / world.attack_duration
            body = copy(player)
            body.x += player.facing * player_attack.weapon_pose(world.attack_kind, progress)[3]
            blend = player_attack.body_frames(progress) if world.weapon_index == 2 else None
            height = 91 if world.weapon_index == 2 else None
            self.player_attack.draw(body, floor, progress, opacity=player_alpha, blend_frames=blend, height=height)
            if world.weapon_index:
                for past, strength in player_attack.trail(progress):
                    self._draw_weapon(player, world.weapon_index, floor, past, round(player_alpha * strength), world.attack_kind)
                self._draw_weapon(player, world.weapon_index, floor, progress, player_alpha, world.attack_kind)
        else:
            self._avatar(self.player, self.player_walk, player, opacity=player_alpha)
            if world.weapon_index == 2:
                self._draw_weapon(player, 2, floor, 0, player_alpha, 'slash',
                                  pose=player_attack.held_sword_pose(world.player))
        player_attack.draw_attack_effect(
            self.attack_fx, world.attack_kind, world.attack_age, world.attack_duration,
            WEAPONS[world.weapon_index].reach, player.x, floor, player.facing)
        for spark_x, spark_floor, age in world.hit_sparks:
            player_attack.draw_hit_spark(self.attack_fx, age, spark_x - self.camera_x,
                                         self.floor_y[spark_floor], world.player.facing)
        self.floor_y = normal_floors
        if recording is not None:
            actor = self._screen_actor(recording.preview)
            self._avatar(self.echo, self.echo_walk, actor)
            marker = 'REC'
        else:
            actor = player
            marker = 'YOU'
        x, y = actor.x, self._actor_floor_y(actor) + actor.jump_height + 104
        color = CYAN if recording else WHITE
        box(x - 19, y - 7, x + 19, y + 13, INK)
        self.small.draw(x - 15, y + 3, marker, color)

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

    def _draw_weapon(self, actor, index, floor_y, progress, opacity, attack_kind, pose=None):
        region, height, grip = WEAPON_SPRITES[index]
        width = round(height * region[2] / region[3])
        if pose is None:
            pose = (player_attack.sword_pose(attack_kind, progress) if index == 2
                    else player_attack.weapon_pose(attack_kind, progress))
        hand_x, hand_y, angle, lunge = pose
        grip_y = round(height * grip)
        center = canvas.SDL_Point(width // 2, grip_y)
        left = actor.x + actor.facing * (hand_x + lunge) - center.x
        bottom = floor_y + hand_y + grip_y - height
        target = canvas.to_sdl_rect(left, bottom, width, height)
        texture = (self.hero_sword_art if index == 2 else self.weapon_art).texture
        canvas.SDL_SetTextureAlphaMod(texture, opacity)
        canvas.SDL_RenderCopyEx(
            canvas.renderer, texture, canvas.SDL_Rect(*region), target,
            angle * actor.facing, center, canvas.SDL_FLIP_NONE,
        )
        canvas.SDL_SetTextureAlphaMod(texture, 255)

    def _avatar(self, idle, walk, actor, opacity=255):
        if actor.jump_time > 0:
            progress = min(7.999, actor.jump_time * 8 / JUMP_DURATION)
            phase = int(progress)
            # Blend briefly into the next pose instead of abruptly replacing it.
            blend = max(0.0, (progress - phase - 0.65) / 0.35) if phase < 7 else 0.0
            self._draw_jump_pose(actor, JUMP_POSE_ORDER[phase], opacity, idle is self.echo)
            if blend:
                self._draw_jump_pose(actor, JUMP_POSE_ORDER[phase + 1], round(opacity * blend), idle is self.echo)
        elif actor.moving:
            walk.draw(actor, self._actor_floor_y(actor), opacity)
        else:
            breathing = sin(self.animation_time * 2.1) * 1.5
            self._sprite(idle, actor, 91 + breathing, 0, opacity=opacity)

    def _draw_jump_pose(self, actor, index, opacity, is_echo):
        region = JUMP_FRAMES[index]
        scale = 91 / 406
        width, height = region[2] * scale, region[3] * scale
        face_offset = (JUMP_FACE_X[index] - region[0]) * scale - width / 2
        face_alignment = (7 - face_offset) * actor.facing
        left = actor.x - width / 2 + face_alignment
        bottom = self._actor_floor_y(actor) + actor.jump_height + JUMP_HEAD_LIFT[index]
        flip = actor.facing < 0
        texture = self.player_jump.texture
        canvas.SDL_SetTextureAlphaMod(texture, opacity)
        if is_echo:
            canvas.SDL_SetTextureColorMod(texture, 100, 220, 255)
        draw_region(self.player_jump, region, left, bottom, width, height, flip)
        if is_echo:
            # The player's dark sprite cannot become bright cyan through color
            # modulation alone; a cyan additive pass keeps the echo recognizable.
            canvas.SDL_SetTextureBlendMode(texture, canvas.SDL_BLENDMODE_ADD)
            canvas.SDL_SetTextureColorMod(texture, 0, 220, 255)
            draw_region(self.player_jump, region, left, bottom, width, height, flip)
            canvas.SDL_SetTextureBlendMode(texture, canvas.SDL_BLENDMODE_BLEND)
        canvas.SDL_SetTextureColorMod(texture, 255, 255, 255)
        canvas.SDL_SetTextureAlphaMod(texture, 255)

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
        color, label = (CYAN, '녹화 중 · 시간 정지') if world.recording else (WHITE, '본체 조작 · 일반 진행')
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
            for point in stage.bridge.points:
                marker(point, CYAN, 1)
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
        height = WIDTH * self.title_art.h / self.title_art.w
        self.title_art.draw(WIDTH / 2, HEIGHT / 2, WIDTH, height)
        pulse = (sin(perf_counter() * 4) + 1) / 2
        if menu.page == 'main':
            line(62, 523, 147, 523, CYAN)
            self.small.draw(62, 496, '멈춘 시간의 잔향', CYAN)
            self.display.draw(58, 440, 'ECHO ESCAPE', WHITE)
            self.body.draw(62, 377, '분신에게 길과 시간을 맡기고', MUTED)
            self.body.draw(62, 348, '본체로 지하 감옥을 탈출하세요.', MUTED)
        else:
            box(0, 0, WIDTH, HEIGHT, (2, 8, 17, 215))
            line(90, 640, 175, 640, CYAN)
            self.heading.draw(90, 610, PAGE_TITLES[menu.page], WHITE)
        if menu.page == 'controls':
            for row, (keys, what) in enumerate(CONTROLS):
                y = 548 - row * 36
                box(90, y - 14, 230, y + 14, PANEL)
                self.body.draw(102, y, keys, CYAN)
                self.body.draw(252, y, what, WHITE)
        for index, (action, label, (left, bottom, right, top)) in enumerate(menu.buttons()):
            chosen = index == menu.index
            middle = (bottom + top) / 2
            if menu.page == 'main':
                # 고른 줄만 띠와 막대로 강조하고 글자가 살짝 숨 쉬듯 움직인다.
                if chosen:
                    box(left, bottom, right, top, (23, 60, 71))
                    box(left, bottom, left + 4, top, CYAN)
                self.body.draw(left + 20 + 4 * pulse * chosen, middle, label, CYAN if chosen else MUTED)
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
        self.small.draw(62, 26, '↑ ↓ ← →  선택     Enter  결정     Esc  뒤로     마우스로 가리키고 클릭', MUTED)

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
            self.body.draw(345, y, f'{option + 1}. {MONSTER_NAMES[boss.kind]}  ·  {stage_index + 1}스테이지', color)
        if not selector.stages:
            self.body.draw(345, 410, '이동할 보스방이 없습니다.', MUTED)
        self.small.draw(335, 250, '↑ ↓ 선택   Enter 이동   숫자키 바로 이동   Esc 취소', GOLD)

    def draw_stage_selector(self, entry):
        box(0, 0, WIDTH, HEIGHT, (2, 8, 17, 188))
        box(300, 225, 820, 495, INK)
        box(300, 225, 820, 495, LINE, filled=False)
        self.heading.draw(335, 452, '스테이지 바로 이동', WHITE)
        self.body.draw(335, 401, f'이동할 번호를 입력하세요 (1~{len(STAGES)})', MUTED)
        self.display.draw(335, 340, entry if entry else '_', CYAN)
        if entry and not 1 <= int(entry) <= len(STAGES):
            self.small.draw(335, 300, '범위 안의 번호를 입력하세요.', RED)
        self.small.draw(335, 255, 'Enter 이동   Backspace 지우기   Esc 취소', GOLD)

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
