from dataclasses import dataclass, field, replace
from math import asin, atan2, cos, hypot, pi, sin, sqrt
import random

import boss_skills
import chain_snake
from stages import HAZARD_RATIO, LEVEL_UP_XP, POISON_DEPTH, attack_power, max_health

WATCH_RANGE = 170   # 분신이 감시등의 focus에서 이만큼 안에 있으면 빛이 분신을 따라간다.
TAUNT_OFFSET = 35   # 수호자 앞 도발 발판까지의 거리
LIGHT_BELOW = 100   # 위층 분신의 빛이 아래층을 비추는 반폭
from stages import (
    ACTOR_RADIUS, BOSS_KINDS, DOOR_GRACE, ENEMY_KINDS,
    GATE_HALF_WIDTH, LEFT, MOVE_SPEED,
    PLATE_RANGE, RIGHT, SKY_ROOMS, STAIR_RANGE, STAGES, STEP, WEAPONS, EnemySpawn, Point,
)

JUMP_DURATION = 0.64
JUMP_HEIGHT = 48  # 49를 넘으면 슈퍼 점프(100)가 보통 점프의 두 배가 안 된다
# 보스방(간수·대마녀)과 하늘 땅(+ 포털 너머 방)은 두 배로 높이 뛴다. 체공 시간은 높이의 제곱근만큼 늘린다.
# 이 방들의 발판·섬 높이도 이에 맞춰 올렸다 (보스방·포털 방은 1.5배, 하늘 땅 한 단은 두 배). 1·2스테이지 퍼즐은 보통 점프(48)에 맞춰져 있어 그대로 둔다.
HIGH_JUMP_SECTIONS, HIGH_JUMP_HEIGHT = (2, 3, 5, 11, 12, 13), 96
BEAST_JUMP_DURATION = 1.0
BEAST_JUMP_HEIGHT = 100
BEAST_CHARGE_SECONDS = 1.0
# 하늘 섬: 좌우로 아무 곳이나 정해 떠다니고, 마법책 분신이 놓은 섬은 SKY_PIN초 멈췄다가 다시 떠다닌다.
SKY_SPEED = (60.0, 110.0)  # px/s
SKY_WALL_BIAS = 300        # 목표를 맵 밖까지 뽑고 벽에서 자른다: 벽 턱 옆에 섬이 더 자주 머문다
SKY_PIN = 15.0
SKY_FLY = 1200.0   # px/s. 염력으로 잡은 땅이 마우스 쪽으로 날아오는 빠르기 (멀리서 잡아도 금방 온다)
ELEVATOR_DURATION = 0.8
ENEMY_CHASE_MARGIN = 400
ECHO_DAMAGE_RATIO = 0.30
ECHO_INVULNERABILITY = 0.92
# 거미줄 그네 (거미 분신 전용). F로 붙이고 ←→로 반동, ↑↓로 줄을 감고 풀고,
# Space로 흔들리던 속도 그대로 날아가며 놓거나 D로 그 자리에서 놓는다. 매달린 채 F를 다시 쏘면 새 지점에 옮겨 붙는다.
SPIDER_WEB_TOP = 150       # 거미줄을 붙이는 천장 높이 (바닥 위)
SPIDER_GRAVITY = 1400      # px/s²
SPIDER_PUMP = 3.2          # ←→로 주는 반동 (rad/s²)
SPIDER_DAMPING = 0.15      # 초당 흔들림이 줄어드는 비율
SPIDER_REEL = 170          # ↑↓로 줄을 감고 푸는 속도 (px/s)
SPIDER_WEB_MIN, SPIDER_WEB_MAX = 22, 190
# 거미줄이 닿는 거리. 1스테이지 조각상(아랫면 215)에 바로 아래에서는 위로 181,
# 대각선으로는 256이 필요해 대각선 발사까지 닿도록 260으로 잡는다.
SPIDER_AIM_REACH = 260
SPIDER_MAX_ANGLE = 1.35    # 줄이 수직에서 벌어질 수 있는 최대 각 (rad)
SPIDER_OVER_HEIGHT = 125   # 이 높이 이상이면 문과 벽 위로 넘어간다
SPIDER_DOOR_CLIMB_DURATION = 1.2
SPIDER_DOOR_CLIMB_HEIGHT = 145
# 거미 밧줄: 재현 중인 거미 분신이 rope 조각상에 줄을 붙이면 그 자리에서 바로 아래 바닥(발판)까지 줄이 늘어져
# ROPE_LIFE초 남는다. 본체는 줄 옆에서 ↑로 붙잡아(뛰는 중에도) ↑↓로 오르내리고 Space로 뛰어내린다. 줄이 끊어지면 떨어진다.
ROPE_LIFE = 6.0
ROPE_CLIMB = 150           # px/s
ROPE_GRAB = 18             # 줄에서 이만큼 안이면 붙잡는다
ROPE_TOP = 60              # 조각상 아랫면에서 이만큼 아래까지 오른다
EGG_REACH = 26             # 거미 알을 줍는 거리
FALL_GRAVITY = 820         # 예전 보통 점프(높이 42, 0.64초)에 맞춘 낙하 중력
PIT_DEPTH = 90             # 구덩이로 이만큼 떨어지면 죽는다
RADAR_RANGE = 220          # 외눈 유령 분신의 눈에서 발판이 드러나는 거리
RADAR_EYE = 55             # 발밑에서 눈까지의 높이
# 물약 슬라임 분신: F를 누르고 있으면 힘이 모이고, 떼면 바라보는 쪽 위로 물약을 던진다.
# 75°로 던져 가장 세게 던지면 높이 약 300, 거리 약 320까지 간다.
POTION_ANGLE = 1.31
POTION_SPEED = (300.0, 760.0)
POTION_GRAVITY = 900
POTION_CHARGE = 1.0        # 이만큼 모으면 가장 세게 던진다 (초)
POTION_HAND = 40           # 발밑에서 손까지
PORTAL_RANGE = 16          # 포털 가운데에서 이만큼 안에 서면 들어간다
LEVEL_UP_SECONDS = 3.2     # 레벨이 오르면 본체 둘레에 레벨 업 이펙트(pixelfx ui/level-up)가 이만큼 보인다
# 대시(같은 방향키 두 번 연타)와 2단 점프(공중에서 Space): 2스테이지 간수의 방부터 쓴다.
# 1스테이지·2스테이지 점프맵에서는 못 쓴다. 공중에서는 1단 점프 중 한 번, 2단 점프 뒤 한 번 대시할 수 있다.
# 대시는 ←→ 옆, ↑ 위, ↑와 ←→를 함께 누르면 대각선 위로 간다. 위로 가는 대시는 공중 대시 한 번으로 친다.
NO_MOVES_SECTIONS = (0, 1)
DASH_SPEED = 900           # px/s. 한 번에 약 145px
DASH_TIME = 0.16           # 대시하는 동안은 맞지 않는다
DASH_COOLDOWN = 0.55
# 대마녀 2페이즈: 체력이 절반 이하가 되면 빗자루에 올라타(그동안 무적) 공중을 날며 마법을 쓴다.
BROOM_MOUNT = 1.0          # 타는 연출 시간 (grand_witch_broom 시트 0줄 8칸)
BROOM_HEIGHT = 110         # 나는 높이. 하늘 섬(90·135)이나 2단 점프로 올라가야 벨 수 있다
BROOM_DIVE, BROOM_RISE = 420, 180   # 기본 공격 때 본체 쪽으로 급강하하는 속도, 다시 떠오르는 속도 (px/s)
# 보스를 처치하면 출구에 포털이 열린다. PULL_RANGE 안에 들어오면 빨려 들어가고(가까울수록 빠르다),
# 가운데에 닿으면 ABSORB_SECONDS 동안 빨려 들어간 뒤 클리어.
PULL_RANGE = 260
PULL_SPEED = (50.0, 340.0)  # 가장자리, 가운데 바로 앞의 당기는 속도 (px/s). 걸음은 230
ABSORB_SECONDS = 0.8
SKILL_UNLOCK_SECONDS = 2.4  # 처음 쓸 수 있게 된 구역에서 능력 획득 알림판(pixelfx ui/achievement)이 보이는 시간


def potion_launch(actor) -> list:
    """물약 슬라임 분신이 지금 던지면 날아갈 물약 [x, 층, 높이, vx, vh]. 화면의 예상 궤적도 쓴다."""
    speed = POTION_SPEED[0] + (POTION_SPEED[1] - POTION_SPEED[0]) * min(1.0, actor.potion_charge / POTION_CHARGE)
    return [actor.x, actor.floor, actor.jump_height + POTION_HAND,
            actor.facing * speed * cos(POTION_ANGLE), speed * sin(POTION_ANGLE)]


@dataclass
class Actor:
    x: float
    floor: int
    facing: int = 1
    moving: bool = False
    walk_distance: float = 0
    jump_time: float = 0.0
    jump_duration: float = JUMP_DURATION
    jump_peak: float = JUMP_HEIGHT
    beast_charge: float = 0.0
    beast_charge_active: bool = False
    beast_super_jump: bool = False
    elevator_target: int | None = None
    elevator_time: float = 0.0
    web_time: float = 0.0         # 거미줄에 매달리거나 놓고 날아가는 동안 0보다 크다
    web_anchor_x: float = 0.0
    web_anchor_height: float = SPIDER_WEB_TOP
    web_anchor_beam: bool = False
    web_length: float = 0.0
    web_angle: float = 0.0        # 수직에서 벌어진 각. 양수면 붙인 점보다 오른쪽
    web_speed: float = 0.0        # 각속도 (rad/s)
    web_flying: bool = False      # 줄을 놓고 날아가는 중
    web_vx: float = 0.0
    web_vy: float = 0.0
    web_height: float = 0.0
    web_aiming: bool = False
    web_aim_x: int = 1
    door_climb_time: float = 0.0
    door_climb_x: float = 0.0
    door_climb_start: float = 0.0
    door_climb_end: float = 0.0
    spider_up_latched: bool = False
    base: float = 0.0             # 서 있는 발판의 높이. 구덩이로 떨어지면 음수가 된다.
    fall_speed: float = 0.0
    radar: bool = False           # 외눈 유령 분신의 레이더 (F)
    potion_charge: float = 0.0    # 물약 슬라임 분신이 F로 모은 시간
    dash_time: float = 0.0        # 남은 대시 시간
    dash_cooldown: float = 0.0
    dash_age: float = 9.0         # 대시를 시작한 뒤 흐른 시간 (화면의 잔상용)
    dash_from: float = 0.0        # 대시를 시작한 x와 끝난 x (잔상이 이 사이에 남는다)
    dash_to: float = 0.0
    dash_from_h: float = 0.0      # 대시를 시작한 높이와 끝난 높이
    dash_to_h: float = 0.0
    dash_vx: float = 0.0          # 대시 방향 (대각선이면 0.71씩)
    dash_vy: float = 0.0
    air_jumped: bool = False      # 공중에서 2단 점프를 이미 썼다
    air_dashed: bool = False      # 공중에서 대시를 이미 썼다
    rope: list | None = None      # 붙잡고 있는 거미 밧줄 (World.ropes의 한 줄)

    @property
    def elevator_offset(self):
        if self.elevator_target is None:
            return 0.0
        return (self.elevator_target - self.floor) * min(1.0, self.elevator_time / ELEVATOR_DURATION)

    @property
    def jump_height(self):
        if self.door_climb_time > 0:
            return SPIDER_DOOR_CLIMB_HEIGHT * sin(pi * min(1.0, self.door_climb_time / SPIDER_DOOR_CLIMB_DURATION))
        if self.web_time > 0:
            return self.web_height
        if self.jump_time <= 0:
            return self.base
        progress = min(1.0, self.jump_time / self.jump_duration)
        return self.base + 4 * self.jump_peak * progress * (1 - progress)

    @classmethod
    def at(cls, point: Point, facing: int = 1):
        return cls(point.x, point.floor, facing)


@dataclass(frozen=True)
class Motion:
    horizontal: int = 0
    stairs: int = 0
    jump: bool = False
    web: bool = False
    jump_held: bool = False
    web_aiming: bool = False
    aim_x: int | None = None   # 녹화된 발사 방향 (-1, 0, 1). 재현은 조준 없이 이 방향으로 쏜다.
    release: bool = False      # D: 거미줄을 그 자리에서 놓는다
    dash: bool = False         # 같은 방향키 두 번 연타: 대시. 방향은 누르고 있는 ←→와
    dash_up: bool = False      # ↑ (↑만이면 곧장 위, ←→와 함께면 대각선 위)


@dataclass
class Recording:
    start: Point
    facing: int
    preview: Actor
    inputs: list[Motion] = field(default_factory=list)
    monster_kind: str | None = None
    clock: float = 0.0         # 녹화를 시작할 때의 움직이는 발판 시계
    base: float = 0.0          # 녹화를 시작한 높이 (하늘 섬 위에서 시작하면 0보다 크다)


