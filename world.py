from dataclasses import dataclass, field

from stages import (
    ACTOR_RADIUS, BOSS_KINDS, DOOR_GRACE, ENEMY_KINDS,
    GATE_HALF_WIDTH, LEFT, MAX_HEALTH, MOVE_SPEED,
    PLATE_RANGE, RIGHT, STAIR_RANGE, STAGES, STEP, WEAPONS, EnemySpawn, Point,
)

JUMP_DURATION = 0.64
JUMP_HEIGHT = 42
ELEVATOR_DURATION = 0.8
ENEMY_CHASE_MARGIN = 400


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

    @property
    def elevator_offset(self):
        if self.elevator_target is None:
            return 0.0
        return (self.elevator_target - self.floor) * min(1.0, self.elevator_time / ELEVATOR_DURATION)

    @property
    def jump_height(self):
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


@dataclass
class Recording:
    start: Point
    facing: int
    preview: Actor
    inputs: list[Motion] = field(default_factory=list)


@dataclass
class Echo:
    actor: Actor
    inputs: tuple[Motion, ...]
    cursor: int = 0


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
    patrol_direction: int = -1
    target: Actor | None = None
    last_seen: float = 0
    unseen: float = 0
    windup: float = 0
    recovery: float = 0
    flash: float = 0


def approach_direction(start: float, end: float) -> int:
    return (end > start) - (end < start)


