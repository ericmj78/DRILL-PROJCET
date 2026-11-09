from dataclasses import dataclass, field

from stages import (
    ACTOR_RADIUS, ATTACK_COOLDOWN, GATE_HALF_WIDTH, LEFT, MAX_RECORD_SECONDS,
    MOVE_SPEED, RIGHT, STAGE, STEP, Point,
)


@dataclass
class Actor:
    x: float
    floor: int
    facing: int = 1
    moving: bool = False
    walk_distance: float = 0

    @classmethod
    def at(cls, point: Point, facing: int = 1):
        return cls(point.x, point.floor, facing)


@dataclass(frozen=True)
class Motion:
    horizontal: int = 0


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


class World:
    def __init__(self):
        self.stage = STAGE
        self.player = Actor.at(self.stage.start)
        self.echo: Echo | None = None
        self.recording: Recording | None = None
        self.attack_cooldown = 0.0
        self.attack_flash = 0.0
        self.time = 0.0
        self.message = ''
        self.message_time = 0.0

    def notify(self, message: str):
        self.message = message
        self.message_time = 2.2

    def toggle_recording(self):
        if self.recording is None:
            if self.echo is not None:
                self.notify('분신의 재현이 끝난 뒤 다시 녹화하세요.')
                return
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
        self.echo = Echo(Actor.at(record.start, record.facing), tuple(record.inputs))
        self.notify('녹화 상한에 도달해 재현을 시작합니다.' if time_limit else '본체 조작 재개 · 분신이 재현합니다.')

    def step(self, motion: Motion = Motion(), attack: bool = False):
        self.message_time = max(0, self.message_time - STEP)
        if self.recording is not None:
            self._move(self.recording.preview, motion)
            self.recording.inputs.append(motion)
            if len(self.recording.inputs) >= round(MAX_RECORD_SECONDS / STEP):
                self._finish_recording(time_limit=True)
            return

        self.time += STEP
        self.attack_cooldown = max(0, self.attack_cooldown - STEP)
        self.attack_flash = max(0, self.attack_flash - STEP)
        self._move(self.player, motion)
        if attack and self.attack_cooldown == 0:
            self.attack_cooldown = ATTACK_COOLDOWN
            self.attack_flash = 0.14

        if self.echo is not None:
            self._move(self.echo.actor, self.echo.inputs[self.echo.cursor])
            self.echo.cursor += 1
            if self.echo.cursor == len(self.echo.inputs):
                self.echo = None
                self.notify('분신의 재현이 끝났습니다.')

    def _barriers(self, floor: int):
        for wall in self.stage.walls:
            if wall.floor == floor:
                yield wall.x

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
        if motion.horizontal:
            actor.facing = motion.horizontal
        self._move_x(actor, motion.horizontal * MOVE_SPEED * STEP)
