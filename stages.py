from dataclasses import dataclass
from math import pi, sin


LEFT, RIGHT = 48, 2192
FLOOR_Y = (156, 320, 484)
STEP = 1 / 60
MOVE_SPEED = 230
MAX_RECORD_SECONDS = 10
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
class JumpBlock:
    """점프 블록. 점프 높이가 height 이상일 때만 넘어가고, 걷거나 낮게 뛰면 벽처럼 막힌다.

    본체·보통 점프는 높이 48, 뿔짐승 분신의 슈퍼 점프(Space 1초)는 높이 100이라
    기본 높이 70은 슈퍼 점프로만 넘을 수 있다.
    """
    floor: int
    x: int
    height: int = 70
    width: int = 44


@dataclass(frozen=True)
class Platform:
    """공중 발판. 바닥 위 height 높이에 있다. hidden이면 외눈 유령 분신의 레이더로 드러난 동안만 밟힌다.
    swing이 있으면 left~right 자리를 가운데로 좌우 swing px만큼 period초마다 한 번 오간다."""
    floor: int
    left: int
    right: int
    height: int
    hidden: bool = True
    swing: int = 0
    period: float = 1.0
    phase: float = 0.0     # 0~1, 처음 위치

    def shift(self, clock: float) -> float:
        return self.swing * sin(2 * pi * (clock / self.period + self.phase)) if self.swing else 0.0


@dataclass(frozen=True)
class Switch:
    """공중 턱 위의 스위치. 분신(녹화 중인 분신 포함)이 그 높이에 올라서면 door가 열린 채로 고정된다."""
    floor: int
    x: int
    height: int
    door: Point


@dataclass(frozen=True)
class SkyPuzzle:
    """하늘 땅 퍼즐. 마법책 분신을 녹화하는 동안 마우스로 떠 있는 땅(blocks의 (x, 높이))을
    분신 둘레 reach 안에서 끌어 옮긴다. 땅은 저마다 좌우로 떠다니고, 옮겨 놓은 땅은 잠시 멈췄다가 다시 떠다닌다.
    본체가 switches((x, 높이))를 1→2→3 순서로 밟아야 출구가 열리고,
    순서가 틀리면 스위치와 땅이 모두 처음 자리로 돌아간다."""
    blocks: tuple[tuple[int, int], ...]
    switches: tuple[tuple[int, int], ...]
    width: int = 100
    reach: int = 340


SKY_STEP = 38   # 보통 점프(높이 48)로 오를 수 있는 한 단


@dataclass(frozen=True)
class Lens:
    """렌즈 건축물. 외눈 유령 분신의 레이더 원이 닿으면 그 층의 숨은 발판이 모두 드러난다."""
    floor: int
    x: int
    height: int


