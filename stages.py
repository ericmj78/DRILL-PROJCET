from dataclasses import dataclass


LEFT, RIGHT = 48, 1072
FLOOR_Y = (320,)
STEP = 1 / 60
MOVE_SPEED = 230
MAX_RECORD_SECONDS = 9
ATTACK_COOLDOWN = 0.32
ACTOR_RADIUS = 15
GATE_HALF_WIDTH = 13


@dataclass(frozen=True)
class Point:
    x: float
    floor: int = 0


@dataclass(frozen=True)
class Stage:
    title: str
    hint: str
    start: Point
    floors: int = 1
    walls: tuple[Point, ...] = ()


STAGE = Stage(
    '01  분신 녹화 연습',
    'C로 이동과 대기를 녹화한 뒤 다시 C를 눌러 분신의 재현을 확인하세요.',
    Point(112),
    walls=(Point(740),),
)