@dataclass
class Echo:
    actor: Actor
    inputs: tuple[Motion, ...]
    cursor: int = 0
    monster_kind: str | None = None
    clock: float = 0.0


@dataclass
class DoorState:
    pressed: bool = False
    open: bool = False
    grace: float = 0
    latched: bool = False


@dataclass
class Enemy:
    spawn: EnemySpawn
    actor: Actor
    health: int | None
    max_health: int | None = None
    patrol_direction: int = -1
    target: Actor | None = None
    last_seen: float = 0
    unseen: float = 0
    windup: float = 0
    recovery: float = 0
    flash: float = 0
    skill: str = ''            # 보스가 쓰는 중인 스킬 이름 (boss_skills.py)
    skill_time: float = 0
    skill_cooldown: float = 0
    skill_index: int = 0
    boss_engaged: bool = False  # 보스가 본체를 한 번 발견했는지
    boss_appeared: bool = False  # 등장 음악을 이미 틀었는지
    broom: float | None = None  # 대마녀가 빗자루에 오른 뒤 지난 시간 (None = 아직 걸어 다님)
    laser_h: float = 0.0        # 마력 광선이 지나가는 높이
    teleport_to: float = 0.0    # 빗자루 대마녀가 순간이동할 x (본체 너머)
    mark_x: float = 0.0         # 잔향 기사의 그림자 손이 솟을 자리
    phase: int = 1              # 잔향 기사의 단계 (boss_skills.update_phase)
    phase_time: float = 0.0     # 단계가 오르는 연출이 남은 시간. 그동안 무적


def approach_direction(start: float, end: float) -> int:
    return (end > start) - (end < start)


