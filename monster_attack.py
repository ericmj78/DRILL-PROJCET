"""몬스터 공격 모션 스크립트.

몬스터마다 준비 자세(windup)와 타격 자세(strike) 두 개만 적어 두면, 준비 → 타격 → 복귀를
시간에 따라 이어 준다. 새 그림 없이 기존 스프라이트를 밀고, 눌렀다 늘이고, 기울여서 만든다.
수치를 바꾸려면 아래 ATTACKS 표만 고치면 된다.
"""
from dataclasses import dataclass
from math import cos, pi, radians, sin

from pico2d import draw_rectangle
from pico2d import pico2d as canvas

WINDUP, RECOVERY = 0.31, 0.65  # world.py에서 적이 공격을 준비하고 회복하는 시간과 같아야 한다.
STRIKE = 0.18                  # 회복 시간 중 타격 자세로 뻗어 있는 구간
SETTLE = 0.30                  # 그 뒤 제자리로 돌아오는 구간


@dataclass(frozen=True)
class Pose:
    dx: float = 0      # 바라보는 쪽으로 나아간 거리
    dy: float = 0      # 바닥에서 뜬 높이
    sx: float = 1      # 가로 배율
    sy: float = 1      # 세로 배율
    angle: float = 0   # 앞으로 숙인 각도(도). 음수면 뒤로 젖힌다.


@dataclass(frozen=True)
class Attack:
    windup: Pose
    strike: Pose
    effect: str                      # 'slash' 베기, 'slam' 내려찍기, 'bolt' 마법탄, 'charge' 돌진
    color: tuple[int, int, int]
    reach: float                     # 이펙트가 닿는 거리
    height: float                    # 이펙트가 나오는 높이
    hop: float = 0                   # 타격 순간 뛰어오르는 높이


REST = Pose()
ATTACKS = {
    'beast': Attack(Pose(-14, 0, 1.06, 0.90, -9), Pose(30, 0, 1.12, 0.94, 13),
                    'charge', (255, 214, 150), 50, 26),
    'warden': Attack(Pose(-7, 0, 0.96, 1.08, -15), Pose(15, 0, 1.10, 0.90, 19),
                     'slam', (196, 206, 222), 54, 0),
    'watcher': Attack(Pose(-12, 9, 0.88, 0.88, -12), Pose(20, 0, 1.14, 1.00, 12),
                      'bolt', (203, 145, 238), 46, 46),
    'crawler': Attack(Pose(-9, 0, 1.12, 0.80, -6), Pose(26, 0, 1.10, 0.90, 10),
                      'slash', (196, 128, 226), 42, 22, hop=16),
    'jailer_boss': Attack(Pose(-16, 4, 1.00, 1.07, -17), Pose(26, 0, 1.10, 0.93, 18),
                          'slash', (255, 190, 120), 66, 62),
    'magic_book': Attack(Pose(-9, 10, 0.84, 1.20, -14), Pose(22, 0, 1.26, 0.84, 10),
                         'bolt', (120, 200, 255), 44, 34),
    'potion_slime': Attack(Pose(0, 0, 1.32, 0.60, 0), Pose(20, 0, 0.80, 1.30, 6),
                           'slam', (124, 232, 146), 40, 0, hop=22),
    'magic_armor': Attack(Pose(-11, 2, 1.00, 1.05, -13), Pose(23, 0, 1.08, 0.96, 14),
                          'slash', (204, 228, 255), 54, 52),
    'witch': Attack(Pose(-7, 6, 0.96, 1.07, -11), Pose(9, 0, 1.05, 1.00, 9),
                    'bolt', (190, 120, 255), 56, 56),
    'grand_witch': Attack(Pose(-9, 10, 0.96, 1.09, -13), Pose(11, 0, 1.07, 1.00, 11),
                          'bolt', (255, 110, 200), 62, 78),
}
ATTACKS['magic_armor_guard'] = ATTACKS['magic_armor']


def _blend(a: Pose, b: Pose, t: float) -> Pose:
    return Pose(*(x + (y - x) * t for x, y in zip(
        (a.dx, a.dy, a.sx, a.sy, a.angle), (b.dx, b.dy, b.sx, b.sy, b.angle))))


def attack_pose(kind: str, windup: float, recovery: float) -> Pose | None:
    """적의 남은 준비·회복 시간으로 지금 자세를 구한다. 공격 중이 아니면 None."""
    attack = ATTACKS[kind]
    if windup > 0:
        t = 1 - windup / WINDUP
        pose = _blend(REST, attack.windup, 1 - (1 - t) ** 2)
        # 끝으로 갈수록 떨어서 곧 공격한다는 것을 알린다.
        return Pose(pose.dx + sin(t * 38) * 1.6 * t, pose.dy, pose.sx, pose.sy, pose.angle)
    elapsed = RECOVERY - recovery
    if recovery <= 0 or elapsed >= STRIKE + SETTLE:
        return None
    if elapsed < STRIKE:
        t = elapsed / STRIKE
        pose = _blend(attack.windup, attack.strike, min(1, t * 2.8))
        return Pose(pose.dx, pose.dy + attack.hop * sin(pi * t), pose.sx, pose.sy, pose.angle)
    t = (elapsed - STRIKE) / SETTLE
    return _blend(attack.strike, REST, t * t * (3 - 2 * t))


