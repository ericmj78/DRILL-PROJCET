from dataclasses import dataclass, field

from stages import (
    ACTOR_RADIUS, ATTACK_COOLDOWN, ATTACK_RANGE, DOOR_GRACE, ENEMY_KINDS,
    GATE_HALF_WIDTH, LEFT, MAX_HEALTH, MAX_RECORD_SECONDS, MOVE_SPEED,
    PLATE_RANGE, RIGHT, STAIR_RANGE, STAGES, STEP, EnemySpawn, Point,
)


@dataclass
class Actor:
    x: float
    floor: int
    facing: int = 1
    moving: bool = False

    @classmethod
    def at(cls, point: Point, facing: int = 1):
        return cls(point.x, point.floor, facing)


@dataclass(frozen=True)
class Motion:
    horizontal: int = 0
    stairs: int = 0


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
    def __init__(self, index: int = 0):
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
        self.invulnerable = 0.0
        self.attack_cooldown = 0.0
        self.attack_flash = 0.0
        self.time = 0.0
        self.result = 'playing'
        self.message = ''
        self.message_time = 0.0
        self._update_doors(0)

    def notify(self, message: str):
        self.message = message
        self.message_time = 2.2

    def toggle_recording(self):
        if self.result != 'playing':
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

    def step(self, motion: Motion = Motion(), attack: bool = False):
        if self.result != 'playing':
            return
        self.message_time = max(0, self.message_time - STEP)
        if self.recording is not None:
            self._move(self.recording.preview, motion)
            self.recording.inputs.append(motion)
            if len(self.recording.inputs) >= round(MAX_RECORD_SECONDS / STEP):
                self._finish_recording(time_limit=True)
            return

        self.time += STEP
        self.invulnerable = max(0, self.invulnerable - STEP)
        self.attack_cooldown = max(0, self.attack_cooldown - STEP)
        self.attack_flash = max(0, self.attack_flash - STEP)
        self._move(self.player, motion)
        if attack and self.attack_cooldown == 0:
            self._attack()

        if self.echo is not None:
            self._move(self.echo.actor, self.echo.inputs[self.echo.cursor])
            self.echo.cursor += 1
            if self.echo.cursor == len(self.echo.inputs):
                self._remove_echo()
                self.notify('분신의 재현이 끝났습니다.')

        for enemy in self.enemies:
            self._update_enemy(enemy)
            if self.health <= 0:
                self.result = 'defeated'
                return

        self._update_doors(STEP)
        if self._near(self.player, self.stage.exit, 27):
            self.result = 'cleared'

    def _barriers(self, floor: int):
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
        actor.moving = abs(target - start) > 0.001

    def _move(self, actor: Actor, motion: Motion):
        if motion.horizontal:
            actor.facing = motion.horizontal
        self._move_x(actor, motion.horizontal * MOVE_SPEED * STEP)
        if motion.stairs:
            lower = actor.floor if motion.stairs > 0 else actor.floor - 1
            for stair in self.stage.stairs:
                if stair.lower == lower and abs(stair.x - actor.x) <= STAIR_RANGE:
                    actor.x = stair.x
                    actor.floor += motion.stairs
                    break

    @staticmethod
    def _near(actor: Actor, point: Point, distance: float) -> bool:
        return actor.floor == point.floor and abs(actor.x - point.x) <= distance

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
            state.open = state.pressed or state.grace > 0 or (state.open and occupied)

    def _remove_echo(self):
        if self.echo is None:
            return
        for enemy in self.enemies:
            if enemy.target is self.echo.actor:
                enemy.target = None
                enemy.windup = 0
        self.echo = None

    def _clear_line(self, first: Actor, second: Actor, distance: float) -> bool:
        if first.floor != second.floor or abs(first.x - second.x) > distance:
            return False
        left, right = sorted((first.x, second.x))
        return not any(left < wall < right for wall in self._barriers(first.floor))

    def _attack(self):
        self.attack_cooldown = ATTACK_COOLDOWN
        self.attack_flash = 0.14
        for enemy in self.enemies:
            offset = enemy.actor.x - self.player.x
            if offset * self.player.facing < -12 or not self._clear_line(self.player, enemy.actor, ATTACK_RANGE):
                continue
            if enemy.health is None:
                self.notify('이 적은 분신으로 유인하거나 우회하세요.')
            else:
                enemy.health -= 1
                enemy.flash = 0.19
        self.enemies = [enemy for enemy in self.enemies if enemy.health != 0]

    def _update_enemy(self, enemy: Enemy):
        kind = ENEMY_KINDS[enemy.spawn.kind]
        actor = enemy.actor
        actor.moving = False
        enemy.flash = max(0, enemy.flash - STEP)
        enemy.recovery = max(0, enemy.recovery - STEP)

        if enemy.target is not None:
            if self._clear_line(actor, enemy.target, kind.sight):
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
                if candidate is not None and self._clear_line(actor, candidate, kind.sight):
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
            if enemy.recovery == 0:
                self._walk_enemy(actor, enemy.last_seen, kind.speed)
            return

        left, right = enemy.spawn.patrol
        destination = left if enemy.patrol_direction < 0 else right
        self._walk_enemy(actor, destination, kind.speed * 0.46)
        if abs(actor.x - destination) < 1 or not actor.moving:
            enemy.patrol_direction *= -1

    def _walk_enemy(self, actor: Actor, destination: float, speed: float):
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
            self._remove_echo()
            self.notify('분신이 공격을 받아 사라졌습니다.')