class World:
    god = False   # O 키 무적(시험 플레이용). 클래스에 두어 스테이지를 다시 만들어도 이어진다

    def __init__(self, index: int = 0, weapon_index: int = 2, xp: int = 0,
                 monster_echo: str | None = None, monster_echoes=None):
        self.xp = xp  # 스테이지를 넘어가도 이어지는 누적 경험치
        self.index = index
        self.stage = STAGES[index]
        self.player = Actor.at(self.stage.start)
        self.echo: Echo | None = None
        self.recording: Recording | None = None
        self.monster_echoes = list(monster_echoes) if monster_echoes is not None else ([monster_echo] if monster_echo else [])
        self.pending_monster_echoes = []
        self.echo_selecting = False
        self.doors = [DoorState() for gate in self.stage.gates]
        self.enemies = []
        for spawn in self.stage.enemies:
            health = ENEMY_KINDS[spawn.kind].health
            health = None if health is None else round(health * self.stage.enemy_scale)
            self.enemies.append(Enemy(spawn, Actor.at(spawn.point, -1), health, health))
            self.enemies[-1].actor.base = spawn.height
        self.revealed = set()   # 레이더로 드러난 숨은 발판 번호
        self.lens_lit = False   # 렌즈가 켜져 그 층 발판이 모두 드러났는가
        self.switched = [False] * len(self.stage.switches)   # 눌려 문이 열린 스위치
        self.ferry_clock = [0.0] * len(self.stage.platforms)   # 나룻배 발판이 처음 자리에서 간 시간 (Platform.switch)
        sky = self.stage.sky
        self.sky_blocks = [list(block) for block in sky.blocks] if sky else []   # 하늘 땅 [x, 높이]
        tower = self.stage.tower   # 사슬 뱀마다 [머리 자리(길을 따라 잰 거리), 움직이는 중인가]
        self.snake_state = [[chain_snake.start_head(snake), not snake.wait] for snake in tower.snakes] if tower else []
        self.sky_keys = set()      # 포털 너머 방을 깨고 얻은 열쇠 (포털 번호)
        self.sky_on = None         # 본체가 지금 밟고 있는 하늘 포털 (한 번 밟을 때 한 번만 판정)
        self.room_request = None   # 밟은 하늘 포털이 보내는 몬스터 방 번호 (main이 방으로 바꾼다)
        self.parent = None         # 포털 너머 방이면 돌아갈 하늘 땅 World
        self.sky_hold = None       # 마법책 분신이 염력으로 잡은 땅 번호
        self.sky_target = (0.0, 0.0)
        self.sky_rng = random.Random(index)   # 스테이지마다 같은 순서로 떠다니게 (테스트가 재현되도록)
        self.sky_goal = [self._sky_goal(index) for index in range(len(self.sky_blocks))]   # 땅마다 [목표 x, 속도]
        self.sky_pin = [0.0] * len(self.sky_blocks)                   # 놓인 뒤 멈춰 있을 남은 시간
        self.reveal_time = 0.0  # 외눈 유령 분신이 사라진 뒤 남은 공개 시간
        self.potions = []            # 날아가는 물약 [x, 층, 높이, vx, vh]
        self.portals = [None, None]  # 파랑·주황 포털 (층, 땅 번호 또는 None, x, 높이). 땅 위면 x는 땅 가운데에서의 거리
        self.portal_next = 0         # 다음 물약이 만들 포털 (번갈아 옮겨 간다)
        self.portal_lock = True      # 포털에서 나온 뒤 한 번 비켜서야 다시 들어간다
        self.health = self.max_health
        self.damage_texts = []  # 맞은 자리에 뜨는 피해 숫자 [x, 층, 지난 시간, 글자, 본체가 맞았는가]
        self.weapon_index = weapon_index
        self.invulnerable = 0.0
        self.echo_invulnerable = 0.0
        self.attack_cooldown = 0.0
        self.attack_flash = 0.0
        self.attack_kind = 'slash'
        self.attack_duration = 0.28
        self.attack_hit_pending = False
        self.attack_age = 9.0   # 마지막 공격을 시작한 뒤 흐른 시간. 화면의 검기 이펙트가 쓴다.
        self.hit_sparks = []    # 공격이 적에게 맞은 자리 [x, 층, 지난 시간]
        self.boss_effects = []  # 보스 스킬 이펙트 (boss_skills.Effect)
        self.gravity_field = None
        self.shake = 0.0        # 화면을 흔드는 남은 시간
        self.sounds = []        # 이번 프레임에 낼 효과음 이름 (sound.py가 틀고 비운다)
        self.confused = 0.0     # 낙석에 맞아 기절한 남은 시간. 머리 위에 혼란(pixelfx status/confused)이 돈다
        self.level_up_time = 0.0  # 레벨 업 이펙트가 남은 시간
        self.flash_color, self.flash_time = (255, 255, 255), 0.0   # 보스 스킬이 터질 때 화면이 번쩍이는 색과 남은 시간
        self.portal_opened_at = None  # 보스를 처치해 출구 포털이 열린 시각
        self.absorb_time = 0.0        # 포털에 빨려 들어가는 중이면 0보다 크다
        self.moves = index not in NO_MOVES_SECTIONS   # 대시·2단 점프를 쓸 수 있는가
        self.jump_peak = HIGH_JUMP_HEIGHT if index in HIGH_JUMP_SECTIONS else JUMP_HEIGHT   # 본체·분신의 점프 높이
        self.jump_duration = JUMP_DURATION * sqrt(self.jump_peak / JUMP_HEIGHT)
        self.skill_unlock_time = SKILL_UNLOCK_SECONDS if index == 2 else 0.0
        self.time = 0.0
        self.result = 'playing'
        self.message = ''
        self.message_time = 0.0
        self.sequence_progress = 0
        self.sequence_unlocked = False
        self.sync_unlocked = False
        self.sync_pressed = (False, False)   # (본체 발판, 분신 발판)
        self.guard_open_time = 0.0
        self.watch_active = False
        self.isolation_closed = False
        self.isolation_changed_at = -9.0     # 격리실 철창이 마지막으로 움직인 시각 (떨어지는 연출용)
        self.bridge_tiles = [[0.0] * -(-(bridge.right - bridge.left) // bridge.tile) for bridge in self.stage.bridges]
        self.ropes = []   # [층, x, 아래 높이, 위 높이, 남은 시간, 조각상 번호]
        self.eggs = list(self.stage.eggs)   # 아직 줍지 않은 거미 알
        self._update_doors(0)
        if self.skill_unlock_time:
            self.notify('새 능력! ←→ 두 번 연타로 대시, 공중에서 Space로 2단 점프')
            self.message_time = SKILL_UNLOCK_SECONDS + 1.5

    @property
    def level(self) -> int:
        level, needed = 1, 0
        for step in LEVEL_UP_XP:
            needed += step
            if self.xp < needed:
                break
            level += 1
        return level

    @property
    def max_health(self) -> int:
        return max_health(self.level)

    def xp_progress(self) -> tuple[int, int]:
        """(이번 레벨에서 모은 경험치, 다음 레벨까지 필요한 양). 최대 레벨이면 필요한 양이 0이다."""
        level = self.level
        spent = sum(LEVEL_UP_XP[:level - 1])
        needed = LEVEL_UP_XP[level - 1] if level <= len(LEVEL_UP_XP) else 0
        return self.xp - spent, needed

    def notify(self, message: str):
        self.message = message
        self.message_time = 2.2

    def select_weapon(self, index: int):
        if self.recording is None and self.attack_flash == 0:
            self.weapon_index = index

    def toggle_lever(self):
        if self.result != 'playing' or self.recording is not None:
            return
        room = self.stage.isolation
        if room and self._near(self.player, room.lever, 28):
            if self.isolation_closed:
                self.isolation_closed = False
                self.isolation_changed_at = self.time
                self.notify('격리실 문을 열었습니다.')
            elif (not any(enemy.spawn.kind == 'magic_armor_guard' for enemy in self.enemies)
                  or any(enemy.spawn.kind == 'magic_armor_guard' and enemy.actor.floor == room.door.floor and enemy.actor.x >= room.inside_x for enemy in self.enemies)):
                self.isolation_closed = True
                self.isolation_changed_at = self.time
                self.notify('몬스터를 가뒀습니다. 위층 보안문이 열립니다.')
            else:
                self.notify('몬스터를 격리실 안으로 유인하세요.')
            return
        for gate, state in zip(self.stage.gates, self.doors):
            if gate.lever is not None and self._near(self.player, gate.lever, 28):
                state.latched = not state.latched
                self._update_doors(0)
                action = '열린 상태로 고정했습니다.' if state.latched else '고정을 풀었습니다.'
                self.notify(f'{gate.label} 문을 {action}')
                break

    def toggle_recording(self):
        if self.result != 'playing':
            return
        if self.recording is None and self.confused > 0:
            self.notify('기절해서 움직일 수 없습니다!')
            return
        if self.recording is None and self.player.elevator_target is not None:
            self.notify('승강기가 멈춘 뒤 분신 녹화를 시작하세요.')
            return
        if self.recording is None and self.player.jump_time > 0:
            self.notify('착지한 뒤 분신 녹화를 시작하세요.')
            return
        if self.recording is None:
            self.start_recording()
        else:
            self._finish_recording()

    def start_recording(self, monster_kind: str | None = None):
        self.echo_selecting = False
        # 하늘 섬 스테이지는 섬 위에 선 채로도 녹화한다. 다른 스테이지는 발판 퍼즐이 풀리지 않게 바닥에서만.
        if self.player.fall_speed or (self.player.base != 0 and not self.stage.sky):
            self.notify('바닥에 내려선 뒤 분신 녹화를 시작하세요.')
            return
        if self.recording is None:
            clock = self.platform_clock()
            # 녹화용 분신을 만들기 전에 기존 재현 분신을 없애 한 명만 유지한다.
            self._remove_echo()
            start = Point(self.player.x, self.player.floor)
            facing = self.player.facing
            preview = Actor.at(start, facing)
            preview.base = self.player.base
            self.recording = Recording(start, facing, preview, monster_kind=monster_kind,
                                       clock=clock, base=self.player.base)
            self._update_doors(0)

    @property
    def pending_monster_echo(self):
        return self.pending_monster_echoes[0] if self.pending_monster_echoes else None

    def offer_monster_echo(self, kind):
        # 능력은 스테이지 둘마다 하나다. 뿔짐승은 2스테이지에 나와 싸우기만 하고 분신이 되지 않는다.
        if kind in BOSS_KINDS or kind in ('tier_ghost', 'beast'):
            return
        # The guard and regular armor share the same monster form.
        kind = 'magic_armor' if kind == 'magic_armor_guard' else kind
        if kind in self.monster_echoes or kind in self.pending_monster_echoes:
            return
        if len(self.monster_echoes) < 2 and not self.pending_monster_echoes:
            self.monster_echoes.append(kind)
            self.notify('몬스터 분신을 획득했습니다! C 키로 선택하세요.')
        else:
            self.pending_monster_echoes.append(kind)

    def resolve_monster_echo(self, slot=None):
        if not self.pending_monster_echoes:
            return
        kind = self.pending_monster_echoes.pop(0)
        if slot is not None and 0 <= slot < len(self.monster_echoes):
            self.monster_echoes[slot] = kind
            self.notify('몬스터 분신을 교체했습니다.')
        else:
            self.notify('새 몬스터 분신을 획득하지 않았습니다.')
        self.pending_monster_echoes = [kind for kind in self.pending_monster_echoes
                                       if kind not in self.monster_echoes]

    def cancel_recording(self):
        if self.recording is not None:
            self._clear_actor_target(self.recording.preview)
            self.recording = None

    def _finish_recording(self, time_limit: bool = False):
        record = self.recording
        self.recording = None
        if record is not None:
            self._clear_actor_target(record.preview)
        if record is None or not record.inputs:
            return
        self._remove_echo()
        actor = Actor.at(record.start, record.facing)
        actor.base = record.base   # 섬이 떠나 버렸으면 그 자리에서 떨어진다
        self.echo = Echo(actor, tuple(record.inputs), monster_kind=record.monster_kind, clock=record.clock)
        self._update_doors(0)

    def step(self, motion: Motion = Motion(), attack: str | bool = False):
        if self.result != 'playing' or self.echo_selecting or self.pending_monster_echo:
            return
        self.message_time = max(0, self.message_time - STEP)
        self._update_snakes()
        self._update_ferries()
        recording = self.recording
        if recording is not None:
            preview = recording.preview
            spider = recording.monster_kind == 'crawler'
            aim = preview.web_aim_x if preview.web_aiming else (motion.horizontal or preview.facing)
            hanging = preview.web_time > 0
            self._move(preview, motion, recording.monster_kind)
            if spider and motion.web_aiming:
                # 조준하는 동안은 재현에 남기지 않는다. 줄에 매달리거나 날아가는 중이면 몸의 움직임만 남긴다.
                if hanging:
                    recording.inputs.append(Motion())
            elif spider and motion.web:
                recording.inputs.append(replace(motion, aim_x=aim))
            else:
                recording.inputs.append(motion)

        self.time += STEP
        self.guard_open_time = max(0, self.guard_open_time - STEP)
        self.invulnerable = max(0, self.invulnerable - STEP)
        self.echo_invulnerable = max(0, self.echo_invulnerable - STEP)
        self.attack_cooldown = max(0, self.attack_cooldown - STEP)
        self.attack_flash = max(0, self.attack_flash - STEP)
        self.attack_age += STEP
        self.shake = max(0, self.shake - STEP)
        self.confused = max(0, self.confused - STEP)
        self.level_up_time = max(0, self.level_up_time - STEP)
        self.flash_time = max(0, self.flash_time - STEP)
        self.skill_unlock_time = max(0, self.skill_unlock_time - STEP)
        for text in self.damage_texts:
            text[2] += STEP
        self.damage_texts = [text for text in self.damage_texts if text[2] < 0.8]
        for spark in self.hit_sparks:
            spark[2] += STEP
        self.hit_sparks = [spark for spark in self.hit_sparks if spark[2] < 0.5]
        if self.attack_hit_pending and self.attack_flash <= self.attack_duration * 0.55:
            self.attack_hit_pending = False
            self._apply_attack()
        player_x, player_floor = self.player.x, self.player.floor
        if recording is None and not (self.gravity_field and self.gravity_field.captured):
            # 낙석에 맞아 기절했거나 포털에 빨려 들어가는 동안은 입력을 받지 않는다 (하던 점프·낙하는 이어진다).
            self._move(self.player, Motion() if self.confused > 0 or self.absorb_time else motion)
            self._block_body(player_x, player_floor)
        elif recording is not None:
            self.player.moving = False
        boss_skills.update_gravity(self, motion.horizontal if recording is None else 0)
        if self.result != 'playing':
            return
        for floor, left, right in self.stage.poison_zones:
            if (self.player.floor == floor and left <= self.player.x <= right
                    and self.player.elevator_target is None and self.player.jump_height < 12 - POISON_DEPTH):
                self.hurt(max(1, round(self.max_health * HAZARD_RATIO)), '독에 닿았습니다!')
            for actor in self.echo_actors():
                if (actor.floor == floor and left <= actor.x <= right
                        and actor.elevator_target is None and actor.jump_height < 12 - POISON_DEPTH):
                    self.hurt_echo(actor, max(1, round(self.max_health * HAZARD_RATIO)))
        for hazard in self.stage.hidden_hazards:
            # 분신의 빛이 닿지 않은 함정은 뛰어넘을 수도 없다. 무작정 점프로는 통과하지 못한다.
            airborne = self.player.jump_time > 0 and self.hazard_lit(hazard)
            if not airborne and self.player.floor == hazard.floor and abs(self.player.x - hazard.x) <= 18:
                # 맞으면서 밀고 지나갈 수 없도록 온 방향으로 튕겨 낸다. 점프로만 넘는다.
                self._move_x(self.player, 70 if player_x > hazard.x else -70)
                self.hurt(max(1, round(self.max_health * HAZARD_RATIO)),
                          '숨겨진 함정입니다! 분신 곁에서 위치를 보고 뛰어넘으세요.')
                self.sounds.append('trap')
                self.notify('숨겨진 함정입니다! 분신 곁에서 위치를 보고 뛰어넘으세요.')
                if self.result != 'playing':
                    return
        if recording is None and attack and self.attack_cooldown == 0 and self.confused == 0:
            self._attack(attack if isinstance(attack, str) else 'slash')

        if self.echo is not None:
            previous_x = self.echo.actor.x
            previous_floor = self.echo.actor.floor
            self._move(self.echo.actor, self.echo.inputs[self.echo.cursor], self.echo.monster_kind)
            self._update_sequence(previous_x, previous_floor)
            self.echo.cursor += 1
            if self.echo.cursor == len(self.echo.inputs):
                self._remove_echo()

        self._update_reveal()
        self._update_switches()
        self._update_sky()
        self._update_potions()
        self._update_portals()
        if self.player.base < -PIT_DEPTH and self.stage.tower:
            self._fall_back_to_floor_start()   # 사슬 뱀의 탑: 아래층으로 떨어지지 않고 이 층 시작 자리로 돌아간다
        elif self.player.base < -PIT_DEPTH:
            self.invulnerable = 0
            self.hurt(self.health, '구덩이에 떨어졌습니다!')
            return
        if self.recording is not None and self.recording.preview.base < -PIT_DEPTH:
            self.cancel_recording()
        if self.echo is not None and self.echo.actor.base < -PIT_DEPTH:
            self._remove_echo()

        self._update_sync()
        self._update_bridge()
        self._update_ropes()
        self._update_eggs()
        if self.result != 'playing':
            return
        self._update_watch()
        if self.result != 'playing':
            return

        boss_skills.update_effects(self)
        for enemy in self.enemies:
            self._update_enemy(enemy)
            if self.health <= 0:
                self.result = 'defeated'
                return

        self._update_doors(STEP)
        if (recording is not None and self.recording is recording
                and len(recording.inputs) >= round(self.stage.echo_seconds / STEP)):
            self._finish_recording(time_limit=True)
        if self.pending_monster_echo:
            return
        if self.portal_opened_at is not None and recording is None:
            self._pull_into_portal()
            return
        if self._near(self.player, self.stage.exit, 27) and abs(self.player.base - self.stage.exit_height) < 1:
            if any(enemy.spawn.kind in BOSS_KINDS for enemy in self.enemies):
                if self.message_time <= 0:
                    self.notify('보스를 처치하면 출구가 열립니다.')
            elif self.index in SKY_ROOMS:
                pass   # 포털 너머 방은 몬스터를 다 잡으면 열리는 포털로만 나간다
            elif self.stage.sky and len(self.sky_keys) < len(self.stage.sky.switches):
                # 벽 문은 높이 125 위로 넘을 수 있어 하늘 땅 계단으로 넘지 못하게 출구 자체를 잠근다.
                if self.message_time <= 0:
                    self.notify(f'열쇠 3개를 모아야 출구가 열립니다. (지금 {len(self.sky_keys)}개)')
            elif not self.portal_open:
                pass   # 포탈 스위치를 누르기 전엔 출구 자리가 비어 있다
            else:
                self.result = 'cleared'

    def _pull_into_portal(self):
        """보스방 출구 포털: 가까이 오면 끌어당기고, 가운데에 닿으면 빨려 들어가 클리어한다."""
        player, portal = self.player, self.stage.exit
        if self.absorb_time:
            self.absorb_time += STEP
            if self.absorb_time >= ABSORB_SECONDS:
                self.result = 'cleared'
            return
        # 포털(높이 약 220) 위를 지나는 하늘 섬에 서 있으면 끌어당기지 않는다
        if player.floor != portal.floor or player.elevator_target is not None or player.jump_height > 200:
            return
        gap = portal.x - player.x
        if abs(gap) <= 20:
            self.absorb_time = STEP
            self.invulnerable = ABSORB_SECONDS + 1
            self.notify('포털에 빨려 들어갑니다!')
        elif abs(gap) <= PULL_RANGE:
            closeness = 1 - abs(gap) / PULL_RANGE
            pull = PULL_SPEED[0] + (PULL_SPEED[1] - PULL_SPEED[0]) * closeness * closeness
            self._move_x(player, (1 if gap > 0 else -1) * min(abs(gap), pull * STEP))

    @property
    def portal_open(self) -> bool:
        """문 없는 스위치(출구 포탈 스위치)가 모두 눌렸는가. 그런 스위치가 없으면 늘 열려 있다."""
        ferries = {platform.switch for platform in self.stage.platforms if platform.switch is not None}
        return all(on for index, (switch, on) in enumerate(zip(self.stage.switches, self.switched))
                   if switch.door is None and index not in ferries)

    def warp_to_boss(self):
        """본체를 보스가 있는 층의 입구(그 층으로 올라오는 사다리·승강기)로 옮긴다. B 키용."""
        boss = next(enemy for enemy in self.enemies if enemy.spawn.kind in BOSS_KINDS)
        floor = boss.actor.floor
        entries = [stair.x for stair in self.stage.stairs + self.stage.elevators if stair.lower == floor - 1]
        self.player.x = entries[0] if entries else boss.actor.x - 400
        self.player.floor = floor

    def warp_to_floor(self, floor: int) -> bool:
        """본체를 같은 스테이지의 floor층 입구로 옮긴다. - 키용.
        그 층으로 올라오는 승강기·사다리 자리에 내려 구덩이나 독 위에 떨어지지 않게 한다. 1층은 시작 위치."""
        if not 0 <= floor < self.stage.floors or self.result != 'playing':
            return False
        if self.recording is not None:
            self.notify('분신 녹화 중에는 층을 옮길 수 없습니다.')
            return False
        entries = [stair.x for stair in self.stage.elevators + self.stage.stairs if stair.lower == floor - 1]
        if self.stage.tower:
            x = self.stage.tower.starts[floor]
        elif entries:
            x = entries[0]
        elif self.stage.start.floor == floor:
            x = self.stage.start.x
        else:
            x = next((stair.x for stair in self.stage.elevators + self.stage.stairs if stair.lower == floor),
                     self.stage.start.x)
        self.player = Actor(x, floor, self.player.facing)
        self._update_doors(0)
        self.notify(f'{floor + 1}층으로 이동했습니다.')
        return True

    def hazard_lit(self, hazard: Point) -> bool:
        """분신의 빛이 함정을 비추는가. 같은 층에서는 곁을, 바로 위층에서는 발밑 아래층을 비춘다."""
        if self.echo is None or self.echo.actor.elevator_target is not None:
            return False
        echo = self.echo.actor
        if echo.floor == hazard.floor:
            return abs(echo.x - hazard.x) <= 120
        return echo.floor == hazard.floor + 1 and abs(echo.x - hazard.x) <= LIGHT_BELOW

    def taunt_plate(self) -> Point | None:
        """수호자 앞의 도발 발판. 분신이 그 위에 서면 수호자는 분신만 노린다."""
        guard = self.stage.guard
        if guard is None:
            return None
        return Point(guard.x - TAUNT_OFFSET, guard.floor)

    def bridge_tile_at(self, floor: int, x: float) -> tuple[int, int] | None:
        """그 자리의 거미줄 다리 (다리 번호, 칸 번호). 다리 밖이면 None."""
        for index, bridge in enumerate(self.stage.bridges):
            if bridge.floor == floor and bridge.left < x < bridge.right:
                return index, min(len(self.bridge_tiles[index]) - 1, int((x - bridge.left) // bridge.tile))
        return None

    def hunt_open(self, gate) -> bool:
        """사냥 문: 그 구역에서 나온 몬스터가 모두 쓰러졌는가."""
        return not any(enemy.spawn.point.floor == gate.door.floor and gate.left <= enemy.spawn.point.x <= gate.right
                       for enemy in self.enemies)

    def _block_body(self, x: float, floor: int):
        # 처치 불가 적은 본체가 몸으로 지나갈 수 없다. 분신으로 유인하거나 다른 층으로 돌아간다.
        if self.player.floor != floor:
            return
        for enemy in self.enemies:
            if (enemy.health is None and enemy.spawn.point != self.stage.guard and enemy.actor.floor == floor
                    and (x - enemy.actor.x) * (self.player.x - enemy.actor.x) < 0):
                self.player.x = x
                self.player.moving = False
                if self.message_time <= 0:
                    self.notify('이 적은 지나갈 수 없습니다. 분신으로 유인하거나 돌아가세요.')

    def _barriers(self, floor: int):
        room = self.stage.isolation
        if room:
            if self.isolation_closed and room.door.floor == floor:
                yield room.door.x
            if not self.isolation_closed and room.exit_gate.floor == floor:
                yield room.exit_gate.x
        if (self.stage.guard and self.stage.guard.floor == floor
                and self.guard_open_time == 0
                and any(enemy.spawn.point == self.stage.guard for enemy in self.enemies)):
            yield self.stage.guard.x
        if self.stage.sync_gate and not self.sync_unlocked and self.stage.sync_gate.door.floor == floor:
            yield self.stage.sync_gate.door.x
        if self.stage.sequence and not self.sequence_unlocked and self.stage.sequence.door.floor == floor:
            yield self.stage.sequence.door.x
        for wall in self.stage.walls:
            if wall.floor == floor:
                yield wall.x
        for gate, state in zip(self.stage.gates, self.doors):
            if gate.door.floor == floor and not state.open:
                yield gate.door.x
        for switch, on in zip(self.stage.switches, self.switched):
            if not on and switch.door and switch.door.floor == floor:
                yield switch.door.x
        for gate in self.stage.hunt_gates:
            if gate.door.floor == floor and not self.hunt_open(gate):
                yield gate.door.x

    def _spider_surfaces(self, floor):
        # 충돌 가능한 문과 벽만 사용한다. 경비 몬스터와 배경 무늬는 제외한다.
        for gate, state in zip(self.stage.gates, self.doors):
            if not state.open and gate.door.floor == floor:
                yield gate.door.x
        for wall in self.stage.walls:
            if wall.floor == floor:
                yield wall.x
        if self.stage.sequence and not self.sequence_unlocked and self.stage.sequence.door.floor == floor:
            yield self.stage.sequence.door.x
        if self.stage.sync_gate and not self.sync_unlocked and self.stage.sync_gate.door.floor == floor:
            yield self.stage.sync_gate.door.x
        if self.stage.isolation:
            room = self.stage.isolation
            door = room.door if self.isolation_closed else room.exit_gate
            if door.floor == floor:
                yield door.x

    def spider_web_target(self, actor, aim_x):
        """위·대각선 방향의 광선이 실제 장애물이나 위층 바닥에 닿는 첫 지점."""
        origin_x, origin_y = actor.x, actor.jump_height + 34
        dx, dy = aim_x / hypot(aim_x, 1), 1 / hypot(aim_x, 1)
        hits = []
        for beam in self.stage.web_beams:
            if beam.floor != actor.floor:
                continue
            distance = (beam.underside - origin_y) / dy
            x = origin_x + dx * distance
            if 0 < distance <= SPIDER_AIM_REACH and beam.left <= x <= beam.right:
                hits.append((distance, x, beam.underside))
        if actor.floor + 1 < self.stage.floors:
            # 다층 맵의 층 간격과 바닥 두께. 후반 맵은 원본 이미지 비율을 따른다.
            if self.index in (6, 7, 8):
                levels = (0, 235 * 400 / 231, 462 * 400 / 231,
                          462 * 400 / 231 + 400, 462 * 400 / 231 + 400 + 235 * 400 / 231)
                ceiling = levels[actor.floor + 1] - levels[actor.floor] - 35
            else:
                ceiling = self.stage.floor_height - 35
            distance = (ceiling - origin_y) / dy
            if 0 < distance <= SPIDER_AIM_REACH and LEFT <= origin_x + dx * distance <= RIGHT:
                hits.append((distance, origin_x + dx * distance, ceiling))
        if dx:
            for wall in (LEFT, RIGHT, *self._spider_surfaces(actor.floor)):
                distance = (wall - origin_x) / dx
                y = origin_y + distance * dy
                limit = 365 if wall in (LEFT, RIGHT) else SPIDER_DOOR_CLIMB_HEIGHT
                if 0 < distance <= SPIDER_AIM_REACH and 0 < y <= limit:
                    hits.append((distance, wall, y))
        for wall in self._spider_surfaces(actor.floor):
            distance = (SPIDER_DOOR_CLIMB_HEIGHT - origin_y) / dy
            x = origin_x + dx * distance
            if 0 < distance <= SPIDER_AIM_REACH and abs(x - wall) <= GATE_HALF_WIDTH:
                hits.append((distance, x, SPIDER_DOOR_CLIMB_HEIGHT))
        if not hits:
            return None
        _, x, y = min(hits)
        return x, y

    def _swing(self, actor: Actor, motion: Motion):
        """거미줄 그네 한 스텝. 매달린 동안은 진자, 놓은 뒤에는 포물선으로 움직인다."""
        actor.web_time += STEP
        if not actor.web_flying and motion.release:
            # D: 날아가지 않고 그 자리에서 줄을 놓고 떨어진다.
            actor.web_flying = True
            actor.web_vx = actor.web_vy = 0.0
        elif not actor.web_flying and motion.jump:
            # 놓는 순간의 진자 속도 그대로 날아간다.
            actor.web_flying = True
            actor.web_vx = actor.web_speed * actor.web_length * cos(actor.web_angle)
            actor.web_vy = actor.web_speed * actor.web_length * sin(actor.web_angle)
            if actor.web_anchor_beam:
                # 문 위 조각상 줄에서 놓을 때 문 높이까지 도약할 수 있다.
                actor.web_vy = max(actor.web_vy, 650.0)
        if actor.web_flying:
            if actor.web_anchor_beam and motion.horizontal:
                actor.web_vx = motion.horizontal * MOVE_SPEED
            actor.web_vy -= SPIDER_GRAVITY * STEP
            actor.web_height = max(0.0, actor.web_height + actor.web_vy * STEP)
            target = actor.x + actor.web_vx * STEP
            self._move_x(actor, target - actor.x, over=actor.web_height >= SPIDER_OVER_HEIGHT)
            if abs(actor.x - target) > 0.01:
                actor.web_vx = 0.0  # 벽이나 닫힌 문에 부딪혔다
            if actor.web_vx:
                actor.facing = 1 if actor.web_vx > 0 else -1
            if actor.web_height <= 0 and actor.web_vy <= 0:
                actor.web_time, actor.web_flying, actor.web_height = 0.0, False, 0.0
            return
        if motion.horizontal:
            actor.facing = motion.horizontal
        if motion.stairs:
            actor.web_length = max(SPIDER_WEB_MIN, min(max(SPIDER_WEB_MAX, actor.web_length),
                                   actor.web_length - motion.stairs * SPIDER_REEL * STEP))
        accel = -SPIDER_GRAVITY / actor.web_length * sin(actor.web_angle) + motion.horizontal * SPIDER_PUMP
        actor.web_speed = (actor.web_speed + accel * STEP) * (1 - SPIDER_DAMPING * STEP)
        angle = actor.web_angle + actor.web_speed * STEP
        if abs(angle) > SPIDER_MAX_ANGLE:
            angle, actor.web_speed = max(-SPIDER_MAX_ANGLE, min(SPIDER_MAX_ANGLE, angle)), 0.0
        actor.web_angle = angle
        height = actor.web_anchor_height - actor.web_length * cos(angle)
        if height < 0 and cos(angle) > 0:
            # 바닥을 뚫고 내려가지 않도록 줄이 팽팽해질 때까지 짧아진다.
            actor.web_length = max(SPIDER_WEB_MIN, actor.web_anchor_height / cos(angle))
            height = 0.0
        target = actor.web_anchor_x + actor.web_length * sin(angle)
        self._move_x(actor, target - actor.x, over=height >= SPIDER_OVER_HEIGHT)
        if abs(actor.x - target) > 0.5:
            # 낮게 흔들리다 벽이나 닫힌 문에 막혔다. 막힌 자리에 맞춰 줄 각도를 다시 잡는다.
            actor.web_speed = 0.0
            actor.web_angle = asin(max(-1.0, min(1.0, (actor.x - actor.web_anchor_x) / actor.web_length)))
            height = actor.web_anchor_height - actor.web_length * cos(actor.web_angle)
        actor.web_height = max(0.0, height)  # 줄이 길면 바닥을 스치며 흔들린다

    def _move_x(self, actor: Actor, amount: float, ignore_barrier=None, over=False):
        start = actor.x
        target = min(RIGHT, max(LEFT, start + amount))
        margin = GATE_HALF_WIDTH + ACTOR_RADIUS
        # 문·벽(높이 약 120)보다 높은 공중 턱이나 그네 위에서는 그 위를 지나간다.
        over = over or actor.jump_height >= SPIDER_OVER_HEIGHT
        for wall in () if over else self._barriers(actor.floor):
            if ignore_barrier is not None and abs(wall - ignore_barrier) < 0.01:
                continue
            if start <= wall - margin and target > wall - margin:
                target = wall - margin
            elif start >= wall + margin and target < wall + margin:
                target = wall + margin
        for block in self.stage.jump_blocks:
            # 점프 블록은 그 높이보다 높이 떠 있을 때만 넘어간다.
            if block.floor != actor.floor or actor.jump_height >= block.height:
                continue
            edge = block.width / 2 + ACTOR_RADIUS
            if start <= block.x - edge and target > block.x - edge:
                target = block.x - edge
            elif start >= block.x + edge and target < block.x + edge:
                target = block.x + edge
        actor.x = target
        distance = abs(target - start)
        actor.moving = distance > 0.001
        actor.walk_distance += distance

    def platform_visible(self, index: int) -> bool:
        return not self.stage.platforms[index].hidden or index in self.revealed

    def platform_clock(self) -> float:
        """움직이는 발판의 시계. 분신을 녹화·재현하는 동안은 그 프레임 번호로 세어서
        재현 분신이 녹화 때와 똑같이 움직이는 발판을 만나게 한다."""
        if self.recording is not None:
            return self.recording.clock + len(self.recording.inputs) * STEP
        if self.echo is not None:
            return self.echo.clock + self.echo.cursor * STEP
        return self.time

    def platform_span(self, index: int, clock: float | None = None) -> tuple[float, float]:
        platform = self.stage.platforms[index]
        if platform.switch is not None:   # 나룻배 발판은 제 시계로 움직인다
            clock = self.ferry_clock[index]
        shift = platform.shift(self.platform_clock() if clock is None else clock)
        return platform.left + shift, platform.right + shift

    def _ride(self, actor: Actor):
        """움직이는 발판 위에 서 있으면 발판과 함께 옮겨 간다."""
        if actor.jump_time > 0 or actor.fall_speed or actor.base <= 0 or actor.web_time > 0:
            return
        clock = self.platform_clock()
        for index, platform in enumerate(self.stage.platforms):
            if (platform.swing and platform.switch is None and platform.floor == actor.floor
                    and platform.height == actor.base and self.platform_visible(index)):
                left, right = self.platform_span(index, clock - STEP)
                if left <= actor.x <= right:
                    actor.x += platform.shift(clock) - platform.shift(clock - STEP)
                    return

    def _update_ferries(self):
        """나룻배 발판: 스위치가 눌린 뒤 누가 올라서 있으면 건너편으로 가고(위에 선 사람도 함께), 비면 돌아온다."""
        actors = [self.player, *self.echo_actors()]
        for index, platform in enumerate(self.stage.platforms):
            if platform.switch is None:
                continue
            left, right = self.platform_span(index)
            riders = [actor for actor in actors
                      if actor.floor == platform.floor and actor.jump_time == 0 and not actor.fall_speed
                      and actor.base == platform.height and left <= actor.x <= right]
            clock = self.ferry_clock[index]
            if riders and self.switched[platform.switch]:
                clock = min(platform.period / 2, clock + STEP)
            elif not riders:
                clock = max(0.0, clock - STEP)
            dx = platform.shift(clock) - platform.shift(self.ferry_clock[index])
            for actor in riders:
                actor.x += dx
            self.ferry_clock[index] = clock

    def _over_pit(self, floor: int, x: float) -> bool:
        return any(pit_floor == floor and left < x < right for pit_floor, left, right in self.stage.chasms)

    def _ground_heights(self, actor: Actor):
        """actor가 지금 x에서 설 수 있는 높이들. 구덩이 밖 바닥(0)과 보이는 발판."""
        if not self._over_pit(actor.floor, actor.x):   # 독 웅덩이 안은 바닥이 수면 높이로 가라앉아 있다
            poisoned = any(floor == actor.floor and left <= actor.x <= right
                           for floor, left, right in self.stage.poison_zones)
            yield -float(POISON_DEPTH) if poisoned else 0.0
        elif actor is self.player and (spot := self.bridge_tile_at(actor.floor, actor.x)):
            if self.bridge_tiles[spot[0]][spot[1]] > 0:
                yield 0.0   # 거미줄 다리: 본체만 거미줄 위를 걷는다
        for index, platform in enumerate(self.stage.platforms):
            if platform.floor == actor.floor and self.platform_visible(index):
                left, right = self.platform_span(index)
                if left <= actor.x <= right:
                    yield float(platform.height)
        if self.sky_blocks and actor.floor == 0:
            half = self.stage.sky.width / 2
            for x, height in self.sky_blocks:
                if abs(actor.x - x) <= half:
                    yield float(height)
        if self.stage.tower:
            for snake, (head, _) in zip(self.stage.tower.snakes, self.snake_state):
                if snake.floor == actor.floor:
                    for _, left, right, height in chain_snake.surfaces(snake, head):
                        if left <= actor.x <= right:
                            yield float(height)

    def _snake_under(self, actor: Actor):
        """actor가 딛고 선 사슬 뱀 면: (뱀 번호, 길 조각 번호) 또는 None.
        모서리에서 두 조각의 면이 겹치면 길에서 뒤쪽 조각을 고른다: 머리가 위로 꺾이면 그 세로 몸을 타고 함께 올라간다."""
        if actor.jump_time > 0 or actor.fall_speed or actor.elevator_target is not None:
            return None
        found = None
        for index, (snake, (head, _)) in enumerate(zip(self.stage.tower.snakes, self.snake_state)):
            if snake.floor != actor.floor:
                continue
            for piece, left, right, height in chain_snake.surfaces(snake, head):
                if left <= actor.x <= right and abs(actor.base - height) < 0.5 and (found is None or piece > found[1]):
                    found = index, piece
        return found

    def _start_snake(self, index: int):
        snake = self.stage.tower.snakes[index]
        if not self.snake_state[index][1]:
            self.snake_state[index][1] = True
            self.sounds.append('chain')
            self.notify('사슬 뱀이 움직입니다! 꼬리부터 사라지니 머리 쪽으로 걸으세요.')
        if snake.partner is not None:
            self.snake_state[snake.partner][1] = True

    def _update_snakes(self):
        """사슬 뱀을 한 스텝 움직인다. 올라탄 뱀은 출발하고, 오르내리는 세로 몸 위에 선 본체·분신은 함께 오르내리며,
        층 높이까지 올라가면 위층 바닥으로 넘어간다."""
        tower = self.stage.tower
        if tower is None:
            return
        riders = [actor for actor in (self.player, self.recording.preview if self.recording else None,
                                      self.echo.actor if self.echo else None) if actor is not None]
        spots = [self._snake_under(actor) for actor in riders]
        for spot in spots:
            if spot is not None:
                self._start_snake(spot[0])
        for snake, state in zip(tower.snakes, self.snake_state):
            if state[1]:
                state[0] += snake.speed * STEP
        for actor, spot in zip(riders, spots):
            if spot is None:
                continue
            # 이 뱀에서 두 스텝 안에 오르내린 면 가운데 가장 높은 면에 선다: 머리가 위로 꺾이면 그 세로 몸을 타고 오르고,
            # 꼬리가 세로 몸을 내려가면 함께 내려간다. 그런 면이 없으면 (발밑이 사라졌으면) 떨어진다.
            snake = tower.snakes[index := spot[0]]
            reach = 2 * snake.speed * STEP + 0.5   # 처음 닿는 프레임에 세로 몸이 이미 한 스텝 올라가 있을 수 있다
            heights = [height for _, left, right, height in chain_snake.surfaces(snake, self.snake_state[index][0])
                       if left <= actor.x <= right and abs(height - actor.base) <= reach]
            if heights:
                actor.base = float(max(heights))
            if actor.base >= self.stage.floor_height - 0.5 and actor.floor + 1 < self.stage.floors:
                actor.floor += 1
                actor.base = max(0.0, actor.base - self.stage.floor_height)   # 위층 바닥에 딱 맞춰 선다

    def _fall_back_to_floor_start(self):
        floor = self.player.floor
        self.player = Actor(self.stage.tower.starts[floor], floor, 1)
        for snake, state in zip(self.stage.tower.snakes, self.snake_state):
            if snake.floor == floor:
                state[:] = [chain_snake.start_head(snake), not snake.wait]
        self.sounds.append('hurt')
        self.notify('떨어졌습니다! 이 층 시작 자리로 돌아가고 뱀도 처음 자리에서 다시 기다립니다.')

    def _end_jump(self, actor: Actor):
        """점프 포물선이 끝났다. 발판에서 뛰어 디딜 곳이 없으면 포물선 끝의 내려오던 속도로 이어서 떨어진다
        (0부터 다시 떨어지면 공중에서 멈칫한다)."""
        actor.jump_time = 0.0
        if actor.base not in self._ground_heights(actor):
            actor.fall_speed = 4 * actor.jump_peak / actor.jump_duration
        elif actor is self.player:
            self.sounds.append('land')

    def _settle(self, actor: Actor, before: float):
        """발판 착지와 낙하. 점프가 내려오다 발판 높이를 지나면 그 위에 선다."""
        # 발판 없는 방이라도 2단 점프로 공중에 떠 있으면(base > 0) 바닥까지 떨어뜨린다.
        if (not self.stage.chasms and not self.stage.platforms and not self.stage.sky and not self.stage.poison_zones
                and actor.base == 0 and not actor.fall_speed) or actor.elevator_target is not None \
                or (actor.dash_time > 0 and actor.dash_vy > 0) \
                or actor.web_time > 0 or actor.door_climb_time > 0 or actor.rope is not None:
            return
        if actor.jump_time > 0:
            now = actor.jump_height
            landing = [height for height in self._ground_heights(actor) if now <= height <= before]
            if now < before and landing:
                actor.base, actor.jump_time, actor.beast_super_jump = max(landing), 0.0, False
                if actor is self.player:
                    self.sounds.append('land')
            return
        if actor.fall_speed == 0 and actor.base in self._ground_heights(actor):
            return
        if (actor.fall_speed == 0 and -POISON_DEPTH - 0.5 <= actor.base < 0
                and 0.0 in self._ground_heights(actor)):
            actor.base = 0.0   # 가라앉은 독 웅덩이에서 바닥으로 걸어 나오면 턱을 딛고 올라선다
            return
        actor.fall_speed += FALL_GRAVITY * STEP
        below = actor.base - actor.fall_speed * STEP
        landing = [height for height in self._ground_heights(actor) if below <= height <= actor.base]
        if landing:
            actor.base, actor.fall_speed = max(landing), 0.0
            if actor is self.player:
                self.sounds.append('land')
        else:
            actor.base = below

    def _watchers(self):
        if self.recording is not None and self.recording.monster_kind == 'watcher':
            yield self.recording.preview
        if self.echo is not None and self.echo.monster_kind == 'watcher':
            yield self.echo.actor

    def _update_reveal(self):
        """외눈 유령 분신이 있는 동안 레이더 안의 발판이 드러나고, 분신이 사라지면
        stage.reveal_seconds(1스테이지 10초) 뒤 다시 숨는다. 레이더 원이 렌즈에 닿으면 그 층 발판이 모두 드러난다."""
        if not self.stage.platforms:
            return
        watchers = list(self._watchers())
        if watchers:
            self.reveal_time = self.stage.reveal_seconds
        elif self.reveal_time > 0:
            self.reveal_time = max(0.0, self.reveal_time - STEP)
            if self.reveal_time == 0 and self.revealed:
                self.revealed.clear()
                self.lens_lit = False
        lens = self.stage.lens
        for actor in watchers:
            if not actor.radar or actor.elevator_target is not None:
                continue
            eye = actor.jump_height + RADAR_EYE
            lit = (lens is not None and lens.floor == actor.floor
                   and hypot(lens.x - actor.x, lens.height - eye) <= RADAR_RANGE)
            if lit and not self.lens_lit:
                self.lens_lit = True
            for index, platform in enumerate(self.stage.platforms):
                left, right = self.platform_span(index)
                x = min(max(actor.x, left), right)
                if platform.floor == actor.floor and (
                        lit or hypot(x - actor.x, platform.height - eye) <= RADAR_RANGE):
                    self.revealed.add(index)

    def _update_switches(self):
        """분신(녹화 중인 분신 포함)이나 본체가 공중 턱의 스위치에 올라서면 그 문이 열린 채로 고정된다.
        본체는 포털로만 스위치 턱에 갈 수 있다 (점프로는 못 오른다)."""
        for index, switch in enumerate(self.stage.switches):
            if self.switched[index]:
                continue
            for actor in (self.player, *self.echo_actors()):
                if (actor.floor == switch.floor and actor.elevator_target is None and actor.jump_time == 0
                        and actor.fall_speed == 0 and abs(actor.base - switch.height) < 1
                        and abs(actor.x - switch.x) <= PLATE_RANGE):
                    self.switched[index] = True
                    if any(platform.switch == index for platform in self.stage.platforms):
                        self.notify('레버가 당겨졌습니다! 본체로 나룻배 발판에 올라서면 건너편으로 갑니다.')
                    else:
                        self.notify('스위치가 눌렸습니다! ' + ('출구 포탈이 열렸습니다.' if switch.door is None
                                                             else '잠긴 문이 열렸습니다.'))
                    break

    def _sky_book(self):
        """염력을 쓸 수 있는 마법책 분신(녹화 중). 없으면 None."""
        if self.stage.sky and self.recording is not None and self.recording.monster_kind == 'magic_book':
            return self.recording.preview
        return None

    def _sky_clamp(self, book: Actor, x: float, height: float) -> tuple[float, float]:
        """땅이 놓일 자리를 분신 둘레 reach 원 안, 맵 안, 바닥 위로 맞춘다."""
        sky = self.stage.sky
        cx, cy = book.x, book.jump_height + 30
        distance = hypot(x - cx, height - cy)
        if distance > sky.reach:
            x, height = cx + (x - cx) * sky.reach / distance, cy + (height - cy) * sky.reach / distance
        half = sky.width / 2
        return min(max(x, LEFT + half), RIGHT - half), max(20.0, height)

    def sky_grab(self, x: float, height: float) -> bool:
        """마우스를 누른 자리의 하늘 땅을 잡는다. 맵 어디의 땅이든 잡히고, 잡힌 땅은 분신 둘레 reach 안으로 날아온다
        (섬이 떠다니다 가까이 오기를 기다리지 않게)."""
        book = self._sky_book()
        if book is None:
            return False
        sky = self.stage.sky
        hit = [index for index, (bx, bh) in enumerate(self.sky_blocks)
               if abs(x - bx) <= sky.width / 2 + 10 and abs(height - bh) <= 24]
        near = [index for index in hit if index not in sky.fixed]
        if not near:
            return False
        self.sky_hold = min(near, key=lambda index: abs(x - self.sky_blocks[index][0]))
        self.sky_drag(x, height)
        return True

    def sky_drag(self, x: float, height: float):
        """잡은 땅이 갈 자리를 정한다. 땅은 매 프레임 SKY_FLY 빠르기로 그리로 날아간다 (_fly_held_sky)."""
        self.sky_target = (x, height)

    def _fly_held_sky(self, book: Actor):
        tx, th = self._sky_clamp(book, *self.sky_target)
        block = self.sky_blocks[self.sky_hold]
        dx, dh = tx - block[0], th - block[1]
        distance, step = hypot(dx, dh), SKY_FLY * STEP
        if distance > step:
            tx, th = block[0] + dx * step / distance, block[1] + dh * step / distance
        self.sky_blocks[self.sky_hold] = [tx, th]

    def sky_release(self):
        if self.sky_hold is not None:
            self.sky_pin[self.sky_hold] = SKY_PIN
        self.sky_hold = None

    def _sky_goal(self, index):
        sky = self.stage.sky
        if sky.lanes:
            return [self.sky_rng.uniform(*sky.lanes[index]), self.sky_rng.uniform(*SKY_SPEED)]
        half = sky.width / 2
        x = self.sky_rng.uniform(LEFT + half - SKY_WALL_BIAS, RIGHT - half + SKY_WALL_BIAS)
        return [min(max(x, LEFT + half), RIGHT - half), self.sky_rng.uniform(*SKY_SPEED)]

    def _drift_sky(self):
        """잡혀 있거나 멈춘 땅을 빼고 목표 x로 떠간다. 땅 위에 선 본체·분신도 함께 옮겨 간다."""
        half = self.stage.sky.width / 2
        riders = [self.player, self.recording.preview if self.recording else None, self.echo.actor if self.echo else None]
        riders = [a for a in riders if a is not None and a.floor == 0 and a.jump_time == 0 and not a.fall_speed]
        for index, block in enumerate(self.sky_blocks):
            if index == self.sky_hold:
                continue
            if self.sky_pin[index] > 0:
                self.sky_pin[index] -= STEP
                continue
            goal, speed = self.sky_goal[index]
            dx = max(-speed * STEP, min(speed * STEP, goal - block[0]))
            for actor in riders:
                if actor.base == block[1] and abs(actor.x - block[0]) <= half:
                    actor.x += dx
            block[0] += dx
            if block[0] == goal:
                self.sky_goal[index] = self._sky_goal(index)

    def _update_sky(self):
        sky = self.stage.sky
        if not sky:
            return
        if self._sky_book() is None:
            self.sky_release()
        elif self.sky_hold is not None:
            self._fly_held_sky(self._sky_book())   # 분신이 걸어가면 잡은 땅도 끌려온다
        self._drift_sky()
        player = self.player
        on = None
        if player.elevator_target is None and player.jump_time == 0 and player.fall_speed == 0:
            on = next((index for index, (x, height) in enumerate(sky.switches)
                       if player.floor == 0 and abs(player.base - height) < 1
                       and abs(player.x - x) <= PLATE_RANGE), None)
        if on is not None and on != self.sky_on:
            if on in self.sky_keys:
                self.notify(f'{on + 1}번 포털의 열쇠는 이미 얻었습니다.')
            else:
                self.room_request = next(room for room, portal in SKY_ROOMS.items() if portal == on)
        self.sky_on = on

    def enter_room(self) -> 'World':
        """밟은 하늘 포털 너머의 몬스터 방. 체력·경험치·무기·분신을 그대로 가져간다."""
        room = World(self.room_request, weapon_index=self.weapon_index, xp=self.xp, monster_echoes=self.monster_echoes)
        room.health = self.health
        room.parent = self
        self.room_request = None
        return room

    def back_from_room(self) -> 'World':
        """깬 방에서 하늘 땅의 그 포털 위로 돌아간다. 열쇠를 하나 얻는다."""
        parent = self.parent
        parent.sky_keys.add(SKY_ROOMS[self.index])
        parent.xp, parent.weapon_index, parent.monster_echoes = self.xp, self.weapon_index, self.monster_echoes
        parent.health = min(self.health, parent.max_health)
        keys, need = len(parent.sky_keys), len(parent.stage.sky.switches)
        if keys == need:   # 문 없던 출구 자리에 보스방과 같은 포털(pixelfx)이 열리고, 다가가면 빨려 들어간다
            parent.portal_opened_at = parent.time
            parent.sounds.append('boss_defeat')
            parent.notify('열쇠를 모두 모았습니다! 출구에 포털이 열렸습니다.')
        else:
            parent.notify(f'열쇠 {keys}/{need}')
        return parent

    def _potion_landing(self, floor: int, x: float, before: float, now: float):
        """물약이 before에서 now 높이로 떨어지는 사이 닿는 가장 높은 면: (땅 번호 또는 None, x, 높이)."""
        best = None if self._over_pit(floor, x) or not now <= 0 <= before else (None, x, 0.0)
        for index, platform in enumerate(self.stage.platforms):
            left, right = self.platform_span(index)
            if (platform.floor == floor and self.platform_visible(index) and left <= x <= right
                    and now <= platform.height <= before and (best is None or platform.height > best[2])):
                best = (None, x, float(platform.height))
        if self.sky_blocks and floor == 0:
            for index, (bx, bh) in enumerate(self.sky_blocks):
                if abs(x - bx) <= self.stage.sky.width / 2 and now <= bh <= before and (best is None or bh > best[2]):
                    best = (index, x - bx, float(bh))
        return best

    def _update_potions(self):
        """날아가는 물약. 바닥·발판·하늘 땅에 떨어지면 그 자리에 포털이 생기고,
        결계·구덩이·맵 끝에서는 깨진다. 포털은 한 쌍이라 세 번째 병부터는 오래된 쪽이 옮겨 간다."""
        flying = []
        for x, floor, height, vx, vh in self.potions:
            vh -= POTION_GRAVITY * STEP
            nx, nh = x + vx * STEP, height + vh * STEP
            # shortcut: 결계는 층을 따지지 않는다 (1층짜리 방에만 쓴다). 여러 층에 쓰면 층을 더한다.
            if (not LEFT <= nx <= RIGHT or nh < -PIT_DEPTH
                    or any(left <= nx <= right and bottom <= nh <= top
                           for left, bottom, right, top in self.stage.seals)):
                continue
            landing = self._potion_landing(floor, nx, height, nh) if vh < 0 else None
            if landing is None:
                flying.append([nx, floor, nh, vx, vh])
                continue
            self.portals[self.portal_next] = (floor, *landing)
            self.portal_next = 1 - self.portal_next
            self.portal_lock = True   # 발밑에 생긴 포털로 바로 빨려 들어가지 않게
        self.potions = flying

    def portal_point(self, index: int) -> tuple[int, float, float]:
        """포털의 (층, x, 높이). 하늘 땅 위의 포털은 땅을 따라 움직인다."""
        floor, block, x, height = self.portals[index]
        if block is None:
            return floor, x, height
        bx, bh = self.sky_blocks[block]
        return floor, bx + x, bh

    def _update_portals(self):
        """본체가 포털 위에 서면 다른 쪽 포털로 나온다."""
        player = self.player
        if not all(self.portals) or self.recording is not None or player.elevator_target is not None:
            return
        inside = None
        for index in range(2):
            floor, x, height = self.portal_point(index)
            if player.floor == floor and abs(player.x - x) <= PORTAL_RANGE and abs(player.base - height) < 1:
                inside = index
        if inside is None:
            self.portal_lock = False
            return
        if self.portal_lock or player.jump_time > 0 or player.fall_speed:
            return
        player.floor, player.x, player.base = self.portal_point(1 - inside)
        self.portal_lock = True

    def _move(self, actor: Actor, motion: Motion, monster_kind=None):
        self._ride(actor)
        before = actor.jump_height
        self._move_body(actor, motion, monster_kind)
        self._settle(actor, before)

    def _move_body(self, actor: Actor, motion: Motion, monster_kind=None):
        if actor is self.player and self._climb(actor, motion):
            return
        if monster_kind == 'crawler' and actor.door_climb_time > 0:
            progress = min(1.0, actor.door_climb_time / SPIDER_DOOR_CLIMB_DURATION)
            across = max(0.0, min(1.0, (progress - 0.35) / 0.30))
            target = actor.door_climb_start + (actor.door_climb_end - actor.door_climb_start) * across
            self._move_x(actor, target - actor.x, ignore_barrier=actor.door_climb_x)
            actor.door_climb_time = actor.door_climb_time + STEP if progress < 1 else 0.0
            return
        if actor.elevator_target is not None:
            actor.moving = False
            actor.elevator_time += STEP
            if actor.elevator_time >= ELEVATOR_DURATION:
                actor.floor = actor.elevator_target
                actor.elevator_target = None
                actor.elevator_time = 0.0
            return
        if monster_kind == 'crawler':
            if motion.stairs <= 0:
                actor.spider_up_latched = False
            if motion.horizontal:
                actor.facing = motion.horizontal
            if motion.web_aiming:
                if not actor.web_aiming:
                    actor.web_aim_x = actor.facing
                actor.web_aiming = True
                if motion.horizontal:
                    actor.web_aim_x = motion.horizontal
                elif motion.stairs > 0:
                    actor.web_aim_x = 0
                if actor.web_time > 0:
                    self._swing(actor, Motion())
                else:
                    actor.moving = False
                return
            if motion.web:
                if motion.aim_x is not None:
                    aim = motion.aim_x
                else:
                    aim = actor.web_aim_x if actor.web_aiming else actor.facing
                target = self.spider_web_target(actor, aim)
                actor.web_aiming = False
                if target is not None:
                    if actor.web_time > 0 and not actor.web_flying:
                        vx = actor.web_speed * actor.web_length * cos(actor.web_angle)
                        vy = actor.web_speed * actor.web_length * sin(actor.web_angle)
                    else:
                        vx = actor.web_vx if actor.web_flying else 0.0
                        vy = actor.web_vy if actor.web_flying else 0.0
                    height = actor.jump_height
                    actor.web_anchor_x, target_y = target
                    actor.web_anchor_beam = any(
                        beam.floor == actor.floor and beam.left <= target[0] <= beam.right
                        and abs(target_y - beam.underside) < 0.01 for beam in self.stage.web_beams
                    )
                    actor.web_anchor_height = target_y - 34
                    offset = actor.x - actor.web_anchor_x
                    vertical = actor.web_anchor_height - height
                    actor.web_length = max(SPIDER_WEB_MIN, hypot(offset, vertical))
                    actor.web_angle = atan2(offset, vertical)
                    actor.web_speed = (vx * cos(actor.web_angle) + vy * sin(actor.web_angle)) / actor.web_length
                    actor.web_time = STEP
                    actor.web_height = height
                    actor.jump_time = 0.0
                    actor.web_flying = False
                    return
            else:
                actor.web_aiming = False
            if actor.web_time > 0:
                self._swing(actor, motion)
                return
            if motion.stairs > 0 and not actor.spider_up_latched and actor.jump_time == 0:
                margin = GATE_HALF_WIDTH + ACTOR_RADIUS
                obstacles = [gate.door.x for gate, state in zip(self.stage.gates, self.doors)
                             if not state.open and gate.door.floor == actor.floor]
                obstacles.extend(wall.x for wall in self.stage.walls if wall.floor == actor.floor)
                if self.stage.sequence and not self.sequence_unlocked and self.stage.sequence.door.floor == actor.floor:
                    obstacles.append(self.stage.sequence.door.x)
                if self.stage.sync_gate and not self.sync_unlocked and self.stage.sync_gate.door.floor == actor.floor:
                    obstacles.append(self.stage.sync_gate.door.x)
                if self.stage.isolation:
                    room = self.stage.isolation
                    door = room.door if self.isolation_closed else room.exit_gate
                    if door.floor == actor.floor:
                        obstacles.append(door.x)
                for obstacle_x in obstacles:
                    if abs(actor.x - obstacle_x) <= margin + 18:
                        side = -1 if actor.x < obstacle_x else 1
                        actor.door_climb_time = STEP
                        actor.door_climb_x = obstacle_x
                        actor.door_climb_start = actor.x
                        actor.door_climb_end = obstacle_x - side * (margin + 4)
                        actor.facing = -side
                        actor.spider_up_latched = True
                        return
            if (motion.stairs and actor.jump_time == 0
                    and (actor.x <= LEFT + ACTOR_RADIUS or actor.x >= RIGHT - ACTOR_RADIUS)
                    and 0 <= actor.floor + motion.stairs < self.stage.floors):
                actor.elevator_target = actor.floor + motion.stairs
                actor.elevator_time = 0.0
                actor.moving = False
                return
        if monster_kind == 'watcher' and motion.web:
            actor.radar = not actor.radar
        if monster_kind == 'potion_slime':
            if motion.web_aiming:
                actor.potion_charge = min(POTION_CHARGE, actor.potion_charge + STEP)
            elif actor.potion_charge > 0:
                if self.recording is not None and actor is self.recording.preview:
                    # 녹화하는 동안만 던진다. 재현 분신이 다시 던지면 만들어 둔 포털이 옮겨 가 버린다.
                    self.potions.append(potion_launch(actor))
                actor.potion_charge = 0.0
        if monster_kind == 'beast':
            if motion.jump and actor.jump_time == 0 and not motion.stairs:
                actor.beast_charge_active = True
                actor.beast_charge = 0.0
            if actor.beast_charge_active:
                if motion.horizontal:
                    actor.facing = motion.horizontal
                if motion.jump_held:
                    actor.beast_charge += STEP
                if not motion.jump_held or actor.beast_charge + 1e-9 >= BEAST_CHARGE_SECONDS:
                    actor.beast_super_jump = actor.beast_charge + 1e-9 >= BEAST_CHARGE_SECONDS
                    actor.jump_duration = BEAST_JUMP_DURATION if actor.beast_super_jump else JUMP_DURATION
                    actor.jump_peak = BEAST_JUMP_HEIGHT if actor.beast_super_jump else JUMP_HEIGHT
                    actor.jump_time = STEP
                    actor.beast_charge_active = False
                else:
                    actor.moving = False
                    return
            elif actor.jump_time > 0:
                actor.jump_time += STEP
                if actor.jump_time >= actor.jump_duration:
                    self._end_jump(actor)
                    actor.beast_super_jump = False
            if motion.horizontal:
                actor.facing = motion.horizontal
            if actor.jump_time > 0 or not motion.stairs:
                self._move_x(actor, motion.horizontal * MOVE_SPEED * STEP)
                return
            # 땅에 있을 때의 사다리와 승강기는 기존 방식으로 처리한다.
        if motion.horizontal:
            actor.facing = motion.horizontal
        moves = self.moves and monster_kind is None   # 본체와 기본 분신만 (녹화하면 분신도 따라 한다)
        if moves:
            self._dash(actor, motion)
        rising = actor.dash_time > 0 and actor.dash_vy > 0   # 위로 대시하는 중 (공중이다)
        if (moves and motion.jump and not actor.air_jumped and not motion.stairs
                and (actor.jump_time > 0 or actor.fall_speed > 0 or rising)):
            # 2단 점프: 지금 높이에서 보통 점프를 한 번 더 한다. 발밑에서 깃털이 터진다.
            actor.base, actor.fall_speed = actor.jump_height, 0.0
            actor.jump_duration, actor.jump_peak, actor.jump_time = self.jump_duration, self.jump_peak, STEP
            actor.air_jumped = True
            if actor is self.player:
                self.sounds.append('double_jump')
            actor.air_dashed, actor.dash_cooldown = False, 0.0   # 2단 점프 뒤 바로 대시를 한 번 더 쓸 수 있다
            self.boss_effects.append(boss_skills.Effect('feather-burst', actor.x, actor.floor, lift=actor.base,
                                                        scale=0.55, life=3.0))
        elif (motion.jump and actor.jump_time == 0 and actor.fall_speed == 0 and not rising
                and not motion.stairs and monster_kind != 'beast'):
            actor.jump_duration = self.jump_duration
            actor.jump_peak = self.jump_peak
            actor.jump_time = STEP
            if actor is self.player:
                self.sounds.append('jump')
        elif actor.jump_time > 0:
            actor.jump_time += STEP
            if actor.jump_time >= actor.jump_duration:
                self._end_jump(actor)
        self._move_x(actor, motion.horizontal * MOVE_SPEED * STEP)
        if motion.stairs and actor.jump_time == 0 and actor.base == 0 and actor.fall_speed == 0:
            lower = actor.floor if motion.stairs > 0 else actor.floor - 1
            for elevator in self.stage.elevators:
                if elevator.lower == lower and abs(elevator.x - actor.x) <= STAIR_RANGE:
                    actor.x = elevator.x
                    actor.elevator_target = actor.floor + motion.stairs
                    actor.elevator_time = 0.0
                    actor.moving = False
                    return
            for stair in self.stage.stairs:
                if stair.lower == lower and abs(stair.x - actor.x) <= STAIR_RANGE:
                    actor.x = stair.x
                    actor.floor += motion.stairs
                    return
    def _dash(self, actor: Actor, motion: Motion):
        """방향키 두 번 연타로 그쪽으로 짧게 돌진한다. 공중에서는 점프 한 번에 한 번. 출발점에 먼지가 튄다."""
        airborne = (actor.jump_time > 0 or actor.fall_speed > 0 or actor.dash_time > 0
                    or actor.base not in self._ground_heights(actor))
        if not airborne:
            actor.air_jumped = actor.air_dashed = False
        actor.dash_cooldown = max(0.0, actor.dash_cooldown - STEP)
        actor.dash_age += STEP
        if motion.dash and actor.dash_cooldown == 0 and not actor.air_dashed and not motion.stairs:
            vx = motion.horizontal or (0 if motion.dash_up else actor.facing)
            vy = 1 if motion.dash_up else 0
            scale = 0.7071 if vx and vy else 1.0
            actor.dash_vx, actor.dash_vy = vx * scale, vy * scale
            if vx:
                actor.facing = vx
            height = actor.jump_height
            if vy:   # 위로 솟구칠 때는 점프 포물선을 끊고 지금 높이에서 곧장 올라간다 (끝나면 떨어진다)
                actor.base, actor.jump_time, actor.fall_speed = height, 0.0, 0.0
            actor.dash_time, actor.dash_cooldown, actor.dash_age = DASH_TIME, DASH_COOLDOWN, 0.0
            actor.dash_from = actor.dash_to = actor.x
            actor.dash_from_h = actor.dash_to_h = height
            actor.air_dashed = airborne or bool(vy)
            if actor is self.player:
                self.sounds.append('dash')
            if not airborne:   # 땅을 박차고 나갈 때만 먼지가 튄다
                self.boss_effects.append(boss_skills.Effect('heavy-landing', actor.x, actor.floor, -actor.facing,
                                                            scale=0.45, lift=actor.base, life=1.0))
        if actor.dash_time > 0:
            actor.dash_time = max(0.0, actor.dash_time - STEP)
            self._move_x(actor, actor.dash_vx * DASH_SPEED * STEP)
            actor.base += actor.dash_vy * DASH_SPEED * STEP
            actor.dash_to, actor.dash_to_h = actor.x, actor.jump_height

    @staticmethod
    def _near(actor: Actor, point: Point, distance: float) -> bool:
        return (actor.elevator_target is None and actor.jump_time == 0 and actor.web_time == 0 and actor.door_climb_time == 0
                and actor.floor == point.floor and abs(actor.x - point.x) <= distance)

    def _update_doors(self, dt: float):
        actors = [self.player]
        if self.echo is not None:
            actors.append(self.echo.actor)
        occupants = actors + [enemy.actor for enemy in self.enemies]
        for gate, state in zip(self.stage.gates, self.doors):
            state.pressed = any(self._near(actor, gate.plate, PLATE_RANGE) for actor in actors)
            if state.pressed:
                state.grace = DOOR_GRACE
            else:
                state.grace = max(0, state.grace - dt)
            # 닫힐 때 문 안의 캐릭터를 끼우지 않는다.
            occupied = any(
                actor.floor == gate.door.floor and abs(actor.x - gate.door.x) < GATE_HALF_WIDTH + ACTOR_RADIUS
                for actor in occupants
            )
            # Allow a return from behind the first gate without leaving it permanently open.
            returning = (self.index == 0 and gate.label == 'A'
                         and self.player.floor == gate.door.floor
                         and gate.door.x < self.player.x <= gate.door.x + 65)
            state.open = state.latched or state.pressed or state.grace > 0 or returning or (state.open and occupied)

    def _clear_actor_target(self, actor):
        for enemy in self.enemies:
            if enemy.target is actor:
                enemy.target = None
                enemy.windup = 0

    def echo_actors(self):
        actors = []
        if self.recording is not None:
            actors.append(self.recording.preview)
        if self.echo is not None:
            actors.append(self.echo.actor)
        return actors

    def _remove_echo(self):
        if self.echo is None:
            return
        self._clear_actor_target(self.echo.actor)
        self.echo = None
        if not self.sequence_unlocked:
            self.sequence_progress = 0

    def _update_sequence(self, previous_x: float, previous_floor: int):
        sequence = self.stage.sequence
        if sequence is None or self.sequence_unlocked or self.echo is None:
            return
        actor = self.echo.actor
        # 공중에서는 감지 지점을 밟지 않는다. 점프로 순서를 건너뛸 수 있다.
        if (actor.floor != previous_floor or actor.x == previous_x or actor.jump_time > 0
                or actor.web_time > 0 or actor.door_climb_time > 0):
            return
        for index, sensor in enumerate(sequence.sensors):
            if sensor.floor != actor.floor:
                continue
            crossed = (previous_x < sensor.x <= actor.x or previous_x > sensor.x >= actor.x)
            if crossed:
                if index == self.sequence_progress:
                    self.sequence_progress += 1
                    if self.sequence_progress == len(sequence.sensors):
                        self.sequence_unlocked = True
                        self.notify('순서 확인! 보안문이 열렸습니다.')
                else:
                    self.sequence_progress = 1 if index == 0 else 0
                    self.notify('순서가 틀렸습니다. 1번부터 다시 지나가세요.')

    def _update_sync(self):
        """위층 본체 발판과 아래층 분신 발판을 같은 순간에 밟으면 문이 열린 채로 고정된다."""
        gate = self.stage.sync_gate
        if gate is None:
            return
        echo = self.echo.actor if self.echo is not None else None
        self.sync_pressed = (self._near(self.player, gate.player_sensor, PLATE_RANGE),
                             echo is not None and self._near(echo, gate.echo_sensor, PLATE_RANGE))
        if not self.sync_unlocked and all(self.sync_pressed):
            self.sync_unlocked = True
            self.notify('두 발판이 함께 눌렸습니다. 보안문이 열렸습니다.')

    def _update_watch(self):
        """감시등: 분신이 focus 근처에 있으면 분신을 비추고, 아니면 지키는 길을 비춘다."""
        gate = self.stage.watch_gate
        if gate is None:
            return
        echo = self.echo.actor if self.echo is not None else None
        self.watch_active = bool(echo and echo.elevator_target is None and echo.floor == gate.focus.floor
                                 and abs(echo.x - gate.focus.x) <= WATCH_RANGE)
        player = self.player
        if (not self.watch_active and player.elevator_target is None and player.floor == gate.door.floor
                and abs(player.x - gate.door.x) <= gate.zone):
            # 들키면 빛이 닿지 않는 곳까지 밀려난다.
            player.x = gate.door.x - gate.zone - ACTOR_RADIUS - 20
            self.hurt(max(1, round(self.max_health * HAZARD_RATIO)),
                      '감시등에 들켰습니다! 분신을 아래층 감시 구역에 보내 빛을 돌리세요.')

    def _update_bridge(self):
        """거미줄 다리: 거미 분신(재현)이 낭떠러지 위를 지나간 자리 아래에 거미줄이 쳐지고 life초 뒤 끊어진다.
        줄에 매달려 있을 때뿐 아니라 줄을 놓고 날아가거나 뛰는 동안에도 쳐서 본체가 따라 걸어올 길이 끊기지 않게 하고,
        한 프레임에 여러 칸을 지나가면 지나온 칸을 모두 채운다."""
        for tiles in self.bridge_tiles:
            tiles[:] = [max(0.0, remaining - STEP) for remaining in tiles]
        echo = self.echo
        last, self.bridge_last = getattr(self, 'bridge_last', None), None
        if echo is None or echo.monster_kind != 'crawler':
            return
        actor = echo.actor
        self.bridge_last = (actor.floor, actor.x)
        spot = self.bridge_tile_at(actor.floor, actor.x)
        if spot is None:
            return
        index, tile = spot
        first = tile
        if last is not None and last[0] == actor.floor:
            before = self.bridge_tile_at(*last)
            if before is not None and before[0] == index:
                first = before[1]
        life = self.stage.bridges[index].life
        for column in range(min(first, tile), max(first, tile) + 1):
            self.bridge_tiles[index][column] = life

    def _update_ropes(self):
        """거미 밧줄: 재현 중인 거미 분신이 rope 조각상에 줄을 붙인 순간 그 아래로 밧줄이 늘어지고 ROPE_LIFE초 뒤 끊어진다."""
        for rope in self.ropes:
            rope[4] -= STEP
        self.ropes = [rope for rope in self.ropes if rope[4] > 0]
        echo = self.echo
        if echo is None or echo.monster_kind != 'crawler' or echo.actor.web_time != STEP or not echo.actor.web_anchor_beam:
            return
        actor = echo.actor
        for index, beam in enumerate(self.stage.web_beams):
            if beam.rope and beam.floor == actor.floor and beam.left <= actor.web_anchor_x <= beam.right:
                rope = next((rope for rope in self.ropes if rope[5] == index), None)
                if rope is not None:   # 같은 조각상에 다시 붙이면 매달린 본체가 떨어지지 않게 자리는 두고 시간만 늘린다
                    rope[4] = ROPE_LIFE
                    continue
                top = beam.underside - ROPE_TOP
                below = [height for height in self._ground_heights(Actor(actor.web_anchor_x, actor.floor)) if height < top]
                self.ropes.append([actor.floor, actor.web_anchor_x, max(below, default=0.0), top, ROPE_LIFE, index])

    def _gain_xp(self, amount: int):
        level = self.level
        self.xp += amount
        if self.level > level:
            self.health = self.max_health
            self.level_up_time = LEVEL_UP_SECONDS
            self.sounds.append('level_up')
            self.notify(f'레벨 {self.level}! 체력을 모두 회복했습니다.')

    def _update_eggs(self):
        """거미 알: 본체가 닿으면 경험치를 얻는다."""
        player = self.player
        for egg in list(self.eggs):
            x, height, xp = egg
            if abs(player.x - x) <= EGG_REACH and abs(player.jump_height - height) <= 30:
                self.eggs.remove(egg)
                self._gain_xp(xp)

    def _climb(self, actor: Actor, motion: Motion) -> bool:
        """본체의 거미 밧줄 오르기. 줄에 매달려 있으면 True."""
        rope = actor.rope
        if rope is None and motion.stairs > 0:
            height = actor.jump_height
            rope = next((r for r in self.ropes if r[0] == actor.floor and abs(r[1] - actor.x) <= ROPE_GRAB
                         and r[2] - 1 <= height <= r[3]), None)
            if rope is not None:   # ↑: 가까운 줄을 붙잡는다 (뛰는 중에도)
                actor.rope, actor.base, actor.jump_time, actor.fall_speed = rope, height, 0.0, 0.0
        if rope is None:
            return False
        if not any(r is rope for r in self.ropes):   # 줄이 끊어졌다: 그 자리에서 떨어진다
            actor.rope = None
            return False
        actor.x, actor.moving = rope[1], False
        if motion.horizontal:
            actor.facing = motion.horizontal
        if motion.jump:   # 뛰어내린다: 지금 높이에서 보통 점프
            actor.rope = None
            actor.jump_duration, actor.jump_peak, actor.jump_time = self.jump_duration, self.jump_peak, STEP
            self._move_x(actor, motion.horizontal * MOVE_SPEED * STEP)
            if actor is self.player:
                self.sounds.append('jump')
            return True
        actor.base = min(rope[3], max(rope[2], actor.base + motion.stairs * ROPE_CLIMB * STEP))
        if motion.stairs < 0 and actor.base <= rope[2]:
            actor.rope = None   # 바닥까지 내려와 놓는다
        return True

    def _clear_line(self, first: Actor, second: Actor, distance: float) -> bool:
        if first.elevator_target is not None or second.elevator_target is not None:
            return False
        if first.floor != second.floor or abs(first.x - second.x) > distance:
            return False
        if abs(first.jump_height - second.jump_height) > 60:   # 다른 단의 발판이나 높이 뜬 상대
            return False
        left, right = sorted((first.x, second.x))
        return not any(left < wall < right for wall in self._barriers(first.floor))

    def _in_reach(self, enemy: Enemy, reach: float) -> bool:
        """본체의 공격이 적에게 닿는가. 몸 폭(width)이 있는 적(보스)은 그림 크기 상자(폭 × 키)로 본다:
        공격 범위(앞으로 reach, 뒤로 12)가 몸 폭 구간과 겹치고, 본체 높이가 발밑~머리 사이면 맞는다."""
        me, it = self.player, enemy.actor
        kind = ENEMY_KINDS[enemy.spawn.kind]
        if not kind.width:
            return (it.x - me.x) * me.facing >= -12 and self._clear_line(me, it, reach)
        if me.elevator_target is not None or it.elevator_target is not None or me.floor != it.floor:
            return False
        half = kind.width / 2
        low, high = sorted((me.x - me.facing * 12, me.x + me.facing * reach))
        if high < it.x - half or it.x + half < low:
            return False
        if not it.jump_height - 30 <= me.jump_height <= it.jump_height + kind.size:
            return False
        nearest = min(max(me.x, it.x - half), it.x + half)   # 몸에서 본체와 가장 가까운 곳
        left, right = sorted((me.x, nearest))
        return not any(left < wall < right for wall in self._barriers(me.floor))

    def _attack(self, kind='slash'):
        weapon = WEAPONS[self.weapon_index]
        self.attack_kind = kind
        self.attack_duration = 0.28 if kind == 'slash' else 0.24
        self.attack_cooldown = weapon.cooldown
        self.attack_flash = self.attack_duration
        self.attack_age = 0.0
        self.attack_hit_pending = True
        self.sounds.append(kind)   # 'slash' 또는 'thrust'

    def _apply_attack(self):
        weapon = WEAPONS[self.weapon_index]
        reach = round(weapon.reach * (0.8 if self.attack_kind == 'slash' else 1.3))
        damage = max(1, attack_power(self.level) + weapon.bonus + (1 if self.attack_kind == 'slash' else 0))
        for enemy in self.enemies:
            if (not self._in_reach(enemy, reach) or (enemy.broom is not None and enemy.broom < BROOM_MOUNT)
                    or enemy.phase_time > 0):
                continue
            self.hit_sparks.append([enemy.actor.x, enemy.actor.floor, 0.0])
            if enemy.health is None:
                self.notify('이 적은 분신으로 유인하거나 우회하세요.')
            else:
                enemy.health = max(0, enemy.health - damage)
                self.damage_texts.append([enemy.actor.x, enemy.actor.floor, 0.0, str(damage), False])
                enemy.flash = 0.19
                self.sounds.append('hit')
        boss_defeated = any(enemy.health == 0 and enemy.spawn.kind in BOSS_KINDS for enemy in self.enemies)
        if self.stage.isolation and any(enemy.health == 0 and enemy.spawn.kind == 'magic_armor_guard'
                                        for enemy in self.enemies):
            self.isolation_closed = True
        self._gain_xp(sum(ENEMY_KINDS[enemy.spawn.kind].xp for enemy in self.enemies if enemy.health == 0))
        defeated = [enemy for enemy in self.enemies if enemy.health == 0 and enemy.spawn.kind not in BOSS_KINDS]
        if defeated:
            self.sounds.append('monster_die')
        for enemy in defeated:
            self.offer_monster_echo(enemy.spawn.kind)
        self.enemies = [enemy for enemy in self.enemies if enemy.health != 0]
        if boss_defeated:
            self.sounds.append('boss_defeat')
            self.portal_opened_at = self.time
            self.notify('보스를 처치했습니다! 출구에 포털이 열렸습니다.')
        elif self.index in SKY_ROOMS and not self.enemies and self.portal_opened_at is None:
            self.portal_opened_at = self.time
            self.notify('열쇠를 얻었습니다! 가운데에 열린 포털로 돌아가세요.')

    def _update_enemy(self, enemy: Enemy):
        kind = ENEMY_KINDS[enemy.spawn.kind]
        sight = kind.sight
        actor = enemy.actor
        actor.moving = False
        enemy.flash = max(0, enemy.flash - STEP)
        enemy.recovery = max(0, enemy.recovery - STEP)
        left, right = enemy.spawn.patrol
        if enemy.spawn.kind == 'tier_ghost':
            self._update_ghost(enemy, kind)
            return

        def within_chase_area(target):
            return left - ENEMY_CHASE_MARGIN <= target.x <= right + ENEMY_CHASE_MARGIN

        is_boss = enemy.spawn.kind in BOSS_KINDS
        same_floor = actor.floor == self.player.floor
        if is_boss:
            if not same_floor:
                enemy.boss_engaged = False
            elif self._clear_line(actor, self.player, sight):
                if not enemy.boss_appeared:   # 처음 마주친 순간 한 번만 등장 음악
                    enemy.boss_appeared = True
                    self.sounds.append('final_boss' if enemy.spawn.kind == 'echo_knight' else 'boss_appears')
                enemy.boss_engaged = True
        boss_duel = is_boss and same_floor and enemy.boss_engaged
        if boss_duel:
            # 한 번 발견한 본체는 같은 층에서 멀어져도 계속 추적한다.
            enemy.target = self.player
            enemy.last_seen = self.player.x
            enemy.unseen = 0
        elif enemy.target is not None:
            if abs(actor.x - enemy.target.x) > sight + 100 or not within_chase_area(enemy.target):
                enemy.target = None
                enemy.windup = 0
                enemy.unseen = 0
            elif self._clear_line(actor, enemy.target, sight):
                enemy.last_seen = enemy.target.x
                enemy.unseen = 0
            else:
                enemy.unseen += STEP
                if enemy.unseen >= 0.40:
                    enemy.target = None
                    enemy.windup = 0

        if enemy.target is None:
            candidates = [self.player, *self.echo_actors()]
            candidates.sort(key=lambda candidate: abs(candidate.x - actor.x))
            for candidate in candidates:
                if candidate is not None and within_chase_area(candidate) and self._clear_line(actor, candidate, sight):
                    enemy.target = candidate
                    enemy.last_seen = candidate.x
                    enemy.unseen = 0
                    break

        plate = self.taunt_plate()
        if (plate is not None and enemy.spawn.point == self.stage.guard and self.echo is not None
                and self._near(self.echo.actor, plate, PLATE_RANGE)):
            # 도발 발판 위의 분신이 있으면 수호자는 본체 대신 분신을 노린다.
            if enemy.target is not self.echo.actor:
                enemy.windup = 0
            enemy.target = self.echo.actor
            enemy.last_seen = self.echo.actor.x

        if boss_skills.update_phase(self, enemy):
            return
        if (enemy.broom is None and enemy.spawn.kind == 'grand_witch'
                and enemy.health is not None and enemy.health <= enemy.max_health / 2):
            enemy.broom, enemy.skill, enemy.windup, enemy.recovery = 0.0, '', 0, 0
            self.sounds.append('broom')
        flying = enemy.broom is not None
        if flying:
            enemy.broom += STEP
            if enemy.broom < BROOM_MOUNT:
                return
            # 기본 공격 준비 중에는 본체 높이로 급강하하고, 아니면 나는 높이로 떠오른다.
            goal = (max(0, enemy.target.jump_height - 20) if enemy.windup > 0 and enemy.target is not None
                    else BROOM_HEIGHT)
            limit = (BROOM_DIVE if goal < actor.base else BROOM_RISE) * STEP
            actor.base += max(-limit, min(limit, goal - actor.base))

        if boss_skills.update(self, enemy):
            return

        if enemy.windup > 0:
            enemy.windup -= STEP
            if enemy.windup <= 0:
                self.sounds.append('enemy_attack')
                self._enemy_attack(enemy, kind.attack_range)
                enemy.recovery = 0.65
            return

        if enemy.target is not None:
            # 나는 대마녀는 높이가 달라도 바로 위에 오면 급강하 공격을 시작한다.
            in_range = (abs(actor.x - enemy.target.x) <= kind.attack_range and actor.floor == enemy.target.floor
                        if flying else self._clear_line(actor, enemy.target, kind.attack_range))
            if enemy.recovery == 0 and in_range:
                enemy.windup = 0.31
                actor.facing = approach_direction(actor.x, enemy.target.x) or actor.facing
                return
            # 놓친 표적의 마지막 위치를 밟고 서지 않는다. 사다리로 내려온 본체와 겹치지 않게 한다.
            if enemy.recovery == 0 and abs(actor.x - enemy.last_seen) > kind.attack_range:
                self._walk_enemy(actor, enemy.last_seen, kind.speed * (1.6 if flying else 1), floating=flying)
            return

        destination = left if enemy.patrol_direction < 0 else right
        self._walk_enemy(actor, destination, kind.speed * 0.46)
        if abs(actor.x - destination) < 1 or not actor.moving:
            enemy.patrol_direction *= -1

    def _update_ghost(self, enemy: Enemy, kind):
        """층 유령은 표적을 쫓지 않고 자기 높이에서 좌우로 떠다니며, 같은 높이에서 닿으면 피해를 준다."""
        actor = enemy.actor
        left, right = enemy.spawn.patrol
        destination = left if enemy.patrol_direction < 0 else right
        # 위 단일수록 빠르다: 1단 60 → 4단 96
        self._walk_enemy(actor, destination, kind.speed * (1 + actor.base / 180), floating=True)
        if abs(actor.x - destination) < 1 or not actor.moving:
            enemy.patrol_direction *= -1
        for target in (self.player, *self.echo_actors()):
            if (target.floor == actor.floor and target.elevator_target is None
                    and abs(target.x - actor.x) <= kind.attack_range
                    and abs(target.jump_height - actor.base) < 30):
                if target is self.player:
                    self.hurt(self.enemy_damage(enemy), '유령에게 닿았습니다!')
                else:
                    self.hurt_echo(target, self.enemy_damage(enemy))

    def _walk_enemy(self, actor: Actor, destination: float, speed: float, floating=False):
        if self.stage.guard and any(enemy.actor is actor and enemy.spawn.point == self.stage.guard for enemy in self.enemies):
            return
        direction = approach_direction(actor.x, destination)
        if direction:
            actor.facing = direction
            start = actor.x
            self._move_x(actor, direction * min(abs(destination - actor.x), speed * STEP))
            if not floating and self._over_pit(actor.floor, actor.x):
                actor.x, actor.moving = start, False   # 땅을 걷는 적은 구덩이 앞에서 멈춘다

    def hurt(self, amount: int, message: str) -> bool:
        """본체가 피해를 한 번 입는다. 무적 시간 중이면 False."""
        if self.god or self.invulnerable > 0 or self.player.dash_time > 0:
            return False
        self.health = max(0, self.health - amount)
        self.invulnerable = 0.92
        self.sounds.append('hurt')
        self.damage_texts.append([self.player.x, self.player.floor, 0.0, f'-{amount}', True])
        if self.health == 0:   # 맞을 때마다 띄우지 않고, 쓰러졌을 때만 무엇에 당했는지 알려 준다
            self.notify(message)
            self.result = 'defeated'
        return True

    def enemy_damage(self, enemy: Enemy) -> int:
        kind = ENEMY_KINDS[enemy.spawn.kind]
        if kind.damage_ratio:
            return max(1, round(self.max_health * kind.damage_ratio))
        return round(kind.damage * self.stage.enemy_scale)

    def hurt_echo(self, actor: Actor, amount: int) -> bool:
        if self.god or not any(actor is echo for echo in self.echo_actors()) or self.echo_invulnerable > 0:
            return False
        damage = max(1, round(amount * ECHO_DAMAGE_RATIO))
        self.echo_invulnerable = ECHO_INVULNERABILITY
        self.sounds.append('hurt')
        self.health = max(0, self.health - damage)
        self.damage_texts.append([actor.x, actor.floor, 0.0, f'-{damage}', True])
        if self.health == 0:
            self.result = 'defeated'
        return True

    def _enemy_attack(self, enemy: Enemy, distance: int):
        target = enemy.target
        if target is None or not self._clear_line(enemy.actor, target, distance + 8):
            return
        if target is self.player:
            self.hurt(self.enemy_damage(enemy), '피격! 필요하면 R로 스테이지를 다시 시작하세요.')
        elif any(target is actor for actor in self.echo_actors()):
            if self.stage.guard and enemy.spawn.point == self.stage.guard:
                self.guard_open_time = 4.0 if self.stage.elevators else 1.1
            self.hurt_echo(target, self.enemy_damage(enemy))
