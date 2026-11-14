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
from monster_walk import MONSTER_GAITS, MonsterWalk
from stages import BOSS_KINDS, ENEMY_KINDS, GATE_HALF_WIDTH, MAX_HEALTH, MAX_RECORD_SECONDS, RIGHT, STAGES, STEP, WEAPONS
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
WEAPON_SPRITES = {
    1: ((247, 111, 143, 461), 32, 0.81),
    2: ((335, 48, 355, 1450), 65, 0.84),
    3: ((173, 703, 299, 466), 43, 0.72),
    4: ((884, 625, 126, 601), 62, 0.76),
}
# Hand position and weapon angle for the four right-facing attack poses.
WEAPON_SWING = ((14, 65, -28), (25, 69, 26), (34, 74, 82), (14, 65, 18))
WEAPON_THRUST = ((14, 65, 80), (25, 69, 90), (38, 74, 90), (14, 65, 80))
JUMP_FRAMES = (
    (90, 146, 246, 280), (523, 66, 248, 358), (967, 24, 228, 362), (1410, 10, 230, 302),
    (76, 459, 238, 354), (519, 465, 228, 392), (955, 533, 240, 340), (1430, 467, 196, 406),
)
# Keep the face aligned when cape and body widths change between jump poses.
JUMP_FACE_X = (285, 715, 1145, 1595, 275, 708, 1150, 1560)
JUMP_HEAD_LIFT = (0, 0, 0, 14, 3, -4, 0, 0)
JUMP_POSE_ORDER = (7, 1, 2, 3, 4, 5, 6, 7)


def box(left, bottom, right, top, color, filled=True):
    draw_rectangle(left, bottom, right, top, *color, filled=filled)


def line(x1, y1, x2, y2, color):
    draw_line(x1, y1, x2, y2, *color)


