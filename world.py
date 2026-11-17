from dataclasses import dataclass, field
from math import pi, sin

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
JUMP_HEIGHT = 42
ELEVATOR_DURATION = 0.8
ENEMY_CHASE_MARGIN = 400
ECHO_DAMAGE_RATIO = 0.30
ECHO_INVULNERABILITY = 0.92
SPIDER_WEB_DURATION = 1.0
SPIDER_WEB_DISTANCE = 220
SPIDER_WEB_HEIGHT = 100
SPIDER_DOOR_CLIMB_DURATION = 1.2
SPIDER_DOOR_CLIMB_HEIGHT = 145


@dataclass
class Actor:
    x: float
    floor: int
    facing: int = 1
    moving: bool = False
    walk_distance: float = 0
    jump_time: float = 0.0
    elevator_target: int | None = None
    elevator_time: float = 0.0
    web_time: float = 0.0
    web_start_x: float = 0.0
    web_anchor_x: float = 0.0
    web_direction: int = 1
    door_climb_time: float = 0.0
    door_climb_x: float = 0.0
    door_climb_start: float = 0.0
    door_climb_end: float = 0.0
    spider_up_latched: bool = False

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
            return SPIDER_WEB_HEIGHT * sin(pi * min(1.0, self.web_time / SPIDER_WEB_DURATION))
        if self.jump_time <= 0:
            return 0.0
        progress = min(1.0, self.jump_time / JUMP_DURATION)
        return 4 * JUMP_HEIGHT * progress * (1 - progress)

    @classmethod
    def at(cls, point: Point, facing: int = 1):
        return cls(point.x, point.floor, facing)


@dataclass(frozen=True)
class Motion:
    horizontal: int = 0
    stairs: int = 0
    jump: bool = False
    web: bool = False


@dataclass
class Recording:
    start: Point
    facing: int
    preview: Actor
    inputs: list[Motion] = field(default_factory=list)
    monster_kind: str | None = None


