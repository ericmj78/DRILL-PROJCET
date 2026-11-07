from pico2d import pico2d as canvas


STRIDE_PER_FRAME = 22


def draw_region(image, source, left, bottom, width, height, flip=False):
    """Draw an atlas region using top-left image coordinates and game coordinates."""
    source_rect = canvas.SDL_Rect(*source)
    target_rect = canvas.to_sdl_rect(left, bottom, width, height)
    direction = canvas.SDL_FLIP_HORIZONTAL if flip else canvas.SDL_FLIP_NONE
    canvas.SDL_RenderCopyEx(canvas.renderer, image.texture, source_rect, target_rect, 0, None, direction)


class WalkCycle:
    def __init__(self, image, frames):
        self.image = image
        self.frames = frames

    def draw(self, actor, floor_y, opacity=255):
        poses = self.frames
        pose = poses[int(actor.walk_distance / STRIDE_PER_FRAME) % len(poses)]
        _, _, source_width, source_height = pose
        height = 87
        width = height * source_width / source_height
        canvas.SDL_SetTextureAlphaMod(self.image.texture, opacity)
        draw_region(self.image, pose, actor.x - width / 2, floor_y, width, height, actor.facing < 0)
