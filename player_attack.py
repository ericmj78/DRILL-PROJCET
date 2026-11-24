"""본체 공격 모션 스크립트.

베기와 찌르기의 손 위치, 무기 각도, 몸의 내디딤을 키프레임으로 적어 두고 그 사이를
부드럽게 잇는다. 빠르게 지나가는 구간에는 무기 잔상을 남기고, 타격 순간에 맞춰
pixelfx 이펙트(assets/attack_fx)를 그린다. 수치를 바꾸려면 아래 표만 고치면 된다.
"""
from monster_attack import draw_sheet

HIT_AT = 0.45  # world.py가 공격 판정을 내는 진행도(공격 시간의 45%)

# (진행도, 손 앞쪽 거리, 손 높이, 무기 각도, 몸 내디딤). 각도 0은 위, 90은 앞을 가리킨다.
SLASH = (
    (0.00, 14, 65, -35, 0),
    (0.26, 9, 74, -80, -5),    # 머리 뒤로 크게 젖힌다
    (0.45, 33, 73, 55, 9),     # 내디디며 빠르게 내려벤다
    (0.62, 34, 60, 122, 11),   # 끝까지 휘두른다
    (1.00, 14, 65, 18, 0),
)
THRUST = (
    (0.00, 14, 65, 78, 0),
    (0.28, 2, 67, 86, -7),     # 팔꿈치를 뒤로 당긴다
    (0.45, 42, 69, 90, 14),    # 한 번에 뻗는다
    (0.70, 40, 69, 90, 12),    # 뻗은 채 잠깐 버틴다
    (1.00, 14, 65, 80, 0),
)
# 잔상을 남기는 구간과 간격(진행도)
TRAIL_FROM, TRAIL_TO, TRAIL_STEP = 0.28, 0.72, 0.045
# 이펙트: 시트, 타격 순간의 재생 위치(초), 손·발 기준 앞쪽 거리, 높이, 무기 길이 99 기준 배율, 물들일 색
# 배율이 클수록 픽셀도 굵어진다. 시트는 몬스터와 같이 쓰므로 색은 그림 파일이 아니라 그릴 때 입힌다.
EFFECTS = {
    'slash': ('sword-slash', 0.07, 4, 22, 1.5, (190, 90, 255)),   # 보라
    'thrust': ('thrust', 0.07, 16, 50, 1.7, (255, 50, 45)),       # 빨강
}
HIT_SPARK = ('hit-spark', 26, 1.0)  # 시트, 맞은 적의 바닥 위 높이, 배율

def weapon_pose(kind: str, progress: float):
    """지금 진행도의 (손 앞쪽 거리, 손 높이, 무기 각도, 몸 내디딤)."""
    keys = SLASH if kind == 'slash' else THRUST
    progress = max(0.0, min(1.0, progress))
    for before, after in zip(keys, keys[1:]):
        if progress <= after[0]:
            t = (progress - before[0]) / (after[0] - before[0])
            t = t * t * (3 - 2 * t)
            return tuple(a + (b - a) * t for a, b in zip(before[1:], after[1:]))
    return keys[-1][1:]


def trail(progress: float):
    """잔상을 그릴 (진행도, 불투명도 비율) 목록. 오래된 것부터."""
    if not TRAIL_FROM <= progress <= TRAIL_TO:
        return ()
    return tuple((progress - TRAIL_STEP * step, 0.42 / step)
                 for step in (3, 2, 1) if progress - TRAIL_STEP * step >= TRAIL_FROM - 0.06)


def draw_attack_effect(sheets, kind, age, duration, reach, x, floor_y, facing):
    """휘두른 자리에 남는 검기. age는 공격을 시작한 뒤 흐른 시간이다."""
    name, lead, forward, lift, scale, color = EFFECTS[kind]
    time = age - duration * HIT_AT + lead
    if time >= 0:
        draw_sheet(sheets[name], time, x + facing * forward, floor_y + lift, facing, scale * reach / 99,
                   color=color)


def draw_hit_spark(sheets, age, x, floor_y, facing):
    name, lift, scale = HIT_SPARK
    draw_sheet(sheets[name], age, x, floor_y + lift, facing, scale)