def load_asset(name):
    return load_image(str(ASSETS / name))


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
        self.stage_started_at = 0.0
        self.background = load_asset('dungeon.png')
        self.title_art = load_asset('title_art.png')
        self.stage_art = {}
        for floor_count, (name, rows) in MAP_ART.items():
            image = load_asset(name)
            self.stage_art[floor_count] = (image, tuple(HEIGHT - round(row * HEIGHT / image.h) for row in rows))
        self.wizard_art = load_asset('wizard_castle/castle-dark.png')
        self.late_two_floor_art = load_asset('map_sections/stage-08-late-two-floors.png')
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
        self.weapon_art = load_asset('dungeon_props/weapon-atlas.png')
        self.hero_sword_art = load_asset('weapons/sword-slim.png')
        self.player = load_asset('player.png')
        self.player_jump = load_asset('player_jump_sheet.png')
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
        self.enemy_walk = {
            name: MonsterWalk(load_asset(gait.sheet), gait)
            for name, gait in MONSTER_GAITS.items()
        }
        watcher = actors['watcher']
        self.enemy_walk['watcher'] = WalkCycle(
            load_asset(watcher['sheet']), watcher['frames'],
            watcher['draw_height'], watcher['stride_per_frame'],
        )
        for name, asset in (
            ('jailer_boss', 'prison-jailer-boss'), ('magic_armor', 'magic-armor'),
            ('magic_armor_guard', 'magic-armor'),
            ('witch', 'witch'), ('grand_witch', 'grand-witch-boss'),
        ):
            sheet = load_asset(f'monster_concepts/{asset}-walk.png')
            width, height = sheet.w // 4, sheet.h // 2
            frames = [(column * width, row * height, width, height)
                      for row in range(2) for column in range(4)]
            self.enemy_walk[name] = WalkCycle(sheet, frames, ENEMY_KINDS[name].size, 9)
        self.enemies['magic_book'] = load_asset('monster_concepts/magic-book-sprite.png')
        self.enemies['potion_slime'] = load_asset('monster_concepts/potion-slime-sprite.png')

    def draw(self, world, screen):
        if screen == 'intro':
            self.background.draw(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT)
            self._draw_title()
            return
        if world is not self.current_world:
            self.current_world = world
            self.stage_started_at = perf_counter()
        focus = world.recording.preview if world.recording else world.player
        self.camera_x = min(WIDTH, max(0, focus.x - WIDTH * 0.60))
        if world.index in (1, 2):
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
        elif 3 <= world.index <= 6:
            single_floor = world.stage.floors == 1
            source_top = 330 if single_floor else 0
            source_height = self.wizard_art.h - source_top
            rows = (675,) if single_floor else (675, 330)
            self.floor_y = tuple(105 + round((self.wizard_art.h - row) * 520 / source_height)
                                 for row in rows)
            draw_region(self.wizard_art, (0, source_top, self.wizard_art.w, source_height),
                        -self.camera_x, 105, WIDTH * 2, 520)
            self._draw_wizard_effects(world.time, single_floor)
        elif world.index == 7:
            image = self.late_two_floor_art
            self.floor_y = tuple(105 + round((image.h - row) * 520 / image.h)
                                 for row in (635, 333))
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
            for x in (560, 1680):
                draw_region(self.torch_art, (frame * 32, 0, 32, 32), x - self.camera_x - 36, 325, 72, 72)
        self.animation_time = world.time
        for i in range(24):
            x = (i * 137 + world.time * (7 + i % 4)) % (RIGHT + 48) - self.camera_x
            y = 130 + (i * 83 + sin(world.time * 0.7 + i) * 9) % 460
            box(x, y, x + 2, y + 2, (118, 174, 187))
        self._draw_map(world)
        self._draw_characters(world)
        self._draw_hud(world)
        if perf_counter() - self.stage_started_at < 3.5 and world.result == 'playing':
            title_width = c_int()
            title_height = c_int()
            canvas.TTF_SizeUTF8(self.stage_title.font, world.stage.title.encode('utf-8'), byref(title_width), byref(title_height))
            self.stage_title.draw((WIDTH - title_width.value) / 2, HEIGHT / 2, world.stage.title, WHITE)
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
                box(x - 18, y, x + 18, y + 7, color)
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
                line(x, y, x, y + 70, color)
                self.small.draw(x - 15, y + 82, label, color)
            x, y = gate.door.x - self.camera_x, self.floor_y[gate.door.floor]
            draw_grounded(self.gate_art, GATE_FRAMES[world.sync_unlocked], x, y, 112)
            self.small.draw(x - 30, y + 125, '동시 통과', CYAN if world.sync_unlocked else GOLD)

        if world.echo is not None:
            for hazard in stage.hidden_hazards:
                if world.echo.actor.floor == hazard.floor and abs(world.echo.actor.x - hazard.x) <= 120:
                    x, y = hazard.x - self.camera_x, self.floor_y[hazard.floor]
                    box(x - 18, y, x + 18, y + 10, RED)
                    self.small.draw(x - 15, y + 22, '함정', RED)

        if stage.guard is not None:
            x, y = stage.guard.x - self.camera_x, self.floor_y[stage.guard.floor]
            color = CYAN if world.guard_open_time > 0 else RED
            self.small.draw(x - 40, y + 145, '지나가세요!' if world.guard_open_time > 0 else '수호자 방어', color)

        if stage.watch_gate is not None:
            gate = stage.watch_gate
            x, y = gate.focus.x - self.camera_x, self.floor_y[gate.focus.floor]
            color = CYAN if world.watch_active else GOLD
            line(x - 65, y + 10, x + 65, y + 10, color)
            box(x - 10, y + 82, x + 10, y + 96, color)
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
                draw_grounded(self.gate_art, GATE_FRAMES[is_open], x, y, 112)
                self.small.draw(x - 25, y + 125, label, CYAN if is_open else GOLD)
            x, y = room.lever.x - self.camera_x, self.floor_y[room.lever.floor]
            draw_grounded(self.lever_art, LEVER_FRAMES[world.isolation_closed], x, y, 34)
            self.small.draw(x - 25, y + 45, 'E 격리', CYAN if world.isolation_closed else GOLD)

        if stage.bridge is not None:
            for point, remaining in zip(stage.bridge.points, world.bridge_timers):
                x, y = point.x - self.camera_x, self.floor_y[point.floor]
                box(x - 28, y - 4, x + 28, y + 7, CYAN if remaining > 0 else INK)
                self.small.draw(x - 22, y + 19, '발판' if remaining > 0 else '빈 길', CYAN if remaining > 0 else MUTED)

        if stage.lift is not None:
            lift = stage.lift
            x, y = lift.weight.x - self.camera_x, self.floor_y[lift.weight.floor]
            active = world.echo is not None and world._near(world.echo.actor, lift.weight, 22)
            box(x - 25, y, x + 25, y + 8, CYAN if active else GOLD)
            self.small.draw(x - 32, y + 20, '균형 발판', CYAN if active else GOLD)
            x = lift.platform.x - self.camera_x
            low = self.floor_y[lift.platform.floor]
            high = self.floor_y[lift.platform.floor + 1]
            y = low + (high - low) * world.lift_progress
            box(x - 35, y - 5, x + 35, y + 5, CYAN)
            self.small.draw(x - 22, y + 16, '승강', CYAN)

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
            if enemy.spawn.kind in ('jailer_boss', 'magic_armor', 'magic_armor_guard', 'witch', 'grand_witch'):
                if enemy.windup > 0:
                    screen_enemy.actor.x -= screen_enemy.actor.facing * 4 * (1 - enemy.windup / 0.31)
                elif enemy.recovery > 0:
                    screen_enemy.actor.x += screen_enemy.actor.facing * 10 * max(0, 1 - (0.65 - enemy.recovery) / 0.12)
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
            elif enemy.windup > 0 or enemy.recovery > 0:
                if enemy.windup > 0:
                    windup = min(1, max(0, (0.31 - enemy.windup) / 0.31))
                    recovery = None
                else:
                    windup = None
                    recovery = min(1, max(0, 1 - enemy.recovery / 0.65))
                self._draw_enemy_attack(
                    screen_enemy, kind, y, feet, tint, windup=windup, recovery=recovery,
                )
            elif enemy.actor.moving:
                self.enemy_walk[enemy.spawn.kind].draw(
                    screen_enemy.actor, y, faces=-1, tint=tint,
                )
            else:
                self._sprite(self.enemies[enemy.spawn.kind], screen_enemy.actor, kind.size, world.time, feet=feet, faces=-1, tint=tint)
            bar_y = y + (kind.size + 8 if enemy.spawn.kind in BOSS_KINDS else 73 if feet == 0.30 else 103)
            if enemy.health is not None:
                box(x - 14, bar_y, x + 14, bar_y + 3, (52, 34, 67))
                box(x - 14, bar_y, x - 14 + 28 * enemy.health / kind.health, bar_y + 3, PURPLE)
            if enemy.target is not None:
                color = RED if enemy.windup > 0 else CYAN if world.echo and enemy.target is world.echo.actor else GOLD
                self.small.draw(x - 3, bar_y + 13, '!', color)

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
        if world.attack_flash > 0:
            progress = 1 - world.attack_flash / world.attack_duration
            floor = self.floor_y[world.player.floor] + world.player.jump_height
            self.player_attack.draw(
                player, floor, progress, opacity=player_alpha,
            )
            if world.weapon_index:
                self._draw_weapon(player, world.weapon_index, floor, progress, player_alpha, world.attack_kind)
            elif 0.50 <= progress <= 0.78:
                direction = world.player.facing
                x = player.x + direction * 37
                y = floor + 66
                line(x - direction * 5, y + 3, x, y + 10, GOLD)
                line(x + direction * 4, y + 3, x + direction * 11, y + 3, GOLD)
                line(x - direction * 3, y - 3, x + direction * 2, y - 8, GOLD)
        else:
            self._avatar(self.player, self.player_walk, player, opacity=player_alpha)
        self.floor_y = normal_floors
        if recording is not None:
            actor = self._screen_actor(recording.preview)
            self._avatar(self.echo, self.echo_walk, actor)
            marker = 'REC'
        else:
            actor = player
            marker = 'YOU'
        x, y = actor.x, self.floor_y[actor.floor] + actor.jump_height + 104
        color = CYAN if recording else WHITE
        box(x - 19, y - 7, x + 19, y + 13, INK)
        self.small.draw(x - 15, y + 3, marker, color)

    def _screen_actor(self, actor):
        screen_actor = copy(actor)
        screen_actor.x -= self.camera_x
        return screen_actor

    def _draw_weapon(self, actor, index, floor_y, progress, opacity, attack_kind):
        region, height, grip = WEAPON_SPRITES[index]
        width = round(height * region[2] / region[3])
        poses = WEAPON_SWING if attack_kind == 'slash' else WEAPON_THRUST
        hand_x, hand_y, angle = poses[min(int(progress * 4), 3)]
        grip_y = round(height * grip)
        center = canvas.SDL_Point(width // 2, grip_y)
        left = actor.x + actor.facing * hand_x - center.x
        bottom = floor_y + hand_y + grip_y - height
        target = canvas.to_sdl_rect(left, bottom, width, height)
        texture = (self.hero_sword_art if index == 2 else self.weapon_art).texture
        canvas.SDL_SetTextureAlphaMod(texture, opacity)
        canvas.SDL_RenderCopyEx(
            canvas.renderer, texture, canvas.SDL_Rect(*region), target,
            angle * actor.facing, center, canvas.SDL_FLIP_NONE,
        )
        canvas.SDL_SetTextureAlphaMod(texture, 255)

    def _draw_enemy_attack(self, enemy, kind, floor_y, feet, tint, windup=None, recovery=None):
        walk = self.enemy_walk[enemy.spawn.kind]
        if isinstance(walk, MonsterWalk):
            walk.draw(
                enemy.actor, floor_y, faces=-1, tint=tint,
                windup=windup, recovery=recovery,
            )
            return

        if windup is not None:
            prep = windup * windup * (3 - 2 * windup)
            lunge = 0
        else:
            prep = 0
            release = min(1, recovery / 0.18)
            lunge = 1 - release * release * (3 - 2 * release)

        actor = enemy.actor
        size = kind.size * (1 - 0.035 * prep + 0.055 * lunge)
        x = actor.x + actor.facing * (-4 * prep + 14 * lunge)
        y = floor_y + kind.size * feet + 2 * prep - 2 * lunge
        angle = actor.facing * (0.12 * prep - 0.22 * lunge)
        image = self.enemies[enemy.spawn.kind]
        canvas.SDL_SetTextureColorMod(image.texture, *tint)
        image.composite_draw(angle, 'h' if actor.facing != -1 else '', x, y, size, size)
        canvas.SDL_SetTextureColorMod(image.texture, 255, 255, 255)

    def _avatar(self, idle, walk, actor, opacity=255):
        if actor.jump_time > 0:
            phase = min(7, int(actor.jump_time * 8 / JUMP_DURATION))
            index = JUMP_POSE_ORDER[phase]
            region = JUMP_FRAMES[index]
            scale = 91 / 406
            width, height = region[2] * scale, region[3] * scale
            face_offset = (JUMP_FACE_X[index] - region[0]) * scale - width / 2
            face_alignment = (7 - face_offset) * actor.facing
            texture = self.player_jump.texture
            canvas.SDL_SetTextureAlphaMod(texture, opacity)
            if idle is self.echo:
                canvas.SDL_SetTextureColorMod(texture, 100, 220, 255)
            draw_region(self.player_jump, region, actor.x - width / 2 + face_alignment,
                        self.floor_y[actor.floor] + actor.jump_height + JUMP_HEAD_LIFT[index], width, height,
                        actor.facing < 0)
            canvas.SDL_SetTextureColorMod(texture, 255, 255, 255)
            canvas.SDL_SetTextureAlphaMod(texture, 255)
        elif actor.moving:
            walk.draw(actor, self.floor_y[actor.floor], opacity)
        else:
            breathing = sin(self.animation_time * 2.1) * 1.5
            self._sprite(idle, actor, 91 + breathing, 0, opacity=opacity)

    def _sprite(self, image, actor, size, time, feet=0.49, faces=1, opacity=255, tint=(255, 255, 255)):
        bob = abs(sin(time * 21)) * 4 if actor.moving else 0
        canvas.SDL_SetTextureAlphaMod(image.texture, opacity)
        canvas.SDL_SetTextureColorMod(image.texture, *tint)
        image.composite_draw(0, 'h' if actor.facing != faces else '', actor.x,
                             self.floor_y[actor.floor] + size * feet + bob, size, size)

    def _draw_hud(self, world):
        box(0, 625, WIDTH, HEIGHT, INK)
        line(28, 626, WIDTH - 28, 626, LINE)
        self.small.draw(32, 684, '본체 체력', MUTED)
        for index in range(MAX_HEALTH):
            x = 32 + index * 39
            box(x, 648, x + 29, 661, RED if index < world.health else PANEL)
        self.small.draw(340, 684, '상태', MUTED)
        color, label = (CYAN, '녹화 중 · 시간 정지') if world.recording else (WHITE, '본체 조작 · 일반 진행')
        self.body.draw(340, 653, label, color)
        self.small.draw(557, 684, '무기', MUTED)
        self.small.draw(557, 653, WEAPONS[world.weapon_index].name, GOLD)
        if world.recording is not None:
            seconds = len(world.recording.inputs) * STEP
            value = seconds / MAX_RECORD_SECONDS
            status = f'{seconds:04.1f} / {MAX_RECORD_SECONDS:.0f}초'
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
        self.small.draw(33, 78, world.stage.hint, WHITE)
        self.small.draw(33, 45, '← → 이동   Space 점프   ↑ ↓ 사다리   C 녹화   A 베기   S 찌르기   E 레버   0–4 무기   Backspace 취소   R 재시작   Esc 종료', MUTED)
        if world.message_time > 0:
            self.small.draw(33, 18, world.message, GOLD)
        else:
            self.small.draw(33, 18, 'P 스테이지 바로 이동', CYAN)

    def _draw_title(self):
        height = WIDTH * self.title_art.h / self.title_art.w
        self.title_art.draw(WIDTH / 2, HEIGHT / 2, WIDTH, height)
        line(62, 473, 147, 473, CYAN)
        self.small.draw(62, 446, '멈춘 시간의 잔향', CYAN)
        self.display.draw(58, 390, 'ECHO ESCAPE', WHITE)
        self.body.draw(62, 327, '분신에게 길과 시간을 맡기고', MUTED)
        self.body.draw(62, 298, '본체로 지하 감옥을 탈출하세요.', MUTED)
        box(62, 216, 295, 263, (23, 60, 71))
        self.body.draw(78, 240, 'ENTER   탐험 시작', CYAN)

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
