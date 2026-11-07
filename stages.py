from dataclasses import dataclass


LEFT, RIGHT = 48, 1072
FLOOR_Y = (156, 320, 484)
STEP = 1 / 60
MOVE_SPEED = 230
MAX_RECORD_SECONDS = 9
MAX_HEALTH = 3
ATTACK_RANGE = 86
ATTACK_COOLDOWN = 0.32
DOOR_GRACE = 0.18
STAIR_RANGE = 31
ACTOR_RADIUS = 15
GATE_HALF_WIDTH = 13
PLATE_RANGE = 27


@dataclass(frozen=True)
class Point:
    x: float
    floor: int


@dataclass(frozen=True)
class Stair:
    x: int
    lower: int


@dataclass(frozen=True)
class Gate:
    label: str
    plate: Point
    door: Point


@dataclass(frozen=True)
class EnemyKind:
    image: str
    speed: int
    sight: int
    attack_range: int
    health: int | None  # None이면 기본 공격으로 처치할 수 없는 적이다.
    size: int


ENEMY_KINDS = {
    'beast': EnemyKind('monster_01_hornbeast.png', 112, 250, 43, None, 115),
    'warden': EnemyKind('monster_02_stone_warden.png', 92, 220, 48, None, 105),
    'watcher': EnemyKind('monster_03_watcher.png', 114, 215, 39, 2, 86),
    'crawler': EnemyKind('monster_04_crawler.png', 88, 185, 38, 2, 100),
}


@dataclass(frozen=True)
class EnemySpawn:
    kind: str
    point: Point
    patrol: tuple[int, int]


@dataclass(frozen=True)
class Stage:
    title: str
    hint: str
    floors: int
    start: Point
    exit: Point
    stairs: tuple[Stair, ...] = ()
    gates: tuple[Gate, ...] = ()
    enemies: tuple[EnemySpawn, ...] = ()
    walls: tuple[Point, ...] = ()


STAGES = (
    Stage(
        '01  잔향의 문',
        'C로 녹화 → A 발판에서 약 4초 대기 → C로 재현 → 본체로 문 통과',
        1, Point(112, 0), Point(1022, 0),
        gates=(Gate('A', Point(267, 0), Point(740, 0)),),
    ),
    Stage(
        '02  사냥꾼의 시야',
        '분신으로 아래층 A 발판을 유지하고, 본체는 왼쪽 사다리로 윗길을 달리세요.',
        2, Point(111, 0), Point(1022, 1),
        stairs=(Stair(145, 0), Stair(659, 0)),
        gates=(Gate('A', Point(401, 0), Point(794, 1)),),
        enemies=(EnemySpawn('beast', Point(720, 0), (623, 818)),),
        walls=(Point(992, 0),),
    ),
    Stage(
        '03  세 층의 봉인',
        'A 문을 지난 뒤 B 발판으로 새로 녹화하세요. 보라색 체력 표시가 있는 적은 A/S로 공격할 수 있어요.',
        3, Point(112, 0), Point(1043, 2),
        stairs=(Stair(151, 0), Stair(651, 1)),
        gates=(
            Gate('A', Point(324, 0), Point(552, 1)),
            Gate('B', Point(747, 1), Point(870, 2)),
        ),
        enemies=(
            EnemySpawn('warden', Point(845, 0), (744, 978)),
            EnemySpawn('crawler', Point(901, 1), (830, 1019)),
            EnemySpawn('watcher', Point(976, 2), (950, 1004)),
        ),
    ),
)
