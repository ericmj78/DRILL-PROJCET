"""몬스터 공격 모션 스크립트.

몬스터마다 준비 자세(windup)와 타격 자세(strike), 타격 이펙트(fx)를 적어 두면
준비 → 타격 → 복귀를 시간에 따라 이어 준다. 자세는 기존 스프라이트를 밀고, 눌렀다 늘이고,
기울여서 만든다. 이펙트는 pixelfx(https://github.com/patch-gg/pixelfx)로 뽑은
assets/attack_fx의 스프라이트 시트다. 수치를 바꾸려면 아래 ATTACKS 표만 고치면 된다.
"""
import json
from dataclasses import dataclass
from math import pi, sin
from pathlib import Path

from pico2d import load_image
from pico2d import pico2d as canvas
from asset_paths import ASSET_ROOT, asset_path

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
class Fx:
    sheet: str         # assets/attack_fx의 시트 이름
    start: float       # 준비가 시작될 때 이펙트의 재생 위치(초)
    hit: float         # 타격 순간에 맞출 이펙트의 재생 위치(초)
    forward: float     # 몬스터 발밑에서 이펙트 기준점까지 앞쪽 거리
    lift: float = 0    # 기준점의 바닥 위 높이
    scale: float = 1
    hold: float = RECOVERY  # 타격 뒤에 이펙트를 보여 주는 시간


@dataclass(frozen=True)
class Attack:
    windup: Pose
    strike: Pose
    fx: Fx
    hop: float = 0     # 타격 순간 뛰어오르는 높이


REST = Pose()
ATTACKS = {
    # 뿔짐승: 몸을 낮춰 뒤로 당겼다가 뿔로 들이받는다. 부딪친 자리에 강한 충돌 섬광.
    'beast': Attack(Pose(-16, 0, 1.08, 0.88, -10), Pose(32, 0, 1.14, 0.92, 14),
                    Fx('crit-hit', 0, 0, 52, 8, 0.7)),
    # 돌 수호자: 상체를 뒤로 젖혔다가 두 주먹으로 바닥을 내려찍는다. 바닥이 꺼지며 먼지가 인다.
    'warden': Attack(Pose(-7, 0, 0.96, 1.08, -16), Pose(15, 0, 1.10, 0.90, 20),
                     Fx('heavy-landing', 0, 0, 42, 0, 0.95)),
    # 외눈 유령: 떠오르며 움츠렸다가 눈에서 보랏빛 광선을 쏜다.
    'watcher': Attack(Pose(-12, 10, 0.86, 0.86, -8), Pose(6, 4, 1.12, 1.06, 6),
                      Fx('arcane-beam', 0, 0, 4, 50, 0.5, hold=0.30)),
    # 거미: 몸을 낮췄다가 뛰어올라 앞발로 할퀸다.
    'crawler': Attack(Pose(-10, 0, 1.14, 0.78, -6), Pose(26, 0, 1.10, 0.90, 11),
                      Fx('claw-swipe', 0, 0.07, 6, 0, 0.9), hop=18),
    # 간수 보스: 크게 뒤로 젖혔다가 온몸으로 내려찍는다. 준비하는 동안 무기가 떨어져 내린다.
    'jailer_boss': Attack(Pose(-18, 5, 0.98, 1.09, -19), Pose(26, 0, 1.12, 0.90, 21),
                          Fx('hammer-smash', 0, 0.20, 62, 0, 1.25)),
    # 마법책: 책장을 벌리며 물러났다가 날아들며 전격을 뿜는다.
    'magic_book': Attack(Pose(-10, 12, 0.82, 1.24, -14), Pose(20, 2, 1.28, 0.80, 8),
                         Fx('zap-hit', 0, 0.07, 52, 36, 0.8)),
    # 물약 슬라임: 납작하게 눌렸다가 튀어 올라 덮친다. 떨어진 자리에 산성 물약이 튄다.
    'potion_slime': Attack(Pose(0, 0, 1.34, 0.58, 0), Pose(22, 0, 0.78, 1.32, 6),
                           Fx('acid-splash', 0.36, 0.50, 30, 0, 0.8), hop=24),
    # 마법 갑옷: 검을 뒤로 당겼다가 한 발 내디디며 크게 벤다.
    'magic_armor': Attack(Pose(-11, 2, 1.00, 1.05, -13), Pose(24, 0, 1.08, 0.96, 15),
                          Fx('sword-slash', 0, 0.07, 4, 0, 1.0)),
    # 마녀: 지팡이 끝에 기를 모아 마법탄을 쏜다. 타격 순간에 탄이 터진다.
    'witch': Attack(Pose(-7, 6, 0.96, 1.07, -11), Pose(9, 0, 1.05, 1.00, 9),
                    Fx('magic-missile', 0.10, 0.87, 10, 30, 0.7)),
    # 대마녀 보스: 높이 떠올라 상대 발밑에 마력을 모았다가 터뜨린다.
    'grand_witch': Attack(Pose(-9, 12, 0.96, 1.10, -13), Pose(11, 2, 1.08, 1.00, 11),
                          Fx('mana-burst', 0, 0.33, 62, 0, 1.0)),
    'time_thief': Attack(Pose(-8, 0, 0.97, 1.04, -9), Pose(14, 1, 1.05, 0.97, 12),
                         Fx('mana-burst', 0, 0.33, 40, 8, 0.65)),
    'cursed_lantern': Attack(Pose(-8, 8, 0.96, 1.05, -10), Pose(15, 18, 1.06, 0.96, 13),
                             Fx('magic-missile', 0.10, 0.87, 35, 45, 0.6)),
    'broken_jester': Attack(Pose(-10, 0, 0.95, 1.07, -12), Pose(20, 0, 1.08, 0.95, 16),
                            Fx('claw-swipe', 0, 0.07, 16, 12, 0.65)),
}
ATTACKS['magic_armor_guard'] = ATTACKS['magic_armor']
ATTACKS['tier_ghost'] = ATTACKS['watcher']
ATTACKS['echo_knight'] = ATTACKS['magic_armor']


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


