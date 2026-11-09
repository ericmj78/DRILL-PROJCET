from dataclasses import dataclass


LEFT, RIGHT = 48, 1072
FLOOR_Y = (320,)
STEP = 1 / 60
MOVE_SPEED = 230
MAX_RECORD_SECONDS = 9
ATTACK_COOLDOWN = 0.32
DOOR_GRACE = 0.18
ACTOR_RADIUS = 15
GATE_HALF_WIDTH = 13
PLATE_RANGE = 27


@dataclass(frozen=True)
class Point:
    x: float
    floor: int = 0


@dataclass(frozen=True)
class Gate:
    label: str
    plate: Point
    door: Point


@dataclass(frozen=True)
class Stage:
    title: str
    hint: str
    start: Point
    floors: int = 1
    walls: tuple[Point, ...] = ()
    gates: tuple[Gate, ...] = ()


STAGE = Stage(
    '02  발판과 문 연습',
    '분신을 A 발판에서 약 4초 기다리게 녹화하고, 재현 중에 본체로 문을 지나세요.',
    Point(112),
    gates=(Gate('A', Point(267), Point(740)),),
)
