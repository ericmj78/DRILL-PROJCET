from time import perf_counter

from pico2d import (
    SDL_KEYDOWN, SDL_KEYUP, SDL_QUIT, SDLK_a, SDLK_BACKSPACE, SDLK_c,
    SDLK_DOWN, SDLK_ESCAPE, SDLK_LEFT, SDLK_r, SDLK_RETURN, SDLK_RIGHT,
    SDLK_s, SDLK_UP, clear_canvas, close_canvas, delay, get_events,
    hide_lattice, open_canvas, update_canvas,
)
from pico2d import pico2d as canvas

from stages import STAGES, STEP
from view import HEIGHT, WIDTH, View
from world import Motion, World


def main():
    canvas.SDL_SetHint(canvas.SDL_HINT_RENDER_SCALE_QUALITY, b'1')
    open_canvas(WIDTH, HEIGHT, sync=True)
    view = None
    try:
        if canvas.window and not canvas.renderer:
            canvas.renderer = canvas.SDL_CreateRenderer(canvas.window, -1, canvas.SDL_RENDERER_SOFTWARE)
        if not canvas.renderer:
            raise RuntimeError(canvas.SDL_GetError().decode('utf-8', errors='replace'))
        hide_lattice()
        canvas.SDL_SetRenderDrawBlendMode(canvas.renderer, canvas.SDL_BLENDMODE_BLEND)
        view = View()
        world = World()
        screen = 'intro'
        pressed = set()
        pending_stairs = 0
        pending_attack = False
        accumulator = 0.0
        previous = perf_counter()

        while True:
            now = perf_counter()
            accumulator += min(now - previous, 0.1)
            previous = now

            for event in get_events():
                if event.type == SDL_QUIT:
                    return
                if event.type == SDL_KEYUP:
                    pressed.discard(event.key)
                if event.type != SDL_KEYDOWN:
                    continue
                key = event.key
                if key == SDLK_ESCAPE:
                    return
                if screen == 'intro':
                    if key == SDLK_RETURN:
                        screen = 'play'
                    continue
                if key == SDLK_r or (key == SDLK_RETURN and world.result == 'cleared'):
                    index = world.index if key == SDLK_r else (world.index + 1) % len(STAGES)
                    world = World(index)
                    pressed.clear()
                    pending_stairs = 0
                    pending_attack = False
                    accumulator = 0.0
                    continue
                if world.result != 'playing':
                    continue
                if key in (SDLK_LEFT, SDLK_RIGHT):
                    pressed.add(key)
                elif key in (SDLK_UP, SDLK_DOWN):
                    pending_stairs = 1 if key == SDLK_UP else -1
                elif key == SDLK_c:
                    world.toggle_recording()
                    pending_attack = False
                elif key == SDLK_BACKSPACE:
                    world.cancel_recording()
                elif key in (SDLK_a, SDLK_s) and world.recording is None:
                    pending_attack = True

            while accumulator >= STEP:
                if screen == 'play':
                    horizontal = int(SDLK_RIGHT in pressed) - int(SDLK_LEFT in pressed)
                    world.step(Motion(horizontal, pending_stairs), pending_attack)
                pending_stairs = 0
                pending_attack = False
                accumulator -= STEP

            clear_canvas()
            view.draw(world, screen)
            update_canvas()
            delay(0.001)
    finally:
        del view
        close_canvas()


if __name__ == '__main__':
    main()