@dataclass
class Echo:
    actor: Actor
    inputs: tuple[Motion, ...]
    cursor: int = 0
    monster_kind: str | None = None


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
        self.lift_progress = 0.0
        self.lift_riding = False
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
        if self.recording is None and self.player.elevator_target is not None:
            self.notify('승강기가 멈춘 뒤 분신 녹화를 시작하세요.')
            return
        if self.recording is None and self.player.jump_time > 0:
            self.notify('착지한 뒤 분신 녹화를 시작하세요.')
            return
        if self.lift_riding:
            self.notify('발판이 멈춘 뒤 녹화하세요.')
            return
        if self.recording is None:
            self.start_recording()
        else:
            self._finish_recording()

    def start_recording(self, monster_kind: str | None = None):
        self.echo_selecting = False
        if self.recording is None:
            start = Point(self.player.x, self.player.floor)
            facing = self.player.facing
            self.recording = Recording(start, facing, Actor.at(start, facing), monster_kind=monster_kind)
            self.notify('분신으로 이동하고 필요한 자리에서 기다리세요.')

    @property
    def pending_monster_echo(self):
        return self.pending_monster_echoes[0] if self.pending_monster_echoes else None

    def offer_monster_echo(self, kind):
        if kind in BOSS_KINDS:
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
        self.echo = Echo(Actor.at(record.start, record.facing), tuple(record.inputs), monster_kind=record.monster_kind)
        self._update_doors(0)
        self.notify('녹화 상한에 도달해 재현을 시작합니다.' if time_limit else '본체 조작 재개 · 분신이 재현합니다.')

    def step(self, motion: Motion = Motion(), attack: str | bool = False):
        if self.result != 'playing' or self.echo_selecting or self.pending_monster_echo:
            return
        self.message_time = max(0, self.message_time - STEP)
        recording = self.recording
        if recording is not None:
            self._move(self.recording.preview, motion, self.recording.monster_kind)
            self.recording.inputs.append(motion)

        self.time += STEP
        self.guard_open_time = max(0, self.guard_open_time - STEP)
        self.invulnerable = max(0, self.invulnerable - STEP)
        self.echo_invulnerable = max(0, self.echo_invulnerable - STEP)
        self.attack_cooldown = max(0, self.attack_cooldown - STEP)
        self.attack_flash = max(0, self.attack_flash - STEP)
        self.attack_age += STEP
        self.shake = max(0, self.shake - STEP)
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
        if recording is None and not self.lift_riding and not (self.gravity_field and self.gravity_field.captured):
            self._move(self.player, motion)
            self._block_body(player_x, player_floor)
        elif recording is not None:
            self.player.moving = False
        boss_skills.update_gravity(self, motion.horizontal if recording is None else 0)
        if self.result != 'playing':
            return
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
        if recording is None and attack and self.attack_cooldown == 0:
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

        self._update_sync()
        self._update_bridge()
        if self.result != 'playing':
            return
        self._update_lift()
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
            else:
                self.result = 'cleared'

    def warp_to_boss(self):
        """본체를 보스가 있는 층의 입구(그 층으로 올라오는 사다리·승강기)로 옮긴다. B 키용."""
        boss = next(enemy for enemy in self.enemies if enemy.spawn.kind in BOSS_KINDS)
        floor = boss.actor.floor
        entries = [stair.x for stair in self.stage.stairs + self.stage.elevators if stair.lower == floor - 1]
        self.player.x = entries[0] if entries else boss.actor.x - 400
        self.player.floor = floor

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
        if guard is None or self.index == 2:
            return None
        return Point(guard.x - TAUNT_OFFSET, guard.floor)

    def bridge_tile_at(self, x: float) -> int | None:
        bridge = self.stage.bridge
        if bridge is None or not bridge.left < x < bridge.right:
            return None
        return min(len(self.bridge_tiles) - 1, int((x - bridge.left) // bridge.tile))

    def _block_body(self, x: float, floor: int):
        # 처치 불가 적은 본체가 몸으로 지나갈 수 없다. 분신으로 유인하거나 다른 층으로 돌아간다.
        if self.index == 2 or self.player.floor != floor:
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
        if (self.index != 2 and self.stage.guard and self.stage.guard.floor == floor
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

    def _move_x(self, actor: Actor, amount: float, ignore_barrier=None):
        start = actor.x
        target = min(RIGHT, max(LEFT, start + amount))
        margin = GATE_HALF_WIDTH + ACTOR_RADIUS
        for wall in self._barriers(actor.floor):
            if ignore_barrier is not None and abs(wall - ignore_barrier) < 0.01:
                continue
            if start <= wall - margin and target > wall - margin:
                target = wall - margin
            elif start >= wall + margin and target < wall + margin:
                target = wall + margin
        actor.x = target
        distance = abs(target - start)
        actor.moving = distance > 0.001
        actor.walk_distance += distance

    def _move(self, actor: Actor, motion: Motion, monster_kind=None):
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
            if motion.web and actor.web_time == 0 and actor.jump_time == 0:
                actor.web_time = STEP
                actor.web_start_x = actor.x
                actor.web_direction = actor.facing
                actor.web_anchor_x = max(LEFT, min(RIGHT, actor.x + actor.facing * SPIDER_WEB_DISTANCE * 0.5))
            if actor.web_time > 0:
                progress = min(1.0, actor.web_time / SPIDER_WEB_DURATION)
                target = actor.web_start_x + actor.web_direction * SPIDER_WEB_DISTANCE * progress
                self._move_x(actor, target - actor.x)
                actor.web_time = actor.web_time + STEP if progress < 1 else 0.0
                return
            if motion.stairs > 0 and not actor.spider_up_latched and actor.jump_time == 0:
                margin = GATE_HALF_WIDTH + ACTOR_RADIUS
                for gate, state in zip(self.stage.gates, self.doors):
                    if (not state.open and gate.door.floor == actor.floor
                            and abs(actor.x - gate.door.x) <= margin + 18):
                        side = -1 if actor.x < gate.door.x else 1
                        actor.door_climb_time = STEP
                        actor.door_climb_x = gate.door.x
                        actor.door_climb_start = actor.x
                        actor.door_climb_end = gate.door.x - side * (margin + 4)
                        actor.facing = -side
                        actor.spider_up_latched = True
                        return
        if motion.horizontal:
            actor.facing = motion.horizontal
        if motion.jump and actor.jump_time == 0 and not motion.stairs:
            actor.jump_time = STEP
        elif actor.jump_time > 0:
            actor.jump_time += STEP
            if actor.jump_time >= JUMP_DURATION:
                actor.jump_time = 0.0
        self._move_x(actor, motion.horizontal * MOVE_SPEED * STEP)
        if motion.stairs and actor.jump_time == 0:
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
            if (monster_kind == 'crawler' and not (motion.stairs > 0 and actor.spider_up_latched)
                    and 0 <= actor.floor + motion.stairs < self.stage.floors):
                # The dungeon background is a continuous climbable wall.
                actor.elevator_target = actor.floor + motion.stairs
                actor.elevator_time = 0.0
                actor.moving = False

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

    def _update_lift(self):
        lift = self.stage.lift
        if lift is None:
            return
        weighted = self.echo is not None and self._near(self.echo.actor, lift.weight, 22)
        if not self.lift_riding and weighted and self._near(self.player, lift.platform, 18):
            self.lift_riding = True
            self.player.x = lift.platform.x
            self.player.moving = False
        if not self.lift_riding:
            return
        self.lift_progress = max(0, min(1, self.lift_progress + (STEP if weighted else -STEP)))
        if self.lift_progress >= 1:
            self.player.floor = lift.platform.floor + 1
            self.lift_riding = False
            self.lift_progress = 0
            self.notify('균형 발판이 위층에 도착했습니다.')
        elif self.lift_progress <= 0 and not weighted:
            self.lift_riding = False
            self.notify('분신이 사라져 발판이 내려왔습니다.')

    def _clear_line(self, first: Actor, second: Actor, distance: float) -> bool:
        if first.elevator_target is not None or second.elevator_target is not None:
            return False
        if first.floor != second.floor or abs(first.x - second.x) > distance:
            return False
        left, right = sorted((first.x, second.x))
        return not any(left < wall < right for wall in self._barriers(first.floor))

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
            offset = enemy.actor.x - self.player.x
            if offset * self.player.facing < -12 or not self._clear_line(self.player, enemy.actor, reach):
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

    def _walk_enemy(self, actor: Actor, destination: float, speed: float):
        if self.stage.guard and any(enemy.actor is actor and enemy.spawn.point == self.stage.guard for enemy in self.enemies):
            return
        direction = approach_direction(actor.x, destination)
        if direction:
            actor.facing = direction
            self._move_x(actor, direction * min(abs(destination - actor.x), speed * STEP))

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
