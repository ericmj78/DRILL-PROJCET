from dataclasses import dataclass, field, replace
from math import asin, atan2, cos, hypot, pi, sin
import random

import boss_skills
from stages import HAZARD_RATIO, LEVEL_UP_XP, attack_power, max_health

WATCH_RANGE = 170   # 분신이 감시등의 focus에서 이만큼 안에 있으면 빛이 분신을 따라간다.
TAUNT_OFFSET = 35   # 수호자 앞 도발 발판까지의 거리
LIGHT_BELOW = 100   # 위층 분신의 빛이 아래층을 비추는 반폭
from stages import (
    ACTOR_RADIUS, BOSS_KINDS, DOOR_GRACE, ENEMY_KINDS,
    GATE_HALF_WIDTH, LEFT, MOVE_SPEED,
    PLATE_RANGE, RIGHT, STAIR_RANGE, STAGES, STEP, WEAPONS, EnemySpawn, Point,
)

JUMP_DURATION = 0.64
JUMP_HEIGHT = 48  # 49를 넘으면 슈퍼 점프(100)가 보통 점프의 두 배가 안 된다
BEAST_JUMP_DURATION = 1.0
BEAST_JUMP_HEIGHT = 100
BEAST_CHARGE_SECONDS = 1.0
# 하늘 섬: 좌우로 아무 곳이나 정해 떠다니고, 마법책 분신이 놓은 섬은 SKY_PIN초 멈췄다가 다시 떠다닌다.
SKY_SPEED = (60.0, 110.0)  # px/s
SKY_WALL_BIAS = 300        # 목표를 맵 밖까지 뽑고 벽에서 자른다: 벽 턱 옆에 섬이 더 자주 머문다
SKY_PIN = 15.0
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


def approach_direction(start: float, end: float) -> int:
    return (end > start) - (end < start)


