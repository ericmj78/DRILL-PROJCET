from time import perf_counter

from pico2d import (
    SDL_KEYDOWN, SDL_KEYUP, SDL_MOUSEBUTTONDOWN, SDL_MOUSEMOTION, SDL_QUIT, SDLK_0, SDLK_4, SDLK_9, SDLK_a, SDLK_BACKSPACE, SDLK_c,
    SDLK_DOWN, SDLK_e, SDLK_ESCAPE, SDLK_LEFT, SDLK_p, SDLK_r, SDLK_RETURN, SDLK_RIGHT,
    SDLK_s, SDLK_SPACE, SDLK_UP, clear_canvas, close_canvas, delay, get_events,
    hide_lattice, open_canvas, update_canvas,
)
from pico2d import pico2d as canvas

from stages import STAGES, STEP
from title_menu import TitleMenu
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
        canvas.SDL_SetWindowFullscreen(canvas.window, canvas.SDL_WINDOW_FULLSCREEN_DESKTOP)
        canvas.SDL_RenderSetLogicalSize(canvas.renderer, WIDTH, HEIGHT)
        hide_lattice()
        canvas.SDL_SetRenderDrawBlendMode(canvas.renderer, canvas.SDL_BLENDMODE_BLEND)
        view = View()
        world = World()
        screen = 'intro'
        menu = TitleMenu()
        pressed = set()
        pending_stairs = 0
        pending_jump = False
        pending_attack = False
        accumulator = 0.0
        previous = perf_counter()
        stage_entry = None

        while True:
            now = perf_counter()
            accumulator += min(now - previous, 0.1)
            previous = now

            for event in get_events():
                if event.type == SDL_QUIT:
                    return
                if event.type == SDL_KEYUP:
                    pressed.discard(event.key)
                if screen == 'intro' and stage_entry is None:
                    if event.type in (SDL_MOUSEMOTION, SDL_MOUSEBUTTONDOWN):
                        event.y = HEIGHT - 1 - event.y  # pico2d는 마우스 y를 위에서부터 센다.
                    action = menu.handle(event)
                    if action == 'quit':
                        return
                    if action == 'start' or action and action.startswith('stage:'):
                        index = int(action.split(':')[1]) if ':' in action else 0
                        world = World(index, weapon_index=world.weapon_index, xp=world.xp)
                        screen = 'play'
                        pressed.clear()
                        accumulator = 0.0
                    elif action == 'back':
                        menu.open('main')
                    elif action == 'fullscreen':
                        menu.fullscreen = not menu.fullscreen
                        canvas.SDL_SetWindowFullscreen(
                            canvas.window, canvas.SDL_WINDOW_FULLSCREEN_DESKTOP if menu.fullscreen else 0)
                    elif action:
                        menu.open(action)
                    continue
                if event.type != SDL_KEYDOWN:
                    continue
                key = event.key
                if stage_entry is not None:
                    if key == SDLK_ESCAPE or key == SDLK_p:
                        stage_entry = None
                    elif key == SDLK_BACKSPACE:
                        stage_entry = stage_entry[:-1]
                    elif SDLK_0 <= key <= SDLK_9 and len(stage_entry) < len(str(len(STAGES))):
                        stage_entry += str(key - SDLK_0)
                    elif key == SDLK_RETURN and stage_entry:
                        number = int(stage_entry)
                        if 1 <= number <= len(STAGES):
                            world = World(number - 1, weapon_index=world.weapon_index, xp=world.xp)
                            screen = 'play'
                            stage_entry = None
                    accumulator = 0.0
                    continue
                if key == SDLK_p:
                    stage_entry = ''
                    pressed.clear()
                    pending_stairs = 0
                    pending_jump = False
                    pending_attack = False
                    accumulator = 0.0
                    continue
                if key == SDLK_ESCAPE:
                    screen = 'intro'
                    menu.open('main')
                    pressed.clear()
                    continue
                if key == SDLK_r or (key == SDLK_RETURN and world.result == 'cleared'):
                    index = world.index if key == SDLK_r else (world.index + 1) % len(STAGES)
                    world = World(index, weapon_index=world.weapon_index, xp=world.xp)
                    pressed.clear()
                    pending_stairs = 0
                    pending_jump = False
                    pending_attack = False
                    accumulator = 0.0
                    continue
                if world.result != 'playing':
                    continue
                if key in (SDLK_LEFT, SDLK_RIGHT):
                    pressed.add(key)
                elif key == SDLK_SPACE and key not in pressed:
                    pressed.add(key)
                    pending_jump = True
                elif key in (SDLK_UP, SDLK_DOWN):
                    pending_stairs = 1 if key == SDLK_UP else -1
                elif key == SDLK_c:
                    world.toggle_recording()
                    pending_attack = False
                elif key == SDLK_BACKSPACE:
                    world.cancel_recording()
                elif key == SDLK_e and key not in pressed:
                    pressed.add(key)
                    world.toggle_lever()
                elif SDLK_0 <= key <= SDLK_4:
                    world.select_weapon(key - SDLK_0)
                elif key in (SDLK_a, SDLK_s) and world.recording is None:
                    pending_attack = 'slash' if key == SDLK_a else 'thrust'

            while accumulator >= STEP:
                if screen == 'play' and stage_entry is None:
                    horizontal = int(SDLK_RIGHT in pressed) - int(SDLK_LEFT in pressed)
                    world.step(Motion(horizontal, pending_stairs, pending_jump), pending_attack)
                pending_stairs = 0
                pending_jump = False
                pending_attack = False
                accumulator -= STEP

            clear_canvas()
            view.draw(world, screen, menu)
            if stage_entry is not None:
                view.draw_stage_selector(stage_entry)
            update_canvas()
            delay(0.001)
    finally:
        del view
        close_canvas()


if __name__ == '__main__':
    main()
