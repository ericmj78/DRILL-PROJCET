from math import sin
from os import environ
from pathlib import Path

from pico2d import draw_line, draw_rectangle, load_font, load_image
from pico2d import pico2d as canvas

from stages import ENEMY_KINDS, FLOOR_Y, GATE_HALF_WIDTH, LEFT, MAX_HEALTH, MAX_RECORD_SECONDS, RIGHT, STAGES, STEP


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
        self.player = load_asset('player.png')
        self.echo = load_asset('echo.png')
        self.enemies = {name: load_asset(kind.image) for name, kind in ENEMY_KINDS.items()}

    def draw(self, world, screen):
        offset = (len(FLOOR_Y) - world.stage.floors) * 82
        self.floor_y = tuple(y + offset for y in FLOOR_Y)
        self.background.draw(WIDTH / 2, HEIGHT / 2, WIDTH, HEIGHT)
        self._draw_map(world)
        self._draw_characters(world)
        self._draw_hud(world)
        if screen == 'intro':
            self._card(
                'ECHO ESCAPE', '멈춘 시간의 잔향',
                '분신에게 길과 시간을 맡기고, 본체로 지하 감옥을 탈출하세요.',
                'ENTER   탐험 시작',
            )
        elif world.result == 'defeated':
            self._card('다시 도전', world.stage.title, '분신의 경로나 본체의 출발 시점을 바꿔 보세요.', 'R   스테이지 재시작')
        elif world.result == 'cleared':
            if world.index == len(STAGES) - 1:
                self._card('탈출 성공', 'ECHO ESCAPE', f'{len(STAGES)}개 스테이지의 봉인을 모두 통과했습니다.', 'ENTER   처음부터 다시')
            else:
                self._card('스테이지 완료', world.stage.title, '다음 스테이지에서 분신의 새로운 역할을 준비하세요.', 'ENTER   다음 스테이지')

    def _draw_map(self, world):
        stage = world.stage
        for floor, y in enumerate(self.floor_y[:stage.floors]):
            box(30, y - 12, 1090, y + 130, (11, 25, 45, 148))
            line(30, y + 130, 1090, y + 130, (40, 60, 80))
            for x in range(104, 1040, 184):
                box(x, y + 3, x + 8, y + 119, (23, 43, 63, 160))
                line(x + 8, y + 18, x + 8, y + 106, (40, 63, 83))
            box(30, y - 20, 1090, y - 1, (22, 37, 55))
            for x in range(32, 1090, 49):
                line(x, y - 19, x, y - 7, (11, 21, 35))
                line(x + 2, y - 12, min(x + 44, 1090), y - 12, (36, 55, 73))
            line(30, y - 1, 1090, y - 1, (75, 105, 129))
            self.small.draw(33, y + 117, f'{floor + 1}F', MUTED)

        for stair in stage.stairs:
            y = self.floor_y[stair.lower]
            upper = self.floor_y[stair.lower + 1]
            for x in (stair.x - 11, stair.x + 11):
                line(x, y + 5, x, upper + 8, (126, 111, 87))
            for rung in range(y + 9, upper + 7, 12):
                line(stair.x - 11, rung, stair.x + 11, rung, (185, 158, 113))
            self.small.draw(stair.x + 17, y + 17, '↑/↓', GOLD)

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

        x, y = stage.exit.x, self.floor_y[stage.exit.floor]
        box(x - 26, y, x + 26, y + 88, (12, 56, 66, 235))
        box(x - 26, y, x + 26, y + 88, CYAN, filled=False)
        box(x - 18, y + 3, x + 18, y + 79, (24, 88, 94, 205), filled=False)
        self.small.draw(x - 18, y + 102, '출구', CYAN)

    def _draw_characters(self, world):
        recording = world.recording
        if world.echo is not None:
            self._sprite(self.echo, world.echo.actor, 91, world.time, opacity=145 if recording else 228)
        for enemy in world.enemies:
            kind = ENEMY_KINDS[enemy.spawn.kind]
            y = self.floor_y[enemy.actor.floor]
            x = enemy.actor.x
            feet = 0.30 if enemy.spawn.kind in ('beast', 'crawler') else 0.47
            tint = (255, 166, 156) if enemy.flash > 0 else (255, 255, 255)
            self._sprite(self.enemies[enemy.spawn.kind], enemy.actor, kind.size, world.time, feet=feet, faces=-1, tint=tint)
            bar_y = y + (73 if feet == 0.30 else 103)
            if enemy.health is not None:
                box(x - 14, bar_y, x + 14, bar_y + 3, (52, 34, 67))
                box(x - 14, bar_y, x - 14 + 28 * enemy.health / kind.health, bar_y + 3, PURPLE)
            if enemy.target is not None:
                color = RED if enemy.windup > 0 else CYAN if world.echo and enemy.target is world.echo.actor else GOLD
                self.small.draw(x - 3, bar_y + 13, '!', color)

        player_alpha = 170 if recording else 255
        if world.invulnerable > 0 and int(world.time * 18) % 2:
            player_alpha = 130
        self._sprite(self.player, world.player, 91, world.time, opacity=player_alpha)
        if world.attack_flash > 0:
            x = world.player.x + world.player.facing * 38
            y = self.floor_y[world.player.floor] + 46
            for offset in range(0, 7, 2):
                line(x - 26, y + offset - 13, x + 27, y + offset + 11, GOLD)
        if recording is not None:
            age = len(recording.inputs) * STEP
            self._sprite(self.echo, recording.preview, 91, age)
            actor = recording.preview
            marker = 'REC'
        else:
            actor = world.player
            marker = 'YOU'
        x, y = actor.x, self.floor_y[actor.floor] + 104
        color = CYAN if recording else WHITE
        box(x - 19, y - 7, x + 19, y + 13, INK)
        self.small.draw(x - 15, y + 3, marker, color)

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
        self.small.draw(926, 684, '본체 체력', MUTED)
        for index in range(MAX_HEALTH):
            x = 926 + index * 39
            box(x, 648, x + 29, 661, RED if index < world.health else PANEL)

        box(0, 0, WIDTH, 104, INK)
        line(28, 103, WIDTH - 28, 103, LINE)
        self.small.draw(33, 78, world.stage.hint, WHITE)
        self.small.draw(33, 45, '← →  이동     ↑ ↓  사다리     C  녹화/재현     A/S  공격     Backspace  녹화 취소     R  재시작     Esc  종료', MUTED)
        if world.message_time > 0:
            self.small.draw(33, 18, world.message, GOLD)

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
