import json
from math import sin
from os import environ
from pathlib import Path

from pico2d import draw_line, draw_rectangle, load_font, load_image
from pico2d import pico2d as canvas

from animation import AttackCycle, WalkCycle, draw_region
from stages import FLOOR_Y, GATE_HALF_WIDTH, MAX_RECORD_SECONDS, STEP


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
CHAMBER_TILE = (721, 247, 413, 157)
FLOOR_TILE = (738, 416, 393, 30)


def box(left, bottom, right, top, color, filled=True):
    draw_rectangle(left, bottom, right, top, *color, filled=filled)


def line(x1, y1, x2, y2, color):
    draw_line(x1, y1, x2, y2, *color)


def load_asset(name):
    return load_image(str(ASSETS / name))


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
        self.background = load_asset('dungeon.png')
        self.title_art = load_asset('title_art.png')
        self.stone_art = load_asset('dungeon_stone.png')
        self.player = load_asset('player.png')
        self.echo = load_asset('echo.png')
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

    def draw(self, world, screen):
        self.background.draw(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT)
        if screen == 'intro':
            self._draw_title()
            return
        offset = (len(FLOOR_Y) - world.stage.floors) * 82
        self.floor_y = tuple(y + offset for y in FLOOR_Y)
        self._draw_map(world)
        self._draw_characters(world)
        self._draw_hud(world)

    def _draw_map(self, world):
        stage = world.stage
        for floor, y in enumerate(self.floor_y[:stage.floors]):
            for tile, (left, right) in enumerate(((30, 384), (384, 737), (737, 1091))):
                draw_region(self.stone_art, CHAMBER_TILE, left, y, right - left, 130, flip=tile == 1)
                draw_region(self.stone_art, FLOOR_TILE, left, y - 20, right - left, 20, flip=tile == 1)
            box(30, y, 1090, y + 130, (4, 14, 29, 78))
            line(30, y + 130, 1090, y + 130, (40, 60, 80))
            line(30, y - 1, 1090, y - 1, (75, 105, 129))
            box(31, y + 108, 57, y + 127, INK)
            self.small.draw(34, y + 117, f'{floor + 1}F', MUTED)

        for wall in stage.walls:
            y = self.floor_y[wall.floor]
            box(wall.x - GATE_HALF_WIDTH, y, wall.x + GATE_HALF_WIDTH, y + 119, (42, 61, 82))
            for offset in range(12, 120, 15):
                line(wall.x - GATE_HALF_WIDTH, y + offset, wall.x + GATE_HALF_WIDTH, y + offset, LINE)

        for gate, state in zip(stage.gates, world.doors):
            px, py = gate.plate.x, self.floor_y[gate.plate.floor]
            gx, gy = gate.door.x, self.floor_y[gate.door.floor]
            color = CYAN if state.open else GOLD
            box(px - 28, py, px + 28, py + 5, color)
            box(px - 22, py + 6, px + 22, py + 8, (32, 97, 100) if state.pressed else (110, 77, 46))
            self.small.draw(px - 23, py - 11, f'{gate.label} 발판', color)
            box(gx - 24, gy, gx + 24, gy + 91, color, filled=False)
            if not state.open:
                box(gx - 12, gy, gx + 12, gy + 90, (74, 47, 38))
                for bar in range(-12, 13, 6):
                    line(gx + bar, gy, gx + bar, gy + 89, (169, 111, 64))
            box(gx - 19, gy + 92, gx + 19, gy + 113, PANEL)
            self.small.draw(gx - 13, gy + 102, f'{gate.label} 문', color)

    def _draw_characters(self, world):
        recording = world.recording
        if world.echo is not None:
            self._avatar(self.echo, self.echo_walk, world.echo.actor, opacity=145 if recording else 228)
        player_alpha = 170 if recording else 255
        if world.attack_flash > 0:
            progress = 1 - world.attack_flash / 0.14
            self.player_attack.draw(
                world.player, self.floor_y[world.player.floor], progress, opacity=player_alpha,
            )
        else:
            self._avatar(self.player, self.player_walk, world.player, opacity=player_alpha)
        if world.attack_flash > 0:
            attack_progress = 1 - world.attack_flash / 0.14
            if 0.50 <= attack_progress <= 0.78:
                direction = world.player.facing
                x = world.player.x + direction * 37
                y = self.floor_y[world.player.floor] + 66
                line(x - direction * 5, y + 3, x, y + 10, GOLD)
                line(x + direction * 4, y + 3, x + direction * 11, y + 3, GOLD)
                line(x - direction * 3, y - 3, x + direction * 2, y - 8, GOLD)
        if recording is not None:
            self._avatar(self.echo, self.echo_walk, recording.preview)
            actor = recording.preview
            marker = 'REC'
        else:
            actor = world.player
            marker = 'YOU'
        x, y = actor.x, self.floor_y[actor.floor] + 104
        color = CYAN if recording else WHITE
        box(x - 19, y - 7, x + 19, y + 13, INK)
        self.small.draw(x - 15, y + 3, marker, color)

    def _avatar(self, idle, walk, actor, opacity=255):
        if actor.moving:
            walk.draw(actor, self.floor_y[actor.floor], opacity)
        else:
            self._sprite(idle, actor, 91, 0, opacity=opacity)

    def _sprite(self, image, actor, size, time, feet=0.49, faces=1, opacity=255, tint=(255, 255, 255)):
        bob = abs(sin(time * 21)) * 4 if actor.moving else 0
        canvas.SDL_SetTextureAlphaMod(image.texture, opacity)
        canvas.SDL_SetTextureColorMod(image.texture, *tint)
        image.composite_draw(0, 'h' if actor.facing != faces else '', actor.x,
                             self.floor_y[actor.floor] + size * feet + bob, size, size)

    def _draw_hud(self, world):
        box(0, 625, WIDTH, HEIGHT, INK)
        line(28, 626, WIDTH - 28, 626, LINE)
        self.small.draw(32, 687, 'ECHO ESCAPE  /  STAGE', CYAN)
        self.heading.draw(32, 654, world.stage.title, WHITE)
        self.small.draw(364, 684, '상태', MUTED)
        color, label = (CYAN, '녹화 중 · 시간 정지') if world.recording else (WHITE, '본체 조작 · 일반 진행')
        self.body.draw(364, 653, label, color)
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
        self.small.draw(33, 45, '← →  이동     C  녹화/재현     A/S  공격     Backspace  녹화 취소     R  재시작     Esc  종료', MUTED)
        if world.message_time > 0:
            self.small.draw(33, 18, world.message, GOLD)

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
