from dataclasses import dataclass
from math import pi, sin


LEFT, RIGHT = 48, 2192
STEP = 1 / 60
MOVE_SPEED = 230
MAX_RECORD_SECONDS = 10
# 본체 레벨 (BALANCE.md). 레벨 1~9에서 다음 레벨까지 필요한 경험치이며 최대 레벨은 10이다.
LEVEL_UP_XP = (30, 45, 60, 80, 100, 120, 140, 160, 180)
HAZARD_RATIO = 0.2      # 숨은 함정은 최대 체력의 20%를 깎는다.
POISON_DEPTH = 28       # 독 웅덩이 수면은 바닥선보다 이만큼 낮다. 웅덩이 앞 바닥이나 낮게 줄을 타고 지날 때는 닿지 않는다
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
    # 나룻배 발판: switch(스위치 번호)가 눌린 뒤에는 본체·분신이 올라서 있는 동안 처음 자리에서 반 바퀴(swing의 두 배)
    # 건너편으로 가고, 아무도 없으면 처음 자리로 돌아온다. 스위치가 눌리기 전에는 움직이지 않는다.
    switch: int | None = None

    def shift(self, clock: float) -> float:
        return self.swing * sin(2 * pi * (clock / self.period + self.phase)) if self.swing else 0.0


@dataclass(frozen=True)
class Switch:
    """공중 턱 위의 스위치. 분신(녹화 중인 분신 포함)이 그 높이에 올라서면 door가 열린 채로 고정된다.
    door가 없으면 출구 포탈을 여는 스위치다: 눌리기 전엔 출구가 없고, 눌리면 출구에 포탈이 생긴다."""
    floor: int
    x: int
    height: int
    door: Point | None = None


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
    lanes: tuple[tuple[int, int], ...] = ()   # 땅마다 떠다니는 x 범위 (왼쪽, 오른쪽). 비우면 맵 전체
    fixed: tuple[int, ...] = ()               # 염력으로 잡을 수 없는 땅 번호


SKY_STEP = 76   # 하늘 땅의 높은 점프(96, world.HIGH_JUMP_HEIGHT)로 오를 수 있는 한 단. 두 단은 2단 점프로만 오른다


@dataclass(frozen=True)
class Lens:
    """렌즈 건축물. 외눈 유령 분신의 레이더 원이 닿으면 그 층의 숨은 발판이 모두 드러난다."""
    floor: int
    x: int
    height: int


@dataclass(frozen=True)
class WebBeam:
    """거미 분신이 줄을 붙이는 매달린 조각상. rope면 재현 분신이 줄을 붙일 때 본체가 오를 수 있는 밧줄이 늘어진다."""
    floor: int
    left: int
    right: int
    underside: int
    height: int = 70
    rope: bool = False


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
    """거미줄 다리 낭떠러지. 거미 분신(재현)이 줄에 매달리거나 날아서 지나간 자리 아래에 거미줄이 쳐지고
    life초 뒤 끊어진다. 본체는 거미줄 위만 걸을 수 있고, 거미줄이 없는 곳은 구덩이라 떨어진다."""
    floor: int
    left: int
    right: int
    tile: int = 40        # 거미줄 한 칸의 폭
    life: float = 2.2     # 거미가 지나간 뒤 거미줄이 남아 있는 시간


@dataclass(frozen=True)
class HuntGate:
    """사냥 문. 그 층 left~right에서 나온 몬스터를 모두 처치해야 열린다."""
    door: Point
    left: int
    right: int


@dataclass(frozen=True)
class Snake:
    """사슬 뱀 (chain_snake.py). 머리가 path의 꺾인 길((x, 높이) 점들, 그 층 바닥 기준)을 따라가고 몸이 머리가 지나간 칸을
    따라온다. 가로 몸은 윗면이 길 높이다. wait면 본체가 올라탈 때까지 멈춰 있고, partner(뱀 번호)도 함께 출발한다.
    loop면 ㅁ자 길을 끝없이 돌고 사라지지 않는다. 고리가 아니면 머리가 길 끝에 닿은 뒤 꼬리까지 끝으로 빨려 들어가 사라진다."""
    floor: int
    path: tuple[tuple[int, int], ...]
    speed: float
    cells: int = 6
    loop: bool = False
    wait: bool = True
    partner: int | None = None


