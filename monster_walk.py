from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, pi, radians, sin, sqrt

from pico2d import pico2d as canvas


def draw_part(image, source, center, scale, angle, actor_x, floor_y, flip):
    _, _, width, height = source
    width *= scale
    height *= scale
    cx, cy = center
    x = actor_x - cx if flip else actor_x + cx
    y = canvas.get_canvas_height() - floor_y - cy
    target = canvas.SDL_FRect(x - width / 2, y - height / 2, width, height)
    direction = canvas.SDL_FLIP_HORIZONTAL if flip else canvas.SDL_FLIP_NONE
    canvas.SDL_RenderCopyExF(
        canvas.renderer, image.texture, canvas.SDL_Rect(*source), target,
        degrees(-angle if flip else angle), None, direction,
    )


@dataclass(frozen=True)
class Bone:
    source: tuple[int, int, int, int]
    joint: tuple[int, int]
    tip: tuple[int, int]
    length: float

    def draw(self, image, start, end, actor_x, floor_y, flip):
        sx, sy, width, height = self.source
        px, py = self.joint
        vx, vy = self.tip[0] - px, self.tip[1] - py
        dx, dy = end[0] - start[0], start[1] - end[1]
        angle = atan2(dy, dx) - atan2(vy, vx)
        scale = hypot(dx, dy) / hypot(vx, vy)
        offset_x = (sx + width / 2 - px) * scale
        offset_y = (sy + height / 2 - py) * scale
        cx = start[0] + offset_x * cos(angle) - offset_y * sin(angle)
        cy = start[1] - offset_x * sin(angle) - offset_y * cos(angle)
        draw_part(image, self.source, (cx, cy), scale, angle, actor_x, floor_y, flip)


@dataclass(frozen=True)
class Sole:
    source: tuple[int, int, int, int]
    ankle: tuple[int, int]
    bottom: int
    scale: float

    def draw(self, image, foot, actor_x, floor_y, flip):
        x, y, width, height = self.source
        center = (
            foot[0] + (x + width / 2 - self.ankle[0]) * self.scale,
            foot[1] + (self.bottom - y - height / 2) * self.scale,
        )
        draw_part(image, self.source, center, self.scale, 0, actor_x, floor_y, flip)
        return foot[0], foot[1] + (self.bottom - self.ankle[1]) * self.scale


@dataclass(frozen=True)
class Leg:
    hip: tuple[int, int]
    home_x: float
    phase: float
    upper: Bone
    lower: Bone
    bend: int = 1
    sole: Sole | None = None

    def knee(self, hip, foot):
        dx, dy = foot[0] - hip[0], foot[1] - hip[1]
        distance = hypot(dx, dy)
        along = (distance**2 + self.upper.length**2 - self.lower.length**2) / (2 * distance)
        offset = self.bend * sqrt(max(0, self.upper.length**2 - along**2))
        return (
            hip[0] + (dx * along + dy * offset) / distance,
            hip[1] + (dy * along - dx * offset) / distance,
        )


@dataclass(frozen=True)
class Gait:
    sheet: str
    torso: tuple[int, int, int, int]
    origin: tuple[int, int]
    scale: float
    hip_height: float
    cycle_distance: float
    lift: float
    bob: float
    rock: float
    far_legs: tuple[Leg, ...]
    near_legs: tuple[Leg, ...]
    near_legs_in_front: bool = False

    def foot(self, phase):
        stance = 0.56
        half_step = self.cycle_distance * stance / 2
        if phase < stance:
            # In local left-facing coordinates this cancels the actor's movement.
            return phase * self.cycle_distance - half_step, 0
        swing = (phase - stance) / (1 - stance)
        progress = swing**2 * (3 - 2 * swing)
        # Match stance velocity at lift-off and touchdown so the foot leaves
        # and meets the ground without a sudden horizontal change of speed.
        carry = swing * (1 - swing) * (1 - 2 * swing)
        step = half_step * (1 - 2 * progress) + self.cycle_distance * (1 - stance) * carry
        lift_phase = swing + 0.25 * swing * (1 - swing)
        return step, self.lift * sin(pi * lift_phase)**2

    def body_point(self, x, y, hip_y, pitch):
        dx = (x - self.origin[0]) * self.scale
        dy = (self.origin[1] - y) * self.scale
        c, s = cos(pitch), sin(pitch)
        return dx * c + dy * s, hip_y + dy * c - dx * s


