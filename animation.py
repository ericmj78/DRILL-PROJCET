from pico2d import pico2d as canvas


STRIDE_PER_FRAME = 22


def draw_region(image, source, left, bottom, width, height, flip=False):
    """Draw an atlas region using top-left image coordinates and game coordinates."""
    source_rect = canvas.SDL_Rect(*source)
    target_rect = canvas.to_sdl_rect(left, bottom, width, height)
    direction = canvas.SDL_FLIP_HORIZONTAL if flip else canvas.SDL_FLIP_NONE
    canvas.SDL_RenderCopyEx(canvas.renderer, image.texture, source_rect, target_rect, 0, None, direction)


class WalkCycle:
    def __init__(self, image, frames, draw_height=87, stride_per_frame=STRIDE_PER_FRAME):
        self.image = image
        self.frames = frames
        self.draw_height = draw_height
        self.stride_per_frame = stride_per_frame

    def draw(self, actor, floor_y, opacity=255, height=None, faces=1, tint=(255, 255, 255)):
        poses = self.frames
        pose = poses[int(actor.walk_distance / self.stride_per_frame) % len(poses)]
        _, _, source_width, source_height = pose
        height = self.draw_height if height is None else height
        width = height * source_width / source_height
        canvas.SDL_SetTextureAlphaMod(self.image.texture, opacity)
        canvas.SDL_SetTextureColorMod(self.image.texture, *tint)
        draw_region(self.image, pose, actor.x - width / 2, floor_y, width, height,
                    actor.facing != faces)
        canvas.SDL_SetTextureColorMod(self.image.texture, 255, 255, 255)
        canvas.SDL_SetTextureAlphaMod(self.image.texture, 255)


class AttackCycle:
    def __init__(self, image, frames, draw_height=103):
        self.image = image
        self.frames = frames
        self.draw_height = draw_height

    def draw(self, actor, floor_y, progress, opacity=255):
        frame_index = min(int(progress * len(self.frames)), len(self.frames) - 1)
        pose = self.frames[frame_index]
        _, _, source_width, source_height = pose
        height = self.draw_height
        width = height * source_width / source_height
        canvas.SDL_SetTextureAlphaMod(self.image.texture, opacity)
        draw_region(
            self.image, pose, actor.x - width / 2, floor_y, width, height,
            actor.facing < 0,
        )
        canvas.SDL_SetTextureAlphaMod(self.image.texture, 255)
