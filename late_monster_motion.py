"""후반 몬스터의 대기·이동과 공격 자세를 그린다."""
from math import pi, sin

from pico2d import pico2d as canvas


KINDS = frozenset(('time_thief', 'cursed_lantern', 'broken_jester'))


def draw(image, actor, floor_y, size, time, kind, pose=None, tint=(255, 255, 255)):
    """광대는 걸음 시트를, 시간 도둑과 등불은 각기 다른 움직임을 쓴다."""
    if kind == 'broken_jester':
        cell_w, cell_h = image.w // 4, image.h // 4
        frame = int(actor.walk_distance / 7) % 16 if actor.moving else 0
        source = canvas.SDL_Rect((frame % 4) * cell_w, (frame // 4) * cell_h, cell_w, cell_h)
        faces_right = True
        bob = 0 if actor.moving else sin(time * 2) * 1.2
        tilt = 0 if actor.moving else sin(time * 1.8)
    else:
        source = canvas.SDL_Rect(0, 0, image.w, image.h)
        cell_w, cell_h = image.w, image.h
        faces_right = False
        if kind == 'cursed_lantern':
            bob = 17 + sin(time * 3.4) * 4
            tilt = sin(time * 2.5) * (6 if actor.moving else 3)
        else:
            bob = abs(sin(actor.walk_distance / 15)) * 3 if actor.moving else sin(time * 2) * 1.5
            tilt = sin(actor.walk_distance / 19) * 5 if actor.moving else sin(time * 1.7) * 1.5

    dx = dy = 0
    sx = sy = 1
    if pose is not None:
        dx, dy, sx, sy = pose.dx, pose.dy, pose.sx, pose.sy
        tilt += pose.angle * actor.facing
    height = size * sy
    width = size * cell_w / cell_h * sx
    left = actor.x + actor.facing * dx - width / 2
    top = canvas.get_canvas_height() - (floor_y + bob + dy) - height
    flip = canvas.SDL_FLIP_HORIZONTAL if (actor.facing > 0) != faces_right else canvas.SDL_FLIP_NONE
    canvas.SDL_SetTextureColorMod(image.texture, *tint)
    canvas.SDL_RenderCopyExF(canvas.renderer, image.texture, source,
                             canvas.SDL_FRect(left, top, width, height), tilt,
                             canvas.SDL_FPoint(width / 2, height / 2), flip)
    canvas.SDL_SetTextureColorMod(image.texture, 255, 255, 255)
