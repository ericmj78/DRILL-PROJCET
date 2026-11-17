from dataclasses import dataclass


LEFT, RIGHT = 48, 2192
FLOOR_Y = (156, 320, 484)
STEP = 1 / 60
MOVE_SPEED = 230
MAX_RECORD_SECONDS = 9
# 본체 레벨 (BALANCE.md). 레벨 1~9에서 다음 레벨까지 필요한 경험치이며 최대 레벨은 10이다.
LEVEL_UP_XP = (30, 45, 60, 80, 100, 120, 140, 160, 180)
HAZARD_RATIO = 0.2      # 숨은 함정은 최대 체력의 20%를 깎는다.
LATE_STAGE_SCALE = 1.6  # 7~9스테이지의 몬스터 체력·피해 배율


def max_health(level: int) -> int:
    return 25 + 3 * (level - 1)


def attack_power(level: int) -> int:
    return 4 + (level - 1)
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
    """감시등. 평소에는 door 주변 길을 비추고, 분신이 focus 근처에 오면 분신을 따라 돌아간다."""
    focus: Point
    door: Point          # 감시등이 지키는 길의 가운데
    zone: int = 80       # 빛이 덮는 반폭. 이 안에 들어간 본체는 들킨다.


@dataclass(frozen=True)
class IsolationRoom:
    door: Point
    lever: Point
    exit_gate: Point
    inside_x: int


@dataclass(frozen=True)
class EchoBridge:
    """낭떠러지. 분신이 지나간 자리에만 잠깐 빛 발판이 생긴다."""
    floor: int
    left: int
    right: int
    tile: int = 60        # 발판 한 칸의 폭
    life: float = 2.2     # 분신이 지나간 뒤 발판이 남아 있는 시간


@dataclass(frozen=True)
class BalanceLift:
    platform: Point
    weight: Point


@dataclass(frozen=True)
class Weapon:
    name: str
    reach: int
    cooldown: float
    bonus: int = 0  # 피해 = 공격력 + 무기 보정 + 공격 보정(베기 +1)


