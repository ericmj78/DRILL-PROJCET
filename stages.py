from dataclasses import dataclass


LEFT, RIGHT = 48, 2192
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
    lever: Point | None = None


@dataclass(frozen=True)
class Weapon:
    name: str
    reach: int
    cooldown: float
    damage: int = 1


WEAPONS = (
    Weapon('맨손', ATTACK_RANGE, ATTACK_COOLDOWN),
    Weapon('단검', 70, 0.23),
    Weapon('한손검', 99, 0.38),
    Weapon('전투 망치', 91, 0.62, damage=2),
    Weapon('마력 지팡이', 113, 0.46),
)


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
        '분신으로 A와 B 발판을 차례로 유지하며 두 문을 통과하세요.',
        1, Point(112, 0), Point(2100, 0),
        gates=(
            Gate('A', Point(267, 0), Point(740, 0), lever=Point(820, 0)),
            Gate('B', Point(1040, 0), Point(1510, 0)),
        ),
        enemies=(EnemySpawn('crawler', Point(1820, 0), (1740, 1920)),),
    ),
    Stage(
        '02  사냥꾼의 시야',
        '분신으로 아래층 A 발판을 유지하고, 본체는 왼쪽 사다리로 윗길을 달리세요.',
        2, Point(111, 0), Point(2100, 1),
        stairs=(Stair(145, 0), Stair(659, 0)),
        gates=(Gate('A', Point(401, 0), Point(794, 1)),),
        enemies=(
            EnemySpawn('beast', Point(720, 0), (623, 818)),
            EnemySpawn('watcher', Point(1650, 1), (1550, 1750)),
        ),
        walls=(Point(992, 0),),
    ),
    Stage(
        '03  세 층의 봉인',
        'A 문을 지난 뒤 B 발판으로 새로 녹화하세요. 보라색 체력 표시가 있는 적은 A/S로 공격할 수 있어요.',
        3, Point(112, 0), Point(2100, 2),
        stairs=(Stair(151, 0), Stair(651, 1)),
        gates=(
            Gate('A', Point(324, 0), Point(552, 1)),
            Gate('B', Point(747, 1), Point(870, 2)),
        ),
        enemies=(
            EnemySpawn('warden', Point(845, 0), (744, 978)),
            EnemySpawn('crawler', Point(901, 1), (830, 1019)),
            EnemySpawn('watcher', Point(976, 2), (950, 1004)),
            EnemySpawn('crawler', Point(1680, 2), (1580, 1780)),
        ),
    ),
    Stage(
        '04  반대편 발판',
        '분신을 왼쪽 A 발판에 약 4초 두고, 본체는 오른쪽으로 달려 문을 통과하세요.',
        1, Point(340, 0), Point(2100, 0),
        gates=(Gate('A', Point(160, 0), Point(900, 0)),),
        enemies=(EnemySpawn('watcher', Point(1660, 0), (1560, 1760)),),
    ),
    Stage(
        '05  아래층의 열쇠',
        '분신만 사다리로 내려가 A 발판에 약 4초 머물게 하세요. 본체는 위층 왼쪽 출구로 가세요.',
        2, Point(2065, 1), Point(104, 1),
        stairs=(Stair(2030, 0),),
        gates=(Gate('A', Point(1910, 0), Point(1420, 1)),),
        enemies=(EnemySpawn('crawler', Point(650, 1), (550, 750)),),
    ),
    Stage(
        '06  시야 밖의 길',
        '위층에서 추적을 끊고, 분신으로 적을 왼쪽에 유인하세요. 본체는 오른쪽 사다리로 내려가세요.',
        2, Point(310, 0), Point(2100, 0),
        stairs=(Stair(320, 0), Stair(680, 0)),
        enemies=(
            EnemySpawn('beast', Point(520, 0), (460, 635)),
            EnemySpawn('watcher', Point(1650, 0), (1550, 1750)),
        ),
    ),
    Stage(
        '07  사다리 밑의 기다림',
        '분신이 2층 A 발판을 밟고 오른쪽으로 적을 유인하면, 문을 지난 본체는 오른쪽 사다리로 오르세요.',
        2, Point(111, 0), Point(2100, 1),
        stairs=(Stair(145, 0), Stair(928, 0)),
        gates=(Gate('A', Point(440, 1), Point(800, 0)),),
        enemies=(
            EnemySpawn('beast', Point(820, 1), (760, 890)),
            EnemySpawn('crawler', Point(1650, 1), (1550, 1750)),
        ),
    ),
    Stage(
        '08  두 번째 잔향',
        'A 문을 지나 사다리 앞에서 B 발판으로 새 분신을 녹화하세요. 본체는 올라가 왼쪽으로 가세요.',
        2, Point(120, 0), Point(105, 1),
        stairs=(Stair(1300, 0),),
        gates=(
            Gate('A', Point(245, 0), Point(540, 0)),
            Gate('B', Point(1490, 0), Point(1050, 1)),
        ),
        enemies=(EnemySpawn('watcher', Point(650, 1), (550, 750)),),
    ),
    Stage(
        '09  되돌아가는 발자국',
        'A 문을 지난 뒤 새 분신을 사다리 너머 왼쪽 B 발판으로 보내세요. 본체는 2층에서 오른쪽으로 가세요.',
        3, Point(112, 0), Point(2100, 2),
        stairs=(Stair(690, 0), Stair(950, 1)),
        gates=(
            Gate('A', Point(220, 0), Point(520, 0)),
            Gate('B', Point(548, 1), Point(835, 1)),
        ),
        enemies=(
            EnemySpawn('crawler', Point(929, 1), (885, 1000)),
            EnemySpawn('watcher', Point(1650, 2), (1550, 1750)),
        ),
    ),
    Stage(
        '10  마지막 잔향',
        'A 문을 지나 첫 사다리 앞에서 1층 B 발판으로 새 분신을 녹화하고, 본체는 3층 출구로 가세요.',
        3, Point(100, 0), Point(2100, 2),
        stairs=(Stair(670, 0), Stair(953, 1)),
        gates=(
            Gate('A', Point(252, 0), Point(510, 0), lever=Point(590, 0)),
            Gate('B', Point(820, 0), Point(846, 1)),
        ),
        enemies=(
            EnemySpawn('beast', Point(1008, 0), (948, 1060)),
            EnemySpawn('watcher', Point(955, 1), (905, 1005)),
            EnemySpawn('crawler', Point(1650, 2), (1550, 1750)),
        ),
    ),
)