class World:
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
        sky = self.stage.sky
        self.sky_blocks = [list(block) for block in sky.blocks] if sky else []   # 하늘 땅 [x, 높이]
        self.sky_progress = 0      # 순서대로 눌린 하늘 스위치 수
        self.sky_on = None         # 본체가 지금 밟고 있는 하늘 스위치 (한 번 밟을 때 한 번만 판정)
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
        self.confused = 0.0     # 낙석에 맞아 기절한 남은 시간. 머리 위에 혼란(pixelfx status/confused)이 돈다
        self.level_up_time = 0.0  # 레벨 업 이펙트가 남은 시간
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
        bridge = self.stage.bridge
        self.bridge_tiles = [0.0] * (-(-(bridge.right - bridge.left) // bridge.tile)) if bridge else []
        self._update_doors(0)

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
            self.notify('마우스로 분신 둘레의 하늘 땅을 끌어 길을 만드세요.' if self._sky_book()
                        else 'F를 누르고 있다가 떼면 물약을 던집니다. 두 병이 포털 한 쌍이 됩니다.'
                        if monster_kind == 'potion_slime'
                        else '분신으로 이동하고 필요한 자리에서 기다리세요.')

    @property
    def pending_monster_echo(self):
        return self.pending_monster_echoes[0] if self.pending_monster_echoes else None

    def offer_monster_echo(self, kind):
        if kind in BOSS_KINDS or kind == 'tier_ghost':
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
            self.notify('녹화를 취소했습니다.')

    def _finish_recording(self, time_limit: bool = False):
        record = self.recording
        self.recording = None
        if record is not None:
            self._clear_actor_target(record.preview)
        if record is None or not record.inputs:
            self.notify('분신이 재현할 녹화가 비어 있어요.')
            return
        self._remove_echo()
        actor = Actor.at(record.start, record.facing)
        actor.base = record.base   # 섬이 떠나 버렸으면 그 자리에서 떨어진다
        self.echo = Echo(actor, tuple(record.inputs), monster_kind=record.monster_kind, clock=record.clock)
        self._update_doors(0)
        self.notify('녹화 상한에 도달해 재현을 시작합니다.' if time_limit else '본체 조작 재개 · 분신이 재현합니다.')

    def step(self, motion: Motion = Motion(), attack: str | bool = False):
        if self.result != 'playing' or self.echo_selecting or self.pending_monster_echo:
            return
        self.message_time = max(0, self.message_time - STEP)
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
            # 낙석에 맞아 기절한 동안은 입력을 받지 않는다 (하던 점프·낙하는 이어진다).
            self._move(self.player, Motion() if self.confused > 0 else motion)
            self._block_body(player_x, player_floor)
        elif recording is not None:
            self.player.moving = False
        boss_skills.update_gravity(self, motion.horizontal if recording is None else 0)
        if self.result != 'playing':
            return
        for floor, left, right in self.stage.poison_zones:
            if (self.player.floor == floor and left <= self.player.x <= right
                    and self.player.elevator_target is None and self.player.jump_height < 12):
                self.hurt(max(1, round(self.max_health * HAZARD_RATIO)), '독에 닿았습니다!')
            for actor in self.echo_actors():
                if (actor.floor == floor and left <= actor.x <= right
                        and actor.elevator_target is None and actor.jump_height < 12):
                    self.hurt_echo(actor, max(1, round(self.max_health * HAZARD_RATIO)))
        for hazard in self.stage.hidden_hazards:
            # 분신의 빛이 닿지 않은 함정은 뛰어넘을 수도 없다. 무작정 점프로는 통과하지 못한다.
            airborne = self.player.jump_time > 0 and self.hazard_lit(hazard)
            if not airborne and self.player.floor == hazard.floor and abs(self.player.x - hazard.x) <= 18:
                # 맞으면서 밀고 지나갈 수 없도록 온 방향으로 튕겨 낸다. 점프로만 넘는다.
                self._move_x(self.player, 70 if player_x > hazard.x else -70)
                self.hurt(max(1, round(self.max_health * HAZARD_RATIO)),
                          '숨겨진 함정입니다! 분신 곁에서 위치를 보고 뛰어넘으세요.')
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
                self.notify('분신의 재현이 끝났습니다.')

        self._update_reveal()
        self._update_switches()
        self._update_sky()
        self._update_potions()
        self._update_portals()
        if self.player.base < -PIT_DEPTH:
            self.invulnerable = 0
            self.hurt(self.health, '구덩이에 떨어졌습니다!')
            return
        if self.recording is not None and self.recording.preview.base < -PIT_DEPTH:
            self.cancel_recording()
            self.notify('분신이 구덩이에 떨어졌습니다.')
        if self.echo is not None and self.echo.actor.base < -PIT_DEPTH:
            self._remove_echo()
            self.notify('분신이 구덩이에 떨어졌습니다.')

        self._update_sync()
        self._update_bridge()
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
        if self._near(self.player, self.stage.exit, 27):
            if any(enemy.spawn.kind in BOSS_KINDS for enemy in self.enemies):
                if self.message_time <= 0:
                    self.notify('보스를 처치하면 출구가 열립니다.')
            elif self.stage.sky and self.sky_progress < len(self.stage.sky.switches):
                # 벽 문은 높이 125 위로 넘을 수 있어 하늘 땅 계단으로 넘지 못하게 출구 자체를 잠근다.
                if self.message_time <= 0:
                    self.notify('1→2→3 스위치를 순서대로 밟아야 출구가 열립니다.')
            elif not self.portal_open:
                pass   # 포탈 스위치를 누르기 전엔 출구 자리가 비어 있다
            else:
                self.result = 'cleared'

    @property
    def portal_open(self) -> bool:
        """문 없는 스위치(출구 포탈 스위치)가 모두 눌렸는가. 그런 스위치가 없으면 늘 열려 있다."""
        return all(on for switch, on in zip(self.stage.switches, self.switched) if switch.door is None)

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
        if entries:
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

    def bridge_tile_at(self, x: float) -> int | None:
        bridge = self.stage.bridge
        if bridge is None or not bridge.left < x < bridge.right:
            return None
        return min(len(self.bridge_tiles) - 1, int((x - bridge.left) // bridge.tile))

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
                ceiling = 365
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
        shift = platform.shift(self.platform_clock() if clock is None else clock)
        return platform.left + shift, platform.right + shift

    def _ride(self, actor: Actor):
        """움직이는 발판 위에 서 있으면 발판과 함께 옮겨 간다."""
        if actor.jump_time > 0 or actor.fall_speed or actor.base <= 0 or actor.web_time > 0:
            return
        clock = self.platform_clock()
        for index, platform in enumerate(self.stage.platforms):
            if (platform.swing and platform.floor == actor.floor and platform.height == actor.base
                    and self.platform_visible(index)):
                left, right = self.platform_span(index, clock - STEP)
                if left <= actor.x <= right:
                    actor.x += platform.shift(clock) - platform.shift(clock - STEP)
                    return

    def _over_pit(self, floor: int, x: float) -> bool:
        return any(pit_floor == floor and left < x < right for pit_floor, left, right in self.stage.pits)

    def _ground_heights(self, actor: Actor):
        """actor가 지금 x에서 설 수 있는 높이들. 구덩이 밖 바닥(0)과 보이는 발판."""
        if not self._over_pit(actor.floor, actor.x):
            yield 0.0
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

    def _end_jump(self, actor: Actor):
        """점프 포물선이 끝났다. 발판에서 뛰어 디딜 곳이 없으면 포물선 끝의 내려오던 속도로 이어서 떨어진다
        (0부터 다시 떨어지면 공중에서 멈칫한다)."""
        actor.jump_time = 0.0
        if actor.base not in self._ground_heights(actor):
            actor.fall_speed = 4 * actor.jump_peak / actor.jump_duration

    def _settle(self, actor: Actor, before: float):
        """발판 착지와 낙하. 점프가 내려오다 발판 높이를 지나면 그 위에 선다."""
        if (not self.stage.pits and not self.stage.platforms and not self.stage.sky) or actor.elevator_target is not None \
                or actor.web_time > 0 or actor.door_climb_time > 0:
            return
        if actor.jump_time > 0:
            now = actor.jump_height
            landing = [height for height in self._ground_heights(actor) if now <= height <= before]
            if now < before and landing:
                actor.base, actor.jump_time, actor.beast_super_jump = max(landing), 0.0, False
            return
        if actor.fall_speed == 0 and actor.base in self._ground_heights(actor):
            return
        actor.fall_speed += FALL_GRAVITY * STEP
        below = actor.base - actor.fall_speed * STEP
        landing = [height for height in self._ground_heights(actor) if below <= height <= actor.base]
        if landing:
            actor.base, actor.fall_speed = max(landing), 0.0
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
                self.notify('발판이 다시 사라졌습니다!')
        lens = self.stage.lens
        for actor in watchers:
            if not actor.radar or actor.elevator_target is not None:
                continue
            eye = actor.jump_height + RADAR_EYE
            lit = (lens is not None and lens.floor == actor.floor
                   and hypot(lens.x - actor.x, lens.height - eye) <= RADAR_RANGE)
            if lit and not self.lens_lit:
                self.lens_lit = True
                self.notify('렌즈가 빛을 퍼뜨려 숨은 발판이 모두 드러났습니다!')
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
        """마우스를 누른 자리의 하늘 땅을 잡는다. 분신 둘레 reach 안의 땅만 잡힌다."""
        book = self._sky_book()
        if book is None:
            return False
        sky = self.stage.sky
        center = (book.x, book.jump_height + 30)
        hit = [index for index, (bx, bh) in enumerate(self.sky_blocks)
               if abs(x - bx) <= sky.width / 2 + 10 and abs(height - bh) <= 24]
        near = [index for index in hit if index not in sky.fixed
                and hypot(self.sky_blocks[index][0] - center[0], self.sky_blocks[index][1] - center[1]) <= sky.reach]
        if not near:
            if any(index in sky.fixed for index in hit):
                self.notify('이 땅에는 염력이 통하지 않습니다.')
            elif hit:
                self.notify('염력이 닿지 않습니다. 분신을 땅 가까이 데려가세요.')
            return False
        self.sky_hold = min(near, key=lambda index: abs(x - self.sky_blocks[index][0]))
        self.sky_drag(x, height)
        return True

    def sky_drag(self, x: float, height: float):
        self.sky_target = (x, height)
        book = self._sky_book()
        if self.sky_hold is not None and book is not None:
            self.sky_blocks[self.sky_hold] = list(self._sky_clamp(book, x, height))

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
            self.sky_drag(*self.sky_target)   # 분신이 걸어가면 잡은 땅도 끌려온다
        self._drift_sky()
        player = self.player
        on = None
        if player.elevator_target is None and player.jump_time == 0 and player.fall_speed == 0:
            on = next((index for index, (x, height) in enumerate(sky.switches)
                       if player.floor == 0 and abs(player.base - height) < 1
                       and abs(player.x - x) <= PLATE_RANGE), None)
        if on is not None and on != self.sky_on and self.sky_progress < len(sky.switches):
            if on == self.sky_progress:
                self.sky_progress += 1
                self.notify('하늘 문이 열렸습니다!' if self.sky_progress == len(sky.switches)
                            else f'{on + 1}번 스위치가 켜졌습니다.')
            elif on > self.sky_progress:
                self.sky_progress = 0
                self.sky_blocks = [list(block) for block in sky.blocks]
                self.sky_hold = None
                self.sky_pin = [0.0] * len(self.sky_blocks)
                self.notify('순서가 틀렸습니다! 스위치와 하늘 땅이 처음으로 돌아갑니다.')
        self.sky_on = on

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
                self.notify('물약이 깨졌습니다.')
                continue
            landing = self._potion_landing(floor, nx, height, nh) if vh < 0 else None
            if landing is None:
                flying.append([nx, floor, nh, vx, vh])
                continue
            self.portals[self.portal_next] = (floor, *landing)
            self.portal_next = 1 - self.portal_next
            self.portal_lock = True   # 발밑에 생긴 포털로 바로 빨려 들어가지 않게
            self.notify('포털이 이어졌습니다!' if all(self.portals) else '포털 한쪽이 열렸습니다. 한 병 더 던지세요.')
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
        self.notify('포털을 지나왔습니다.')

    def _move(self, actor: Actor, motion: Motion, monster_kind=None):
        self._ride(actor)
        before = actor.jump_height
        self._move_body(actor, motion, monster_kind)
        self._settle(actor, before)

    def _move_body(self, actor: Actor, motion: Motion, monster_kind=None):
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
                self.notify('거미줄이 닿는 벽이나 천장이 없습니다.')
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
        if (motion.jump and actor.jump_time == 0 and actor.fall_speed == 0
                and not motion.stairs and monster_kind != 'beast'):
            actor.jump_duration = JUMP_DURATION
            actor.jump_peak = JUMP_HEIGHT
            actor.jump_time = STEP
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
        """낭떠러지: 분신(재현) 발밑에 빛 발판이 생기고 life초 뒤 사라진다. 발판 없는 곳의 본체는 떨어진다."""
        bridge = self.stage.bridge
        if bridge is None:
            return
        self.bridge_tiles = [max(0.0, remaining - STEP) for remaining in self.bridge_tiles]
        echo = self.echo.actor if self.echo is not None else None
        if echo is not None and echo.floor == bridge.floor and echo.elevator_target is None:
            tile = self.bridge_tile_at(echo.x)
            if tile is not None:
                self.bridge_tiles[tile] = bridge.life
        player = self.player
        if player.floor != bridge.floor or player.elevator_target is not None or player.jump_time > 0:
            return
        tile = self.bridge_tile_at(player.x)
        if tile is not None and self.bridge_tiles[tile] <= 0:
            player.x = bridge.left - ACTOR_RADIUS - 10
            player.facing = 1
            self.invulnerable = 0
            self.hurt(max(1, round(self.max_health * HAZARD_RATIO)),
                      '낭떠러지에 떨어졌습니다! 분신이 지나간 빛 발판만 밟으세요.')

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

    def _apply_attack(self):
        weapon = WEAPONS[self.weapon_index]
        reach = round(weapon.reach * (0.8 if self.attack_kind == 'slash' else 1.3))
        damage = max(1, attack_power(self.level) + weapon.bonus + (1 if self.attack_kind == 'slash' else 0))
        for enemy in self.enemies:
            if not self._in_reach(enemy, reach):
                continue
            self.hit_sparks.append([enemy.actor.x, enemy.actor.floor, 0.0])
            if enemy.health is None:
                self.notify('이 적은 분신으로 유인하거나 우회하세요.')
            else:
                enemy.health = max(0, enemy.health - damage)
                self.damage_texts.append([enemy.actor.x, enemy.actor.floor, 0.0, str(damage), False])
                enemy.flash = 0.19
        boss_defeated = any(enemy.health == 0 and enemy.spawn.kind in BOSS_KINDS for enemy in self.enemies)
        if self.stage.isolation and any(enemy.health == 0 and enemy.spawn.kind == 'magic_armor_guard'
                                        for enemy in self.enemies):
            self.isolation_closed = True
        level = self.level
        self.xp += sum(ENEMY_KINDS[enemy.spawn.kind].xp for enemy in self.enemies if enemy.health == 0)
        if self.level > level:
            self.health = self.max_health
            self.level_up_time = LEVEL_UP_SECONDS
            self.notify(f'레벨 {self.level}! 체력을 모두 회복했습니다.')
        defeated = [enemy for enemy in self.enemies if enemy.health == 0 and enemy.spawn.kind not in BOSS_KINDS]
        for enemy in defeated:
            self.offer_monster_echo(enemy.spawn.kind)
        self.enemies = [enemy for enemy in self.enemies if enemy.health != 0]
        if boss_defeated:
            self.notify('보스를 처치했습니다! 출구로 이동하세요.')

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

        if boss_skills.update(self, enemy):
            return

        if enemy.windup > 0:
            enemy.windup -= STEP
            if enemy.windup <= 0:
                self._enemy_attack(enemy, kind.attack_range)
                enemy.recovery = 0.65
            return

        if enemy.target is not None:
            if enemy.recovery == 0 and self._clear_line(actor, enemy.target, kind.attack_range):
                enemy.windup = 0.31
                actor.facing = approach_direction(actor.x, enemy.target.x) or actor.facing
                return
            # 놓친 표적의 마지막 위치를 밟고 서지 않는다. 사다리로 내려온 본체와 겹치지 않게 한다.
            if enemy.recovery == 0 and abs(actor.x - enemy.last_seen) > kind.attack_range:
                self._walk_enemy(actor, enemy.last_seen, kind.speed)
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
        if self.invulnerable > 0:
            return False
        self.health = max(0, self.health - amount)
        self.invulnerable = 0.92
        self.damage_texts.append([self.player.x, self.player.floor, 0.0, f'-{amount}', True])
        self.notify(message)
        if self.health == 0:
            self.result = 'defeated'
        return True

    def enemy_damage(self, enemy: Enemy) -> int:
        kind = ENEMY_KINDS[enemy.spawn.kind]
        if kind.damage_ratio:
            return max(1, round(self.max_health * kind.damage_ratio))
        return round(kind.damage * self.stage.enemy_scale)

    def hurt_echo(self, actor: Actor, amount: int) -> bool:
        if not any(actor is echo for echo in self.echo_actors()) or self.echo_invulnerable > 0:
            return False
        damage = max(1, round(amount * ECHO_DAMAGE_RATIO))
        self.echo_invulnerable = ECHO_INVULNERABILITY
        self.health = max(0, self.health - damage)
        self.damage_texts.append([actor.x, actor.floor, 0.0, f'-{damage}', True])
        self.notify(f'분신이 피격되어 본체 체력이 {damage} 감소했습니다.')
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