def draw_posed(image, source, x, floor_y, height, facing, pose, tint=(255, 255, 255)):
    """왼쪽을 보는 스프라이트 한 장을 자세대로 그린다. 발밑 가운데를 축으로 기울인다."""
    width = height * source[2] / source[3] * pose.sx
    height *= pose.sy
    left = x + facing * pose.dx - width / 2
    top = canvas.get_canvas_height() - (floor_y + pose.dy) - height
    flip = canvas.SDL_FLIP_HORIZONTAL if facing != -1 else canvas.SDL_FLIP_NONE
    canvas.SDL_SetTextureColorMod(image.texture, *tint)
    canvas.SDL_RenderCopyExF(
        canvas.renderer, image.texture, canvas.SDL_Rect(*source),
        canvas.SDL_FRect(left, top, width, height), pose.angle * facing,
        canvas.SDL_FPoint(width / 2, height), flip,
    )
    canvas.SDL_SetTextureColorMod(image.texture, 255, 255, 255)


def _pixel(x, y, size, color, alpha):
    draw_rectangle(x - size, y - size, x + size, y + size, *color, round(255 * max(0, min(1, alpha))))


def draw_attack_effect(kind: str, x, floor_y, facing, windup: float, recovery: float):
    """타격 이펙트. 마법탄은 준비 중에 기를 모으는 빛도 그린다."""
    attack = ATTACKS[kind]
    color, reach, base = attack.color, attack.reach, floor_y + attack.height
    if windup > 0:
        if attack.effect == 'bolt':
            t = 1 - windup / WINDUP
            for index in range(5):
                turn = index * 2 * pi / 5 + t * 7
                gather = 16 * (1 - t)
                _pixel(x + facing * 14 + cos(turn) * gather, base + sin(turn) * gather, 2, color, 0.4 + t * 0.6)
            _pixel(x + facing * 14, base, 2 + 4 * t, (255, 255, 255), 0.5 * t)
        return
    t = (RECOVERY - recovery) / 0.24
    if recovery <= 0 or t >= 1:
        return
    fade = 1 - t
    if attack.effect == 'slash':
        # 위에서 아래로 휘두른 호. 지나간 자리가 꼬리로 남는다.
        for index in range(9):
            sweep = min(1, t * 2.2) - index * 0.07
            if sweep < 0:
                break
            turn = radians(78 - 120 * sweep)
            _pixel(x + facing * cos(turn) * reach, base + sin(turn) * reach * 0.62,
                   4 - index * 0.35, (255, 255, 255) if index < 2 else color, fade * (1 - index / 9))
    elif attack.effect == 'slam':
        # 바닥을 따라 퍼지는 충격과 튀어 오르는 파편.
        for index in range(7):
            spread = (index + 1) / 7 * reach * min(1, t * 1.8)
            rise = sin(pi * min(1, t * 1.3)) * (10 + index % 3 * 7)
            for side in (1, -0.45):
                _pixel(x + facing * (14 + spread) * side, floor_y + 3 + rise * (index % 2), 3, color, fade)
        draw_rectangle(x + facing * 10, floor_y, x + facing * (14 + reach * min(1, t * 1.8)), floor_y + 3,
                       255, 255, 255, round(200 * fade))
    elif attack.effect == 'bolt':
        # 날아가는 탄과 꼬리, 닿는 순간 터진다.
        travel = min(1, t * 1.7)
        head = x + facing * (14 + reach * travel)
        for index in range(6):
            _pixel(head - facing * index * 6, base + sin(t * 30 + index) * 2, 5 - index * 0.7,
                   (255, 255, 255) if index == 0 else color, fade * (1 - index / 6))
        if travel == 1:
            burst = (t * 1.7 - 1) / 0.7
            for index in range(8):
                turn = index * pi / 4
                _pixel(head + cos(turn) * 18 * burst, base + sin(turn) * 18 * burst, 3, color, 1 - burst)
    else:
        # 돌진: 뒤로 길게 남는 속도선과 머리 앞의 충돌 불꽃.
        for index in range(5):
            y = base - 12 + index * 9
            length = (26 + index % 2 * 14) * fade
            draw_rectangle(x - facing * (10 + length), y, x - facing * 10, y + 2, *color, round(210 * fade), filled=True)
        for index in range(6):
            turn = radians(-50 + index * 20)
            burst = 8 + 20 * min(1, t * 2)
            _pixel(x + facing * (reach + cos(turn) * burst), base + sin(turn) * burst, 3, (255, 255, 255), fade)