class World:
    def __init__(self, index: int = 0, weapon_index: int = 2):
        self.index = index
        self.stage = STAGES[index]
        self.player = Actor.at(self.stage.start)
        self.echo: Echo | None = None
        self.recording: Recording | None = None
        self.doors = [DoorState() for gate in self.stage.gates]
        self.enemies = [
            Enemy(spawn, Actor.at(spawn.point, -1), ENEMY_KINDS[spawn.kind].health)
            for spawn in self.stage.enemies
        ]
        self.health = MAX_HEALTH
        self.weapon_index = weapon_index
        self.invulnerable = 0.0
        self.attack_cooldown = 0.0
        self.attack_flash = 0.0
        self.attack_kind = 'slash'
        self.attack_duration = 0.28
        self.attack_hit_pending = False
        self.time = 0.0
        self.result = 'playing'
        self.message = ''
        self.message_time = 0.0
        self.sequence_progress = 0
        self.sequence_unlocked = False
        self.sync_unlocked = False
        self.sync_player_time = None
        self.sync_echo_time = None
        self.guard_open_time = 0.0
        self.watch_active = False
        self.isolation_closed = False
        self.bridge_timers = [0.0 for _ in self.stage.bridge.points] if self.stage.bridge else []
        self.lift_progress = 0.0
        self.lift_riding = False
        self._update_doors(0)

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
                self.notify('격리실 문을 열었습니다.')
            elif any(enemy.spawn.kind == 'magic_armor_guard' and enemy.actor.floor == room.door.floor and enemy.actor.x >= room.inside_x for enemy in self.enemies):
                self.isolation_closed = True
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
            start = Point(self.player.x, self.player.floor)
            facing = self.player.facing
            self.recording = Recording(start, facing, Actor.at(start, facing))
            self.notify('분신으로 이동하고 필요한 자리에서 기다리세요.')
        else:
            self._finish_recording()

    def cancel_recording(self):
        if self.recording is not None:
            self.recording = None
            self.notify('녹화를 취소했습니다.')

    def _finish_recording(self, time_limit: bool = False):
        record = self.recording
        self.recording = None
        if record is None or not record.inputs:
            self.notify('분신이 재현할 녹화가 비어 있어요.')
            return
        self._remove_echo()
        self.echo = Echo(Actor.at(record.start, record.facing), tuple(record.inputs))
        self._update_doors(0)
        self.notify('녹화 상한에 도달해 재현을 시작합니다.' if time_limit else '본체 조작 재개 · 분신이 재현합니다.')

    def step(self, motion: Motion = Motion(), attack: str | bool = False):
        if self.result != 'playing':
            return
        self.message_time = max(0, self.message_time - STEP)
        if self.recording is not None:
            self._move(self.recording.preview, motion)
            self.recording.inputs.append(motion)
            if len(self.recording.inputs) >= round(self.stage.echo_seconds / STEP):
                self._finish_recording(time_limit=True)
            return

        self.time += STEP
        self.guard_open_time = max(0, self.guard_open_time - STEP)
        self.invulnerable = max(0, self.invulnerable - STEP)
        self.attack_cooldown = max(0, self.attack_cooldown - STEP)
        self.attack_flash = max(0, self.attack_flash - STEP)
        if self.attack_hit_pending and self.attack_flash <= self.attack_duration * 0.55:
            self.attack_hit_pending = False
            self._apply_attack()
        player_x, player_floor = self.player.x, self.player.floor
        if not self.lift_riding:
            self._move(self.player, motion)
            self._block_body(player_x, player_floor)
        for hazard in self.stage.hidden_hazards:
            # 분신의 빛이 닿지 않은 함정은 뛰어넘을 수도 없다. 무작정 점프로는 통과하지 못한다.
            airborne = self.player.jump_time > 0 and self.hazard_lit(hazard)
            if not airborne and self.player.floor == hazard.floor and abs(self.player.x - hazard.x) <= 18:
                # 맞으면서 밀고 지나갈 수 없도록 온 방향으로 튕겨 낸다. 점프로만 넘는다.
                self._move_x(self.player, 70 if player_x > hazard.x else -70)
                if self.invulnerable == 0:
                    self.health -= 1
                    self.invulnerable = 0.92
                    self.notify('숨겨진 함정입니다! 분신 곁에서 위치를 보고 뛰어넘으세요.')
                    if self.health <= 0:
                        self.result = 'defeated'
                        return
        if attack and self.attack_cooldown == 0:
            self._attack(attack if isinstance(attack, str) else 'slash')

        if self.echo is not None:
            previous_x = self.echo.actor.x
            previous_floor = self.echo.actor.floor
            self._move(self.echo.actor, self.echo.inputs[self.echo.cursor])
            self._update_sequence(previous_x, previous_floor)
            self._update_sync(player_x, player_floor, previous_x, previous_floor)
            self.echo.cursor += 1
            if self.echo.cursor == len(self.echo.inputs):
                self._remove_echo()
                self.notify('분신의 재현이 끝났습니다.')

        if self.echo is None:
            self._update_sync(player_x, player_floor, None, None)

        self._update_bridge()
        self._update_lift()
        self._update_watch()

        for enemy in self.enemies:
            self._update_enemy(enemy)
            if self.health <= 0:
                self.result = 'defeated'
                return

        self._update_watch()

        self._update_doors(STEP)
        if self._near(self.player, self.stage.exit, 27):
            if any(enemy.spawn.kind in BOSS_KINDS for enemy in self.enemies):
                if self.message_time <= 0:
                    self.notify('보스를 처치하면 출구가 열립니다.')
            else:
                self.result = 'cleared'

    def hazard_lit(self, hazard: Point) -> bool:
        return (self.echo is not None and self.echo.actor.floor == hazard.floor
                and abs(self.echo.actor.x - hazard.x) <= 120)

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
        if self.stage.bridge:
            for point, remaining in zip(self.stage.bridge.points, self.bridge_timers):
                if point.floor == floor and remaining <= 0:
                    yield point.x
        room = self.stage.isolation
        if room:
            if self.isolation_closed and room.door.floor == floor:
                yield room.door.x
            if not self.isolation_closed and room.exit_gate.floor == floor:
                yield room.exit_gate.x
        if self.stage.watch_gate and self.stage.watch_gate.door.floor == floor and not self.watch_active:
            yield self.stage.watch_gate.door.x
        if self.index != 2 and self.stage.guard and self.stage.guard.floor == floor and self.guard_open_time == 0:
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

    def _move_x(self, actor: Actor, amount: float):
        start = actor.x
        target = min(RIGHT, max(LEFT, start + amount))
        margin = GATE_HALF_WIDTH + ACTOR_RADIUS
        for wall in self._barriers(actor.floor):
            if start <= wall - margin and target > wall - margin:
                target = wall - margin
            elif start >= wall + margin and target < wall + margin:
                target = wall + margin
        actor.x = target
        distance = abs(target - start)
        actor.moving = distance > 0.001
        actor.walk_distance += distance

    def _move(self, actor: Actor, motion: Motion):
        if actor.elevator_target is not None:
            actor.moving = False
            actor.elevator_time += STEP
            if actor.elevator_time >= ELEVATOR_DURATION:
                actor.floor = actor.elevator_target
                actor.elevator_target = None
                actor.elevator_time = 0.0
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
                    break

    @staticmethod
    def _near(actor: Actor, point: Point, distance: float) -> bool:
        return actor.elevator_target is None and actor.jump_time == 0 and actor.floor == point.floor and abs(actor.x - point.x) <= distance

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
            state.open = state.latched or state.pressed or state.grace > 0 or (state.open and occupied)

    def _remove_echo(self):
        if self.echo is None:
            return
        for enemy in self.enemies:
            if enemy.target is self.echo.actor:
                enemy.target = None
                enemy.windup = 0
        self.echo = None
        if not self.sequence_unlocked:
            self.sequence_progress = 0
        if not self.sync_unlocked:
            self.sync_echo_time = None

    def _update_sequence(self, previous_x: float, previous_floor: int):
        sequence = self.stage.sequence
        if sequence is None or self.sequence_unlocked or self.echo is None:
            return
        actor = self.echo.actor
        # 공중에서는 감지 지점을 밟지 않는다. 점프로 순서를 건너뛸 수 있다.
        if actor.floor != previous_floor or actor.x == previous_x or actor.jump_time > 0:
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

    def _update_sync(self, player_x, player_floor, echo_x, echo_floor):
        gate = self.stage.sync_gate
        if gate is None or self.sync_unlocked:
            return
        if self.sync_player_time is not None and self.time - self.sync_player_time > 1.2:
            self.sync_player_time = None
        if self.sync_echo_time is not None and self.time - self.sync_echo_time > 1.2:
            self.sync_echo_time = None
        if player_floor == gate.player_sensor.floor == self.player.floor and player_x > gate.player_sensor.x >= self.player.x:
            self.sync_player_time = self.time
        if self.echo is not None and echo_x is not None and echo_floor == gate.echo_sensor.floor == self.echo.actor.floor and echo_x > gate.echo_sensor.x >= self.echo.actor.x:
            self.sync_echo_time = self.time
        if self.sync_player_time is not None and self.sync_echo_time is not None:
            self.sync_unlocked = True
            self.notify('두 감지선을 통과했습니다. 보안문이 열렸습니다.')

    def _update_watch(self):
        gate = self.stage.watch_gate
        self.watch_active = bool(gate and self.echo and self._near(self.echo.actor, gate.focus, 65))

    def _update_bridge(self):
        bridge = self.stage.bridge
        if bridge is None:
            return
        for index, point in enumerate(bridge.points):
            self.bridge_timers[index] = max(0, self.bridge_timers[index] - STEP)
            if self.echo and self.echo.actor.floor == bridge.echo_floor and abs(self.echo.actor.x - point.x) <= 18:
                self.bridge_timers[index] = 2.0
            if self.player.floor == point.floor and abs(self.player.x - point.x) < GATE_HALF_WIDTH + ACTOR_RADIUS:
                self.bridge_timers[index] = max(self.bridge_timers[index], STEP)
        if (self.echo is None and self.player.floor == bridge.points[0].floor
                and bridge.points[0].x < self.player.x < bridge.points[-1].x
                and not any(remaining > STEP for remaining in self.bridge_timers)):
            self.player.x = bridge.points[0].x - GATE_HALF_WIDTH - ACTOR_RADIUS - 1
            self.notify('발판이 사라졌습니다. 안전한 곳에서 다시 시도하세요.')

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
        self.attack_hit_pending = True

    def _apply_attack(self):
        weapon = WEAPONS[self.weapon_index]
        reach = round(weapon.reach * (0.8 if self.attack_kind == 'slash' else 1.3))
        damage = weapon.damage + (1 if self.attack_kind == 'slash' else 0)
        for enemy in self.enemies:
            offset = enemy.actor.x - self.player.x
            if offset * self.player.facing < -12 or not self._clear_line(self.player, enemy.actor, reach):
                continue
            if enemy.health is None:
                self.notify('이 적은 분신으로 유인하거나 우회하세요.')
            else:
                enemy.health = max(0, enemy.health - damage)
                enemy.flash = 0.19
        boss_defeated = any(enemy.health == 0 and enemy.spawn.kind in BOSS_KINDS for enemy in self.enemies)
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

        if enemy.target is not None:
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
            visible_echo = self.echo.actor if self.echo is not None else None
            for candidate in (self.player, visible_echo):
                if candidate is not None and within_chase_area(candidate) and self._clear_line(actor, candidate, sight):
                    enemy.target = candidate
                    enemy.last_seen = candidate.x
                    enemy.unseen = 0
                    break

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

    def _enemy_attack(self, enemy: Enemy, distance: int):
        target = enemy.target
        if target is None or not self._clear_line(enemy.actor, target, distance + 8):
            return
        if target is self.player:
            if self.invulnerable == 0:
                self.health -= 1
                self.invulnerable = 0.92
                self.notify('피격! 필요하면 R로 스테이지를 다시 시작하세요.')
        elif self.echo is not None and target is self.echo.actor:
            if self.stage.guard and enemy.spawn.point == self.stage.guard:
                self.guard_open_time = 4.0 if self.stage.elevators else 1.1
            self._remove_echo()
            self.notify('분신이 공격을 받아 사라졌습니다.')