WEAPONS = (
    Weapon('맨손', ATTACK_RANGE, ATTACK_COOLDOWN, bonus=-1),
    Weapon('단검', 70, 0.23, bonus=-2),
    Weapon('한손검', 99, 0.38),
    Weapon('전투 망치', 91, 0.62, bonus=3),
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
    damage: int = 0          # 본체가 맞을 때 깎이는 체력
    xp: int = 0              # 처치했을 때 얻는 경험치
    damage_ratio: float = 0  # 일부 적은 본체 최대 체력에 비례해 피해를 준다.


ENEMY_KINDS = {
    'beast': EnemyKind('monster_01_hornbeast.png', 112, 250, 43, 45, 115, xp=20, damage_ratio=0.4),
    'warden': EnemyKind('monster_02_stone_warden.png', 92, 220, 48, 60, 105, xp=28, damage_ratio=0.5),
    'watcher': EnemyKind('monster_03_watcher.png', 114, 215, 39, 12, 86, damage=8, xp=12),
    'crawler': EnemyKind('monster_spider.png', 88, 185, 38, 10, 100, damage=7, xp=10),
    'jailer_boss': EnemyKind('monster_concepts/prison-jailer-boss.png', 65, 235, 70, 95, 260, damage=8, xp=80),
    'magic_book': EnemyKind('monster_concepts/magic-book.png', 75, 175, 38, 15, 76, damage=8, xp=10),
    'potion_slime': EnemyKind('monster_concepts/potion-slime.png', 55, 160, 36, 22, 85, damage=9, xp=14),
    'magic_armor': EnemyKind('monster_concepts/magic-armor.png', 65, 180, 48, 32, 115, damage=11, xp=20),
    'magic_armor_guard': EnemyKind('monster_concepts/magic-armor.png', 112, 600, 43, 40, 115, xp=24, damage_ratio=0.4),
    'witch': EnemyKind('monster_concepts/witch.png', 60, 180, 50, 30, 112, damage=10, xp=22),
    'time_thief': EnemyKind('monster_concepts/time-thief.png', 65, 175, 42, 20, 108, damage=7, xp=16),
    'cursed_lantern': EnemyKind('monster_concepts/cursed-lantern.png', 70, 185, 42, 16, 112, damage=7, xp=14),
    'broken_jester': EnemyKind('monster_concepts/broken-jester.png', 75, 185, 40, 18, 104, damage=7, xp=15),
    'grand_witch': EnemyKind('monster_concepts/grand-witch-boss.png', 65, 220, 55, 145, 230, damage=11, xp=120),
    'echo_knight': EnemyKind('monster_concepts/echo-knight-boss.png', 70, 260, 65, 180, 240, damage=12, xp=160),
}

BOSS_KINDS = frozenset(('jailer_boss', 'grand_witch', 'echo_knight'))


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
    echo_seconds: float = MAX_RECORD_SECONDS  # 이 스테이지에서 분신 한 번에 녹화할 수 있는 시간
    elevators: tuple[Stair, ...] = ()
    enemy_scale: float = 1.0  # 몬스터 체력·피해 배율


STAGES = (
    Stage(
        '01  잔향의 문',
        'A 발판을 밟으면 문이 열립니다. B 발판을 누르도록 분신을 녹화하세요.',
        3, Point(112, 0), Point(2100, 2),
        elevators=(Stair(1950, 0), Stair(350, 1)),
        gates=(
            Gate('A', Point(267, 0), Point(740, 0)),
            Gate('B', Point(430, 0), Point(1400, 0)),
        ),
        enemies=(
            EnemySpawn('crawler', Point(1100, 0), (1000, 1200)),
            EnemySpawn('crawler', Point(1800, 0), (1700, 1900)),
        ),
        echo_seconds=5.5,
    ),
    Stage(
        '02  사냥꾼의 시야',
        '뿔짐승을 처치하거나 분신으로 유인한 뒤 아래층을 지나가세요.',
        3, Point(111, 1), Point(2100, 2),
        stairs=(Stair(659, 0), Stair(1200, 0)),
        elevators=(Stair(1950, 1),),
        enemies=(
            EnemySpawn('beast', Point(900, 0), (720, 1100)),
            EnemySpawn('watcher', Point(1650, 1), (1550, 1750)),
        ),
        walls=(Point(900, 1),),
        watch_gate=WatchGate(Point(1300, 0), Point(1800, 1)),
        echo_seconds=5,
    ),
    Stage(
        '03  간수의 다섯 층',
        '승강기 앞에서 ↑↓로 이동하세요. 분신과 문을 지나 5층의 간수를 처치하세요.',
        5, Point(112, 0), Point(2100, 4),
        elevators=(Stair(151, 0), Stair(700, 1), Stair(1300, 1), Stair(1800, 2), Stair(400, 3)),
        gates=(
            Gate('A', Point(324, 0), Point(500, 1), lever=Point(550, 1)),
            Gate('C', Point(600, 1), Point(800, 1), lever=Point(950, 1)),
            Gate('B', Point(1000, 1), Point(870, 2)),
        ),
        enemies=(
            EnemySpawn('crawler', Point(400, 0), (350, 450)),
            EnemySpawn('beast', Point(1700, 1), (1400, 1800)),
            EnemySpawn('watcher', Point(1080, 2), (1000, 1160)),
            EnemySpawn('warden', Point(1500, 2), (1500, 1500)),
            EnemySpawn('crawler', Point(1000, 3), (900, 1100)),
            EnemySpawn('watcher', Point(1500, 3), (1400, 1600)),
            EnemySpawn('jailer_boss', Point(1120, 4), (1050, 1190)),
        ),
        walls=(Point(1100, 1),),
        guard=Point(1500, 2),
        echo_seconds=8,
    ),
    Stage(
        '04  반대편 발판',
        '1→2→3 순서로 발판을 밟아 보안문을 여세요. 꼭대기 층 낭떠러지는 분신이 지나간 자리만 밟을 수 있습니다.',
        4, Point(340, 0), Point(2100, 3),
        elevators=(Stair(1980, 0), Stair(1980, 1), Stair(300, 2)),
        bridge=EchoBridge(3, 700, 1500),
        gates=(Gate('A', Point(160, 0), Point(900, 0)),),
        enemies=(
            EnemySpawn('magic_book', Point(700, 0), (620, 780)),
            EnemySpawn('potion_slime', Point(1120, 0), (1060, 1200)),
            EnemySpawn('magic_armor', Point(1380, 0), (1320, 1440)),
            EnemySpawn('witch', Point(2000, 0), (1940, 2060)),
        ),
        sequence=SequenceGate((Point(1460, 0), Point(1300, 0), Point(1620, 0)), Point(1850, 0)),
        echo_seconds=5,
    ),
    Stage(
        '05  아래층의 열쇠',
        'A 발판의 분신은 갑옷의 미끼도 됩니다. 문을 지나 갑옷이 격리실에 들어온 순간 E 레버를 당기세요.',
        4, Point(2065, 1), Point(104, 3),
        elevators=(Stair(180, 1), Stair(180, 2)),
        stairs=(Stair(2030, 0), Stair(1350, 0)),  # 1350: 실패했을 때 레버 옆에서 미끼를 다시 보내는 길
        gates=(Gate('A', Point(1700, 0), Point(1420, 1)),),
        enemies=(
            EnemySpawn('magic_armor', Point(650, 1), (550, 750)),
            EnemySpawn('magic_armor_guard', Point(1300, 0), (1250, 1450)),
            EnemySpawn('magic_book', Point(1750, 1), (1680, 1810)),
            EnemySpawn('potion_slime', Point(350, 1), (290, 410)),
        ),
        isolation=IsolationRoom(Point(1500, 0), Point(1320, 1), Point(1000, 1), 1540),
        echo_seconds=5,
    ),
    Stage(
        '06  대마녀의 다섯 층',
        '분신으로 균형 발판을 작동하고, 승강기를 타고 5층 대마녀에게 가세요.',
        5, Point(111, 0), Point(2100, 4),
        stairs=(Stair(145, 0),),
        elevators=(Stair(400, 1), Stair(1800, 2), Stair(400, 3)),
        gates=(
            Gate('A', Point(440, 1), Point(800, 0)),
            Gate('C', Point(1150, 0), Point(1380, 0)),
        ),
        enemies=(
            EnemySpawn('potion_slime', Point(1650, 1), (1550, 1750)),
            EnemySpawn('magic_book', Point(400, 0), (340, 460)),
            EnemySpawn('magic_armor', Point(1030, 0), (970, 1090)),
            EnemySpawn('magic_book', Point(950, 2), (880, 1020)),
            EnemySpawn('potion_slime', Point(1450, 2), (1380, 1520)),
            EnemySpawn('magic_armor', Point(1250, 3), (1180, 1320)),
            EnemySpawn('witch', Point(1650, 3), (1580, 1720)),
            EnemySpawn('grand_witch', Point(1120, 4), (1050, 1190)),
        ),
        lift=BalanceLift(Point(1450, 0), Point(1300, 0)),
        echo_seconds=3.5,
    ),
    Stage(
        '07  두 번째 잔향',
        '분신은 B 발판을 밟은 뒤 아래층 동시 발판으로 가야 합니다. 두 발판을 함께 밟으면 문이 열립니다.',
        5, Point(120, 0), Point(2100, 4),
        stairs=(Stair(1300, 0), Stair(150, 1), Stair(1850, 2), Stair(150, 3)),
        gates=(
            Gate('A', Point(245, 0), Point(540, 0)),
            Gate('B', Point(1490, 0), Point(1050, 1)),
        ),
        enemies=(
            EnemySpawn('cursed_lantern', Point(350, 1), (250, 450)),
            EnemySpawn('broken_jester', Point(950, 0), (850, 1150)),
        ),
        sync_gate=SyncGate(Point(800, 1), Point(800, 0), Point(500, 1)),
        echo_seconds=4.5,
        enemy_scale=LATE_STAGE_SCALE,
    ),
    Stage(
        '08  되돌아가는 발자국',
        '3층의 함정은 분신 곁에서만 보입니다. 분신을 앞세워 뛰어넘고, 새 분신을 D 발판으로 돌려보내세요.',
        3, Point(112, 0), Point(2100, 2),
        stairs=(Stair(690, 0), Stair(950, 1)),
        gates=(
            Gate('A', Point(220, 0), Point(520, 0)),
            Gate('B', Point(548, 1), Point(835, 1)),
            Gate('D', Point(1080, 2), Point(1950, 2)),
        ),
        enemies=(
            EnemySpawn('broken_jester', Point(929, 1), (885, 1000)),
            EnemySpawn('cursed_lantern', Point(1150, 2), (1100, 1200)),
        ),
        hidden_hazards=(Point(1300, 2), Point(1520, 2), Point(1740, 2)),
        echo_seconds=4.5,
        enemy_scale=LATE_STAGE_SCALE,
    ),
    Stage(
        '09  마지막 잔향',
        '유인과 숨은 함정을 지나 승강기를 타고 마지막 보스를 처치하세요.',
        4, Point(100, 0), Point(2100, 3),
        elevators=(Stair(2000, 2),),
        stairs=(Stair(670, 0), Stair(1300, 1)),
        gates=(
            Gate('A', Point(252, 0), Point(510, 0)),
            Gate('B', Point(820, 0), Point(1000, 1)),
        ),
        enemies=(
            EnemySpawn('broken_jester', Point(1008, 0), (948, 1060)),
            EnemySpawn('cursed_lantern', Point(1180, 1), (1100, 1250)),
            EnemySpawn('time_thief', Point(1500, 2), (1500, 1500)),
            EnemySpawn('echo_knight', Point(1120, 3), (1050, 1190)),
        ),
        hidden_hazards=(Point(1700, 2), Point(1900, 2)),
        guard=Point(1500, 2),
        echo_seconds=4,
        enemy_scale=LATE_STAGE_SCALE,
    ),
)

# One visible stage may contain multiple connected map sections.
STAGE_GROUPS = ((0,), (1, 2), (3,), (4, 5), (6,), (7, 8))
STAGE_TITLES = (
    '01  잔향의 문', '02  사냥꾼과 간수', '03  반대편 발판',
    '04  격리실과 대마녀', '05  두 번째 잔향', '06  마지막 잔향',
)


def stage_group_index(section_index):
    return next(i for i, group in enumerate(STAGE_GROUPS) if section_index in group)


def next_section_in_stage(section_index):
    group = STAGE_GROUPS[stage_group_index(section_index)]
    position = group.index(section_index)
    return group[position + 1] if position + 1 < len(group) else None