class MonsterWalk:
    def __init__(self, image, gait):
        self.image = image
        self.gait = gait

    def draw(self, actor, floor_y, faces=-1, tint=(255, 255, 255), windup=None, recovery=None):
        gait = self.gait
        phase = (actor.walk_distance / gait.cycle_distance) % 1
        weight = 4 * pi * (phase - 0.055)
        hip_y = gait.hip_height + gait.bob * (1 - cos(weight)) / 2
        pitch = radians(gait.rock) * sin(weight)
        forward = 0
        attacking = windup is not None or recovery is not None
        if windup is not None:
            prep = windup * windup * (3 - 2 * windup)
            forward = -5.5 * prep
            hip_y -= 2.5 * prep
            pitch += radians(gait.rock * 1.4) * prep
        elif recovery is not None:
            release = min(1, recovery / 0.20)
            lunge = 1 - release * release * (3 - 2 * release)
            forward = 8 * lunge
            hip_y -= 2.5 * lunge
            pitch -= radians(gait.rock * 1.8) * lunge
        body_pose = (hip_y, pitch)
        flip = actor.facing != faces
        texture = self.image.texture
        actor_x = actor.x + actor.facing * forward

        canvas.SDL_SetTextureColorMod(texture, *(round(channel * 0.67) for channel in tint))
        self._draw_legs(gait.far_legs, phase, body_pose, 2, actor_x, floor_y, flip, attacking)
        canvas.SDL_SetTextureColorMod(texture, *tint)
        if not gait.near_legs_in_front:
            self._draw_legs(gait.near_legs, phase, body_pose, 0, actor_x, floor_y, flip, attacking)

        x, y, width, height = gait.torso
        center = gait.body_point(x + width / 2, y + height / 2, *body_pose)
        draw_part(self.image, gait.torso, center, gait.scale, pitch, actor_x, floor_y, flip)

        if gait.near_legs_in_front:
            self._draw_legs(gait.near_legs, phase, body_pose, 0, actor_x, floor_y, flip, attacking)
        canvas.SDL_SetTextureColorMod(texture, 255, 255, 255)

    def _draw_legs(self, legs, phase, body_pose, depth, actor_x, floor_y, flip, attacking):
        gait = self.gait
        for leg in legs:
            hip = gait.body_point(*leg.hip, *body_pose)
            step, lift = (0, 0) if attacking else gait.foot((phase + leg.phase) % 1)
            if leg.sole is not None:
                foot = (leg.home_x + step, depth + lift)
                ankle = leg.sole.draw(self.image, foot, actor_x, floor_y, flip)
            else:
                ankle = (leg.home_x + step, 1.5 + depth + lift)
            knee = leg.knee(hip, ankle)
            leg.lower.draw(self.image, knee, ankle, actor_x, floor_y, flip)
            leg.upper.draw(self.image, hip, knee, actor_x, floor_y, flip)


STONE_THIGH = Bone((265, 807, 255, 417), (401, 851), (375, 1173), 26)
STONE_SHIN = Bone((675, 882, 229, 239), (753, 918), (777, 1106), 20)
STONE_FOOT = Sole((640, 1093, 282, 124), (777, 1106), 1205, 0.101)
WOLF_FRONT_UPPER = Bone((214, 617, 187, 291), (350, 662), (283, 866), 15)
WOLF_FRONT_LOWER = Bone((451, 693, 217, 287), (606, 721), (555, 963), 18)
WOLF_REAR_UPPER = Bone((785, 608, 224, 334), (866, 646), (949, 898), 17)
WOLF_REAR_LOWER = Bone((1112, 694, 184, 290), (1174, 736), (1200, 967), 17)
CRAWLER_THIGH = Bone((497, 661, 176, 253), (619, 701), (558, 875), 15)
CRAWLER_SHIN = Bone((832, 670, 208, 275), (994, 708), (889, 928), 16)


MONSTER_GAITS = {
    'warden': Gait(
        sheet='monster_02_warden_walk_parts.png', torso=(205, 27, 781, 714),
        origin=(552, 594), scale=0.105, hip_height=47.5, cycle_distance=54,
        lift=8, bob=2, rock=1.4,
        far_legs=(Leg((509, 594), -3, 0.5, STONE_THIGH, STONE_SHIN, sole=STONE_FOOT),),
        near_legs=(Leg((585, 594), 3, 0, STONE_THIGH, STONE_SHIN, sole=STONE_FOOT),),
    ),
    'beast': Gait(
        sheet='monster_01_hornbeast_walk_parts.png', torso=(208, 4, 1135, 558),
        origin=(766, 485), scale=0.101, hip_height=27, cycle_distance=48,
        lift=6.5, bob=1.2, rock=1.8,
        far_legs=(
            Leg((499, 506), -23, 0.5, WOLF_FRONT_UPPER, WOLF_FRONT_LOWER, bend=-1),
            Leg((895, 479), 18, 0.04, WOLF_REAR_UPPER, WOLF_REAR_LOWER),
        ),
        near_legs=(
            Leg((668, 499), -18, 0, WOLF_FRONT_UPPER, WOLF_FRONT_LOWER, bend=-1),
            Leg((1000, 501), 26, 0.54, WOLF_REAR_UPPER, WOLF_REAR_LOWER),
        ),
    ),
    'crawler': Gait(
        sheet='monster_04_crawler_walk_parts.png', torso=(177, 11, 1163, 590),
        origin=(755, 468), scale=0.086, hip_height=21, cycle_distance=40,
        lift=5.7, bob=0.8, rock=0.9,
        far_legs=(
            Leg((537, 463), -26, 0.5, CRAWLER_THIGH, CRAWLER_SHIN),
            Leg((752, 463), 0, 0.02, CRAWLER_THIGH, CRAWLER_SHIN, bend=-1),
            Leg((975, 463), 26, 0.54, CRAWLER_THIGH, CRAWLER_SHIN, bend=-1),
        ),
        near_legs=(
            Leg((692, 466), -16, 0, CRAWLER_THIGH, CRAWLER_SHIN),
            Leg((893, 465), 12, 0.52, CRAWLER_THIGH, CRAWLER_SHIN, bend=-1),
            Leg((1139, 461), 37, 0.04, CRAWLER_THIGH, CRAWLER_SHIN, bend=-1),
        ),
        near_legs_in_front=True,
    ),
}