@dataclass(frozen=True)
class SnakeTower:
    """사슬 뱀의 탑. 층 사이 길은 뱀뿐이다. 뱀을 타고 층 높이(floor_height)까지 오르면 위층으로 넘어가고,
    떨어지면 그 층 시작 자리(starts의 x)로 돌아가며 그 층 뱀도 처음 자리로 돌아간다."""
    snakes: tuple[Snake, ...]
    starts: tuple[int, ...]


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
    width: int = 0           # 그림의 몸 폭. 본체 공격은 폭 × 키(size) 상자에 닿으면 맞는다. 0이면 점으로 본다


ENEMY_KINDS = {
    'beast': EnemyKind('monster_01_hornbeast.png', 112, 250, 43, 45, 115, xp=20, damage_ratio=0.4),
    'warden': EnemyKind('monster_02_stone_warden.png', 92, 220, 48, 60, 105, xp=28, damage_ratio=0.5),
    'watcher': EnemyKind('monster_03_watcher.png', 114, 215, 39, 12, 86, damage=8, xp=12),
    'crawler': EnemyKind('monster_spider.png', 88, 185, 38, 10, 100, damage=7, xp=10),
    # 층 유령: 정해진 높이에서 좌우로 떠다니며 닿으면 최대 체력의 35% (세 번 닿으면 쓰러진다).
    'tier_ghost': EnemyKind('monster_03_watcher.png', 60, 0, 30, 8, 70, xp=6, damage_ratio=0.35),
    'jailer_boss': EnemyKind('monster_concepts/prison-jailer-boss.png', 65, 235, 70, 95, 275, damage=8, xp=80, width=240),
    'magic_book': EnemyKind('monster_concepts/magic-book.png', 75, 175, 38, 15, 76, damage=8, xp=10),
    'potion_slime': EnemyKind('monster_concepts/potion-slime.png', 55, 160, 36, 22, 85, damage=9, xp=14),
    'magic_armor': EnemyKind('monster_concepts/magic-armor.png', 65, 180, 48, 32, 115, damage=11, xp=20),
    'magic_armor_guard': EnemyKind('monster_concepts/magic-armor.png', 112, 600, 43, 40, 115, xp=24, damage_ratio=0.4),
    'witch': EnemyKind('monster_concepts/witch.png', 60, 180, 50, 30, 112, damage=10, xp=22),
    'time_thief': EnemyKind('monster_concepts/time-thief.png', 65, 175, 42, 20, 108, damage=7, xp=16),
    'cursed_lantern': EnemyKind('monster_concepts/cursed-lantern.png', 70, 185, 42, 16, 112, damage=7, xp=14),
    'broken_jester': EnemyKind('monster_concepts/broken-jester.png', 75, 185, 40, 18, 104, damage=7, xp=15),
    'grand_witch': EnemyKind('monster_concepts/grand-witch-boss.png', 65, 220, 55, 145, 268, damage=11, xp=120, width=204),
    'echo_knight': EnemyKind('monster_concepts/echo-knight-boss.png', 70, 260, 65, 180, 240, damage=12, xp=160, width=218),
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
    bridges: tuple[EchoBridge, ...] = ()
    hunt_gates: tuple[HuntGate, ...] = ()
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
    # 결계 (왼쪽, 아래 높이, 오른쪽, 위 높이). 물약 슬라임의 물약은 여기 닿으면 깨진다. 사람과 땅은 지나간다.
    seals: tuple[tuple[int, int, int, int], ...] = ()
    tower: SnakeTower | None = None
    exit_height: int = 0   # 출구가 공중 턱 위에 있으면 그 높이
    eggs: tuple[tuple[int, int, int], ...] = ()   # 거미 알 (x, 높이, 경험치). 본체가 닿으면 경험치를 얻는다

    @property
    def chasms(self):
        """떨어지는 곳 (층, 왼쪽, 오른쪽): 구덩이와 거미줄 다리 낭떠러지."""
        return self.pits + tuple((bridge.floor, bridge.left, bridge.right) for bridge in self.bridges)


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
                   WebBeam(1, 1405, 1525, 175),
                   # 3층: 낭떠러지 위 조각상 다섯 개. 거미 분신이 줄을 쏘고 뛰기를 되풀이해 건너간다.
                   WebBeam(2, 640, 760, 215), WebBeam(2, 865, 985, 215), WebBeam(2, 1105, 1225, 215),
                   WebBeam(2, 1330, 1450, 215), WebBeam(2, 1550, 1670, 215)),
        # 2층: 독 웅덩이 3개 사이에 거미가 쉬어 가는 바닥 2개
        poison_zones=((1, 518, 885), (1, 1027, 1273), (1, 1355, 1525)),
        poison_platforms=((1, 885, 1027), (1, 1273, 1355)),
        # 3층: 거미줄 다리 낭떠러지. 거미 분신이 줄을 타고 지나간 자리에만 3초 동안 거미줄이 쳐진다.
        #   건너편 바닥(1850)에는 레버 스위치가 있다. 거미 분신을 녹화해 건너가 레버를 누르면 낭떠러지 앞 나룻배 발판
        #   (높이 30, 뛰어 올라탄다)이 켜진다. 본체로 돌아와 그 위에 서 있으면 건너편까지 실어 간다.
        bridges=(EchoBridge(2, 560, 1760, life=3.0),),
        switches=(Switch(2, 1850, 0),),
        platforms=(Platform(2, 1110, 1210, 30, False, swing=650, period=12.0, phase=0.75, switch=0),),
        enemies=(
            EnemySpawn('crawler', Point(1100, 0), (1000, 1200)),
            EnemySpawn('crawler', Point(1800, 0), (1700, 1900)),
        ),
        echo_seconds=MAX_RECORD_SECONDS,
    ),
    Stage(
        '02  거미 둥지',
        '사냥터의 거미를 모두 쓰러뜨리세요. 거미 분신이 줄을 타고 건넌 낭떠러지에는 잠깐 거미줄 다리가 생기고, '
        '줄을 붙인 탑의 조각상에는 밧줄이 늘어집니다(↑로 오르기).',
        1, Point(112, 0), Point(1110, 0),
        floor_height=800, exit_height=655,
        # 높이 800의 둥지 한 칸. 모든 길은 거미 분신의 능력으로만 연다 (줄타기 · 거미줄 다리 · 문 타고 넘기 · 밧줄).
        # [사냥터] 거미 둘을 모두 쓰러뜨려야 사냥 문이 열린다 (데드셀·할로우 나이트의 잠기는 전투방).
        # [거미줄 협곡] 600px 낭떠러지. 거미 분신이 조각상 셋을 타고 건너면 그 아래 거미줄 다리가 2.5초 남는다.
        #   거미는 건너편 A 문을 타고 넘어 A 발판을 밟고 버티고, 본체는 거미줄을 따라 건너 열린 A 문을 지난다
        #   (트라인처럼 한쪽이 길을 열고 다른 쪽이 지나간다).
        # [밧줄 탑] 오른쪽 아래에서 왼쪽 위로. 거미 분신이 조각상 셋을 줄을 감아 오르며 잡으면, 재현 때 조각상마다
        #   밧줄이 6초 늘어진다 (스펠렁키의 밧줄). 본체는 밧줄로 턱 셋(185·420·655)을 올라 꼭대기 출구로 간다.
        #   가운데 턱 왼쪽 작은 턱에는 거미 알(경험치)이 있다.
        hunt_gates=(HuntGate(Point(600, 0), 150, 560),),
        bridges=(EchoBridge(0, 700, 1300, life=2.5),),
        web_beams=(WebBeam(0, 780, 900, 215), WebBeam(0, 1000, 1120, 225), WebBeam(0, 1220, 1340, 215),
                   WebBeam(0, 1880, 2000, 215, rope=True), WebBeam(0, 1580, 1700, 450, rope=True),
                   WebBeam(0, 1280, 1400, 685, rope=True)),
        gates=(Gate('A', Point(1550, 0), Point(1450, 0)),),
        platforms=(Platform(0, 1560, 1870, 185, False), Platform(0, 1260, 1600, 420, False),
                   Platform(0, 1050, 1285, 655, False), Platform(0, 1080, 1180, 440, False)),
        eggs=((1120, 440, 60),),
        enemies=(
            EnemySpawn('crawler', Point(300, 0), (220, 400)),
            EnemySpawn('crawler', Point(460, 0), (380, 540)),
            EnemySpawn('crawler', Point(1900, 0), (1780, 2050)),
        ),
        echo_seconds=12,
    ),
    Stage(
        '03  간수의 방',
        '쇠사슬 간수를 처치하세요. 쇠사슬은 뒤로 물러나고, 낙석은 그림자를 피하고, 돌진은 점프로 넘으세요.',
        # 층 없는 한 화면 보스방. (예전 5층 탑의 1~4층 퍼즐은 뺐다)
        1, Point(112, 0), Point(2100, 0),
        floor_height=800,
        # 공중 돌 발판(그림 assets/PixelLab/스테이지/boss_platform.png, 윗면 폭 196): 스케치대로 왼쪽 2단, 가운데, 오른쪽 2단.
        # 대시·2단 점프를 얻는 방이라 발판을 높였다: 양옆은 낮은 단 120·높은 단 240이라 점프(96)로는 못 오르고
        # 2단 점프(약 180)로 한 단씩 오른다. 가운데(220)는 2단 점프로는 못 닿고 점프 + 위 대시(↑↑)로 오른다.
        # 발판 위(높이 30 이상)에서는 돌진을 피한다.
        platforms=(Platform(0, 230, 426, 120, False), Platform(0, 395, 591, 240, False),
                   Platform(0, 871, 1067, 220, False),
                   Platform(0, 1330, 1526, 120, False), Platform(0, 1500, 1696, 240, False)),
        enemies=(EnemySpawn('jailer_boss', Point(1120, 0), (1050, 1190)),),
        echo_seconds=MAX_RECORD_SECONDS,
    ),
    Stage(
        '04  염력의 하늘 땅',
        '떠다니는 하늘 땅을 갈아타며 세 포털에 오르세요. 포털 너머 몬스터를 모두 처치하면 열쇠를 얻고, '
        '열쇠 3개를 모으면 출구가 열립니다. 마법책 분신을 녹화하는 동안 마우스로 아무 땅이나 잡으면 날아오고, 놓은 땅은 잠시 멈춥니다.',
        # [1·2·3층 통합방] 출구는 가운데 바닥에 있고 열쇠 3개를 모아야 열린다.
        # 포털(sky.switches)은 벽에 붙은 작은 턱 위에 있다: 1번 왼쪽 아래(3단), 2번 왼쪽 위(7단), 3번 오른쪽 중간(5단).
        # 포털을 밟으면 그 번호의 몬스터 방(SKY_ROOMS)으로 간다. 순서는 상관없다.
        # 턱까지 가는 길은 없다. 하늘 섬 6개가 1~6단에 하나씩 있고 저마다 좌우로 아무렇게나 떠다닌다.
        # 섬이 적어 기다리지 않도록 마법책 분신의 염력은 맵 어디의 섬이든 잡아 분신 곁으로 끌어온다.
        # 바로 윗단 섬이 가까이 올 때 뛰어 한 단씩 오른다. 마법책 분신으로 섬을 끌어다 놓으면
        # 그 자리에 몇 초(world.SKY_PIN) 멈췄다가 다시 떠다닌다. 화면은 바닥 위 1000까지 보인다.
        1, Point(1000, 0), Point(1240, 0),
        floor_height=800,
        platforms=(Platform(0, 55, 175, SKY_STEP * 3, False), Platform(0, 55, 175, SKY_STEP * 7, False),
                   Platform(0, 2060, 2185, SKY_STEP * 5, False)),
        sky=SkyPuzzle(blocks=tuple((200 + 677 * i % 1840, SKY_STEP * (i + 1)) for i in range(6)),
                      switches=((110, SKY_STEP * 3), (110, SKY_STEP * 7), (2130, SKY_STEP * 5))),
        enemies=(
            EnemySpawn('magic_book', Point(700, 0), (620, 780)),
            EnemySpawn('potion_slime', Point(450, 0), (390, 510)),
            EnemySpawn('magic_armor', Point(1600, 0), (1540, 1660)),
        ),
        echo_seconds=30,   # 땅을 반대쪽 벽까지 날라 디딤돌을 오르려면 시간이 더 든다
    ),
    Stage(
        '06  아래층의 열쇠',
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
        '07  대마녀의 방',
        '대마녀를 처치하세요. 중력장은 반대 방향키로 버티고, 낙뢰는 바닥 문양을 피하고, 마력 구체는 점프로 넘으세요.',
        # 층 없는 한 화면 보스방. (예전 5층 탑의 1~4층과 균형 승강기는 뺐다)
        1, Point(111, 0), Point(2100, 0),
        floor_height=800,
        # 날개 달린 하늘 섬 7개(그림 assets/PixelLab/스테이지/witch_island.png, 윗면 폭 150)가 저마다 범위 안에서 떠다닌다.
        # 높이 120·240·360 세 단이라 2단 점프(약 180)나 위 대시로 한 단씩 갈아타며 대마녀의 공격을 피한다.
        # 윗단·아랫단 범위가 겹친다.
        sky=SkyPuzzle(blocks=((425, 120), (1100, 120), (1775, 120), (600, 240), (1600, 240), (900, 360), (1350, 360)),
                      switches=(), width=150,
                      lanes=((250, 600), (850, 1350), (1600, 1950), (400, 800), (1400, 1800), (700, 1100), (1150, 1550))),
        enemies=(EnemySpawn('grand_witch', Point(1120, 0), (1050, 1190)),),
        echo_seconds=MAX_RECORD_SECONDS,
    ),
    Stage(
        '08  두 번째 잔향',
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
        '09  되돌아가는 발자국',
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
        '10  마지막 잔향',
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
    Stage(
        '05  마녀의 실험 금고',
        '물약 슬라임 분신은 F를 눌렀다 떼어 물약을 던집니다. 떨어진 자리에 포털이 생기고, 땅 위에 생긴 포털은 땅을 따라 움직입니다. '
        '금고는 결계 때문에 물약이 못 들어가니, 포털이 붙은 땅을 마법책 분신의 염력으로 밀어 넣으세요.',
        # [창살 방] 시작 쪽에서 물약 슬라임과 마법책을 처치해 분신을 얻는다. 창살 벽(640)은 본체가 못 넘고
        # 물약은 넘는다: 슬라임 분신이 발밑과 창살 너머에 포털 한 쌍을 만든다.
        # [독 수조] 820~1300은 바닥이 없다. 떠다니는 땅 A(염력이 안 통함)에 물약을 맞혀 포털을 붙이고
        # 본체가 땅 A로 건너가 실려 간 뒤 건너편에 내린다. 물약은 최대 약 320px 날아가 건너편 바닥엔 못 닿는다.
        # [봉인 금고] 금고(1780~2120, 바닥 높이 260)는 결계라 물약이 깨진다. 땅 B에 포털을 붙인 뒤
        # 마법책 분신이 땅 B를 금고 안으로 끌어 놓으면(15초 멈춤) 본체가 포털로 들어가 스위치를 밟는다.
        # 스위치를 밟으면 출구 포탈이 열린다.
        1, Point(110, 0), Point(2155, 0),
        floor_height=800,
        walls=(Point(640, 0),),
        pits=((0, 820, 1300),),
        poison_zones=((0, 820, 1300),),
        platforms=(Platform(0, 1780, 2120, 260, False),),
        switches=(Switch(0, 2050, 260),),
        seals=((1780, 250, 2120, 520),),
        sky=SkyPuzzle(blocks=((1050, 160), (1560, 200)), switches=(),
                      lanes=((950, 1240), (1450, 1700)), fixed=(0,)),
        enemies=(
            EnemySpawn('potion_slime', Point(300, 0), (240, 380)),
            EnemySpawn('magic_book', Point(500, 0), (450, 570)),
        ),
        echo_seconds=20,
    ),
    Stage(
        '04-1  사슬 뱀의 탑',
        '사슬 뱀에 올라타면 움직입니다. 몸은 꼬리부터 사라지니 머리 쪽으로 계속 걸으세요. '
        '2층의 뱀은 막다른 길로 가니 위를 지나는 뱀으로 갈아타고, 3층에서는 도는 뱀 맨 위에서 출구로 뛰어내리세요.',
        # 세로로 3층인 탑. 층 사이에 계단·승강기·포털이 없고 뱀을 타야만 위층으로 간다 (분신·포털·염력 없음).
        # 층마다 바닥은 시작 자리와 도착 자리에만 있고 사이는 낭떠러지다. 떨어지면 그 층 시작 자리로 돌아간다.
        # [1층] 느린 뱀이 ㄱ자로 간다: 오른쪽으로 가다가 위로 꺾여 2층 오른쪽 바닥까지 올라간다. 따라 걷기만 하면 된다.
        # [2층] 뱀 B는 왼쪽으로 가다 한 번 솟았다 내려가 막다른 곳(350)에서 끝난다. B를 타면 뱀 C도 함께 출발해
        #       B가 솟은 윗길(높이 200, 950~600) 바로 위(높이 240)를 B 머리보다 95 앞서 지나간다.
        #       그때 점프해 C로 갈아타면 3층 왼쪽 바닥까지 데려간다.
        # [3층] ㅁ자로 계속 도는 빠른 뱀. 시작 바닥 끝에 서 있으면 아랫길이 지나갈 때 왼쪽 세로 몸이 태워 올라간다.
        #       맨 윗길(330)이 오른쪽 끝에 왔을 때 출구 바닥으로 뛰어내린다. 너무 일찍 뛰면 못 닿고, 늦으면 발밑이 사라진다.
        # 꼬리로 올라탄 뒤 머리를 따라잡는 데 (칸 수 × 66) / (걷기 230 - 뱀 속도)초가 걸리니, 위로 꺾이기 전 직선은
        # 그동안 머리가 가는 거리보다 길게 둔다 (머리 끝에 서 있어야 세로 몸을 타고 올라간다).
        3, Point(150, 0), Point(2100, 2),
        floor_height=800,
        pits=((0, 330, 2200), (1, 40, 1850), (2, 380, 1650)),
        tower=SnakeTower(
            snakes=(
                Snake(0, ((340, 0), (2010, 0), (2010, 800)), speed=110),
                Snake(1, ((1845, 0), (950, 0), (950, 200), (600, 200), (600, 0), (350, 0)), speed=120, partner=2),
                Snake(1, ((1950, 240), (250, 240), (250, 800)), speed=120),
                Snake(2, ((390, 0), (390, 330), (1500, 330), (1500, 0)), speed=200, cells=8, loop=True, wait=False),
            ),
            starts=(150, 2060, 150),
        ),
        echo_seconds=MAX_RECORD_SECONDS,
    ),
    # 하늘 땅(3) 포털 너머의 몬스터 방 셋 (SKY_ROOMS). 그림은 1·2층 통합 회랑 한 장(층별맵/3스테이지_포털방_통합배경.png).
    # 몬스터를 모두 처치하면 열쇠를 얻고 가운데에 돌아가는 포털이 열린다.
    # 돌 발판은 120씩 오르는 피라미드라 2단 점프(약 180)로 한 단씩 올라 꼭대기(2층 다리, 480)까지 간다. 화면은 오른 만큼 따라 올라간다.
    *(Stage(
        f'03-{number}  포털 너머의 회랑',
        '몬스터를 모두 처치하면 열쇠를 얻고, 가운데에 돌아가는 포털이 열립니다.',
        1, Point(150, 0), Point(1120, 0),
        floor_height=800,
        platforms=(Platform(0, 230, 426, 120, False), Platform(0, 460, 656, 240, False),
                   Platform(0, 690, 886, 360, False), Platform(0, 920, 1120, 480, False),
                   Platform(0, 1120, 1320, 480, False), Platform(0, 1354, 1550, 360, False),
                   Platform(0, 1584, 1780, 240, False), Platform(0, 1814, 2010, 120, False)),
        enemies=tuple(EnemySpawn(kind, Point(x, 0), (x - 80, x + 80)) for kind, x in spawns),
        echo_seconds=MAX_RECORD_SECONDS,
    ) for number, spawns in (
        (1, (('magic_book', 600), ('potion_slime', 950), ('magic_book', 1400), ('potion_slime', 1850))),
        (2, (('potion_slime', 550), ('magic_book', 900), ('magic_armor', 1300), ('potion_slime', 1650),
             ('magic_book', 2000))),
        (3, (('magic_armor', 600), ('magic_book', 900), ('potion_slime', 1250), ('magic_book', 1600),
             ('magic_armor', 1950))),
    )),
)
SKY_ROOMS = {11: 0, 12: 1, 13: 2}   # 포털 너머 방 번호 → 하늘 땅 포털 번호

# One visible stage may contain multiple connected map sections.
# 4스테이지는 대마녀의 방(5) 하나다. 사슬 뱀의 탑(10)·마녀의 실험 금고(9)·아래층의 열쇠(4)는 4스테이지에서 뺐다
# (구간 데이터는 남아 있지만 게임에서는 들어가지 않는다).
STAGE_GROUPS = ((0,), (1, 2), (3,), (5,), (6,), (7, 8))
STAGE_TITLES = (
    '01  잔향의 문', '02  사냥꾼과 간수', '03  염력의 하늘 땅',
    '04  대마녀의 방', '05  두 번째 잔향', '06  마지막 잔향',
)


def stage_group_index(section_index):
    section_index = 3 if section_index in SKY_ROOMS else section_index   # 포털 너머 방은 하늘 땅 스테이지에 속한다
    return next(i for i, group in enumerate(STAGE_GROUPS) if section_index in group)


def next_section_in_stage(section_index):
    group = STAGE_GROUPS[stage_group_index(section_index)]
    position = group.index(section_index)
    return group[position + 1] if position + 1 < len(group) else None
