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
class SequenceGate:
    sensors: tuple[Point, ...]
    door: Point


@dataclass(frozen=True)
class SyncGate:
    player_sensor: Point
    echo_sensor: Point
    door: Point


@dataclass(frozen=True)
class WatchGate:
    focus: Point
    door: Point


@dataclass(frozen=True)
class IsolationRoom:
    door: Point
    lever: Point
    exit_gate: Point
    inside_x: int


@dataclass(frozen=True)
class EchoBridge:
    points: tuple[Point, ...]
    echo_floor: int


@dataclass(frozen=True)
class BalanceLift:
    platform: Point
    weight: Point


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
    sequence: SequenceGate | None = None
    sync_gate: SyncGate | None = None
    hidden_hazards: tuple[Point, ...] = ()
    guard: Point | None = None
    watch_gate: WatchGate | None = None
    isolation: IsolationRoom | None = None
    bridge: EchoBridge | None = None
    lift: BalanceLift | None = None


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
        'A 문을 지난 뒤 분신을 아래층 감시 구역에 두고 본체로 보안문을 지나세요.',
        2, Point(111, 0), Point(2100, 1),
        stairs=(Stair(145, 0), Stair(659, 0), Stair(1200, 0)),
        gates=(Gate('A', Point(401, 0), Point(794, 1)),),
        enemies=(
            EnemySpawn('beast', Point(720, 0), (623, 818)),
            EnemySpawn('watcher', Point(1650, 1), (1550, 1750)),
        ),
        walls=(Point(992, 0),),
        watch_gate=WatchGate(Point(1300, 0), Point(1800, 1)),
    ),
    Stage(
        '03  세 층의 봉인',
        'B 문을 지나 분신으로 수호자의 공격을 유도하고 빈틈에 통과하세요.',
        3, Point(112, 0), Point(2100, 2),
        stairs=(Stair(151, 0), Stair(651, 1), Stair(1360, 1)),
        gates=(
            Gate('A', Point(324, 0), Point(552, 1)),
            Gate('B', Point(747, 1), Point(870, 2)),
        ),
        enemies=(
            EnemySpawn('warden', Point(845, 0), (744, 978)),
            EnemySpawn('crawler', Point(901, 1), (830, 1019)),
            EnemySpawn('watcher', Point(976, 2), (950, 1004)),
            EnemySpawn('warden', Point(1450, 2), (1450, 1450)),
            EnemySpawn('crawler', Point(1680, 2), (1580, 1780)),
        ),
        guard=Point(1450, 2),
    ),
    Stage(
        '04  반대편 발판',
        'A 문을 지난 뒤 분신이 1→2→3 감지 지점을 지나도록 녹화하세요.',
        1, Point(340, 0), Point(2100, 0),
        gates=(Gate('A', Point(160, 0), Point(900, 0)),),
        sequence=SequenceGate((Point(1300, 0), Point(1460, 0), Point(1620, 0)), Point(1850, 0)),
    ),
    Stage(
        '05  아래층의 열쇠',
        'A 문 뒤에서 분신으로 몬스터를 격리실로 유인하고 위층 레버를 당기세요.',
        2, Point(2065, 1), Point(104, 1),
        stairs=(Stair(2030, 0), Stair(1350, 0)),
        gates=(Gate('A', Point(1910, 0), Point(1420, 1)),),
        enemies=(
            EnemySpawn('crawler', Point(650, 1), (550, 750)),
            EnemySpawn('beast', Point(1250, 0), (1200, 1280)),
        ),
        isolation=IsolationRoom(Point(1500, 0), Point(1320, 1), Point(1000, 1), 1540),
    ),
    Stage(
        '06  시야 밖의 길',
        '오른쪽 사다리에서 분신을 아래층으로 보내고, 생기는 위층 발판을 따라가세요.',
        2, Point(310, 0), Point(2100, 0),
        stairs=(Stair(320, 0), Stair(680, 0), Stair(1250, 0), Stair(1850, 0)),
        enemies=(
            EnemySpawn('beast', Point(520, 0), (460, 635)),
            EnemySpawn('watcher', Point(1980, 0), (1900, 2070)),
        ),
        walls=(Point(1800, 0),),
        bridge=EchoBridge((Point(1450, 1), Point(1520, 1), Point(1590, 1)), 0),
    ),
    Stage(
        '07  사다리 밑의 기다림',
        'A 문을 지나 분신을 균형 발판에 두고 본체는 승강 발판에 올라서세요.',
        2, Point(111, 0), Point(2100, 1),
        stairs=(Stair(145, 0),),
        gates=(Gate('A', Point(440, 1), Point(800, 0)),),
        enemies=(
            EnemySpawn('beast', Point(820, 1), (760, 890)),
            EnemySpawn('crawler', Point(1650, 1), (1550, 1750)),
        ),
        lift=BalanceLift(Point(1450, 0), Point(1300, 0)),
    ),
    Stage(
        '08  두 번째 잔향',
        'B 문을 지나 분신과 각 층의 감지선을 비슷한 시간에 통과하세요.',
        2, Point(120, 0), Point(105, 1),
        stairs=(Stair(1300, 0),),
        gates=(
            Gate('A', Point(245, 0), Point(540, 0)),
            Gate('B', Point(1490, 0), Point(1050, 1)),
        ),
        enemies=(EnemySpawn('watcher', Point(650, 1), (550, 750)),),
        sync_gate=SyncGate(Point(800, 1), Point(800, 0), Point(500, 1)),
    ),
    Stage(
        '09  되돌아가는 발자국',
        'B 문을 지나면 분신으로 위층의 숨은 함정을 찾고 아래층으로 우회하세요.',
        3, Point(112, 0), Point(2100, 2),
        stairs=(Stair(690, 0), Stair(950, 1), Stair(1800, 1)),
        gates=(
            Gate('A', Point(220, 0), Point(520, 0)),
            Gate('B', Point(548, 1), Point(835, 1)),
        ),
        enemies=(
            EnemySpawn('crawler', Point(929, 1), (885, 1000)),
            EnemySpawn('watcher', Point(1650, 2), (1550, 1750)),
        ),
        hidden_hazards=(Point(1400, 2),),
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