@dataclass(frozen=True)
class WebBeam:
    floor: int
    left: int
    right: int
    underside: int
    height: int = 70


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
    # 층 유령: 정해진 높이에서 좌우로 떠다니며 닿으면 최대 체력의 35% (세 번 닿으면 쓰러진다).
    'tier_ghost': EnemyKind('monster_03_watcher.png', 60, 0, 30, 8, 70, xp=6, damage_ratio=0.35),
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
    height: int = 0   # 바닥 위로 떠 있는 높이 (층 유령)


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
    web_beams: tuple[WebBeam, ...] = ()
    jump_blocks: tuple[JumpBlock, ...] = ()  # 점프 맵용. 예: jump_blocks=(JumpBlock(0, 900),)
    poison_zones: tuple[tuple[int, int, int], ...] = ()
    poison_platforms: tuple[tuple[int, int, int], ...] = ()
    pits: tuple[tuple[int, int, int], ...] = ()   # (층, 왼쪽, 오른쪽). 발판 없이 들어가면 떨어져 죽는다.
    platforms: tuple[Platform, ...] = ()
    floor_height: int = 400     # 층 사이 간격. 두 층을 합친 통합방은 800
    reveal_seconds: float = 10.0  # 외눈 유령 분신이 사라진 뒤 숨은 발판이 보이는 시간
    switches: tuple[Switch, ...] = ()
    lens: Lens | None = None
    sky: SkyPuzzle | None = None


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
        web_beams=(WebBeam(0, 680, 800, 215),
                   WebBeam(1, 628, 748, 175), WebBeam(1, 1087, 1207, 175),
                   WebBeam(1, 1405, 1525, 175)),
        # 2층: 독 웅덩이 3개 사이에 거미가 쉬어 가는 바닥 2개
        poison_zones=((1, 518, 885), (1, 1027, 1273), (1, 1355, 1525)),
        poison_platforms=((1, 885, 1027), (1, 1273, 1355)),
        # 3층: 가운데 구덩이 위에 보이지 않는 발판이 1~4단 지그재그로 놓여 있다.
        pits=((2, 540, 1798),),
        platforms=(
            Platform(2, 600, 700, 0), Platform(2, 760, 860, 36), Platform(2, 650, 740, 72),
            Platform(2, 800, 1100, 108), Platform(2, 1180, 1280, 36), Platform(2, 1340, 1420, 72),
            Platform(2, 1480, 1580, 108), Platform(2, 1660, 1740, 0),
        ),
        enemies=(
            EnemySpawn('crawler', Point(1100, 0), (1000, 1200)),
            EnemySpawn('crawler', Point(1800, 0), (1700, 1900)),
            EnemySpawn('watcher', Point(450, 2), (380, 510)),
            # 단마다 떠다니는 유령. 위 단일수록 빠르고 넓게 돈다.
            EnemySpawn('tier_ghost', Point(650, 2), (580, 720), height=0),
            EnemySpawn('tier_ghost', Point(1000, 2), (760, 1280), height=36),
            EnemySpawn('tier_ghost', Point(1000, 2), (650, 1420), height=72),
            EnemySpawn('tier_ghost', Point(1200, 2), (800, 1580), height=108),
        ),
        echo_seconds=MAX_RECORD_SECONDS,
    ),
    Stage(
        '02  뿔짐승의 도약',
        '뿔짐승을 처치해 분신을 얻으세요. 분신으로 Space를 1초 눌러 슈퍼 점프로 발판을 올라 스위치를 누르세요.',
        2, Point(112, 0), Point(2140, 1),
        floor_height=800,
        # [1·2층 통합방] 바닥이 있다. 발판 사이 높이는 90이라 보통 점프(48)로는 못 오르고
        # 뿔짐승 분신의 슈퍼 점프(100)로만 오른다. 슈퍼 점프는 내려오며 발판 높이를 지날 때까지
        # 최대 약 150px 날아간다. 발판은 폭 35~40으로 좁고 간격은 125~145라 끝에서 뛰고 제때 멈춰야 한다.
        # 방향도 오른쪽·왼쪽으로 번갈아 바뀐다. 마지막 턱은 발판 끝에서 끝까지 날아야 닿는다(여유 약 10px).
        # 오른쪽 위 턱의 스위치가 아래 잠긴 문을 연다.
        # [3·4층 통합방] 바닥이 뚫려 있다(떨어지면 죽는다). 발판은 숨어 있고, 외눈 유령 분신의
        # 레이더가 오른쪽 렌즈에 닿으면 모두 드러난다. 발판은 좌우로 움직여서 다음 발판이
        # 다가오는 때를 보고 1초 먼저 모으기 시작해야 한다. 왼쪽 위 턱의 스위치가 출구 문을 연다.
        platforms=(
            Platform(0, 640, 680, 90, False), Platform(0, 790, 825, 180, False),
            Platform(0, 700, 735, 270, False), Platform(0, 555, 590, 360, False),
            Platform(0, 700, 735, 450, False), Platform(0, 860, 895, 540, False),
            Platform(0, 1035, 1880, 630, False),
            Platform(1, 1665, 1735, 90, swing=70, period=3.0),
            Platform(1, 1485, 1555, 180, swing=80, period=2.6, phase=0.25),
            Platform(1, 1305, 1375, 270, swing=60, period=2.2, phase=0.5),
            Platform(1, 1125, 1195, 360, swing=90, period=3.4, phase=0.1),
            Platform(1, 945, 1015, 450, swing=70, period=2.4, phase=0.6),
            Platform(1, 765, 835, 540, swing=80, period=2.8, phase=0.35),
            Platform(1, 200, 610, 630),
        ),
        pits=((1, 48, 1820),),
        switches=(Switch(0, 1820, 630, Point(1790, 0)), Switch(1, 300, 630, Point(2060, 1))),
        lens=Lens(1, 1990, 230),
        elevators=(Stair(1900, 0),),
        enemies=(EnemySpawn('beast', Point(520, 0), (420, 700)),),
        reveal_seconds=25.0,
        echo_seconds=20,   # 발판 일곱 번을 슈퍼 점프(1초 모으기)로 오르려면 10초로는 모자라다
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
        echo_seconds=MAX_RECORD_SECONDS,
    ),
    Stage(
        '04  염력의 하늘 땅',
        '떠다니는 하늘 땅을 한 단씩 갈아타며 1→2→3 스위치를 순서대로 밟으세요. '
        '마법책 분신을 녹화하는 동안 마우스로 땅을 끌어다 놓으면 잠시 멈춥니다.',
        # [1·2·3층 통합방] 출구는 가운데 바닥에 있고 세 스위치를 순서대로 밟아야 열린다.
        # 스위치는 벽에 붙은 작은 턱 위에 있다: 1번 왼쪽 중간(10단), 2번 왼쪽 맨 위(22단), 3번 오른쪽 위(16단).
        # 턱까지 가는 길은 없다. 하늘 섬 21개가 1~21단에 하나씩 있고 저마다 좌우로 아무렇게나 떠다닌다.
        # 바로 윗단 섬이 가까이 올 때 뛰어 한 단씩 오른다. 마법책 분신으로 섬을 끌어다 놓으면
        # 그 자리에 몇 초(world.SKY_PIN) 멈췄다가 다시 떠다닌다. 화면은 바닥 위 1000까지 보인다.
        1, Point(1000, 0), Point(1240, 0),
        floor_height=800,
        platforms=(Platform(0, 55, 175, SKY_STEP * 10, False), Platform(0, 55, 175, SKY_STEP * 22, False),
                   Platform(0, 2060, 2185, SKY_STEP * 16, False)),
        sky=SkyPuzzle(blocks=tuple((200 + 677 * i % 1840, SKY_STEP * (i + 1)) for i in range(21)),
                      switches=((110, SKY_STEP * 10), (110, SKY_STEP * 22), (2130, SKY_STEP * 16))),
        enemies=(
            EnemySpawn('magic_book', Point(700, 0), (620, 780)),
            EnemySpawn('potion_slime', Point(450, 0), (390, 510)),
            EnemySpawn('magic_armor', Point(1600, 0), (1540, 1660)),
        ),
        echo_seconds=30,   # 땅을 반대쪽 벽까지 날라 디딤돌을 오르려면 시간이 더 든다
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
        echo_seconds=MAX_RECORD_SECONDS,
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
        echo_seconds=MAX_RECORD_SECONDS,
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
        echo_seconds=MAX_RECORD_SECONDS,
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
        echo_seconds=MAX_RECORD_SECONDS,
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
        echo_seconds=MAX_RECORD_SECONDS,
        enemy_scale=LATE_STAGE_SCALE,
    ),
)

# One visible stage may contain multiple connected map sections.
STAGE_GROUPS = ((0,), (1, 2), (3,), (4, 5), (6,), (7, 8))
STAGE_TITLES = (
    '01  잔향의 문', '02  사냥꾼과 간수', '03  염력의 하늘 땅',
    '04  격리실과 대마녀', '05  두 번째 잔향', '06  마지막 잔향',
)


def stage_group_index(section_index):
    return next(i for i, group in enumerate(STAGE_GROUPS) if section_index in group)


def next_section_in_stage(section_index):
    group = STAGE_GROUPS[stage_group_index(section_index)]
    position = group.index(section_index)
    return group[position + 1] if position + 1 < len(group) else None