def skill_pose(kind: str, phase: str, t: float) -> Pose:
    """보스가 스킬을 쓰는 동안의 자세. 예고 때는 준비 자세를 더 크게 잡고 떤다."""
    attack = ATTACKS[kind]
    if phase == 'telegraph':
        pose = _blend(REST, attack.windup, min(1, t * 2.5))
        return Pose(pose.dx * 1.3 + sin(t * 60) * 2 * t, pose.dy * 1.4, pose.sx, pose.sy, pose.angle * 1.3)
    if phase == 'active':
        return _blend(attack.windup, attack.strike, min(1, t * 4))
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


def load_attack_fx(folder: Path) -> dict:
    """폴더의 pixelfx 시트를 모두 읽는다. 시트 이름 → (이미지, pixelfx 메타 정보)."""
    sheets = {}
    for path in folder.glob('*.json'):
        meta = json.loads(path.read_text(encoding='utf-8'))['meta']['pixelfx']
        image_name = path.with_suffix('.png').relative_to(ASSET_ROOT)
        sheets[path.stem] = (load_image(str(asset_path(image_name))), meta)
    return sheets


def draw_sheet(sheet, time, x, y, facing, scale=1, alpha=255, color=(255, 255, 255)):
    """시트의 time초 프레임을 그린다. 시트는 오른쪽을 보고 있고 pivot이 (x, y)에 온다.
    color를 주면 그 색을 곱해 물들인다 (흰 픽셀이 그 색이 된다)."""
    image, meta = sheet
    frame = int(time * meta['fps'])
    if meta['loop']:
        frame %= meta['frames']
    elif not 0 <= frame < meta['frames']:
        return
    width, height = meta['frameSize']
    pivot_x, pivot_y = meta['pivot']
    source = canvas.SDL_Rect(frame % meta['columns'] * width, frame // meta['columns'] * height, width, height)
    left = x - (pivot_x if facing > 0 else width - pivot_x) * scale
    top = canvas.get_canvas_height() - y - pivot_y * scale
    canvas.SDL_SetTextureAlphaMod(image.texture, alpha)
    canvas.SDL_SetTextureColorMod(image.texture, *color)
    canvas.SDL_RenderCopyExF(
        canvas.renderer, image.texture, source,
        canvas.SDL_FRect(left, top, width * scale, height * scale), 0, None,
        canvas.SDL_FLIP_NONE if facing > 0 else canvas.SDL_FLIP_HORIZONTAL,
    )
    canvas.SDL_SetTextureAlphaMod(image.texture, 255)
    canvas.SDL_SetTextureColorMod(image.texture, 255, 255, 255)


def draw_attack_effect(sheets: dict, kind: str, x, floor_y, facing, windup: float, recovery: float):
    """몬스터 공격 이펙트의 지금 프레임을 그린다."""
    fx = ATTACKS[kind].fx
    if windup > 0:
        time = fx.start + (fx.hit - fx.start) * (1 - windup / WINDUP)
        alpha = 255
    else:
        elapsed = RECOVERY - recovery
        if recovery <= 0 or elapsed >= fx.hold:
            return
        time = fx.hit + elapsed
        alpha = round(255 * min(1, (fx.hold - elapsed) / 0.15))  # 끊기지 않게 끝에서 흐려진다.
    draw_sheet(sheets[fx.sheet], time, x + facing * fx.forward, floor_y + fx.lift, facing, fx.scale, alpha)
