from time import perf_counter

from pico2d import (
    SDL_KEYDOWN, SDL_KEYUP, SDL_MOUSEBUTTONDOWN, SDL_MOUSEMOTION, SDL_QUIT, SDLK_0, SDLK_4, SDLK_9, SDLK_a, SDLK_b, SDLK_BACKSPACE, SDLK_c,
    SDLK_d, SDLK_DOWN, SDLK_e, SDLK_f, SDLK_ESCAPE, SDLK_LEFT, SDLK_p, SDLK_r, SDLK_RETURN, SDLK_RIGHT,
    SDLK_s, SDLK_SPACE, SDLK_UP, clear_canvas, close_canvas, delay, get_events,
    hide_lattice, open_canvas, update_canvas,
)
from pico2d import pico2d as canvas

from stages import BOSS_KINDS, STAGES, STAGE_GROUPS, STEP, next_section_in_stage, stage_group_index
from title_menu import BossSelector, TitleMenu
from view import HEIGHT, WIDTH, View
from world import Motion, World


def advance_stage_section(world):
    """Continue a merged stage while preserving the player's progress."""
    following = next_section_in_stage(world.index) if world.result == 'cleared' else None
    if following is None:
        return world
    next_world = World(following, weapon_index=world.weapon_index, xp=world.xp,
                       monster_echoes=world.monster_echoes)
    next_world.health = min(world.health, next_world.max_health)
    return next_world


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
        pending_web = False
        pending_release = False
        pending_attack = False
        accumulator = 0.0
        previous = perf_counter()
        stage_entry = None
        boss_selector = None
        floor_entry = None   # - 키: 같은 스테이지의 층 번호 입력

        while True:
            now = perf_counter()
            accumulator += min(now - previous, 0.1)
            previous = now

            for event in get_events():
                if event.type == SDL_QUIT:
                    return
                if event.type == SDL_KEYUP:
                    if (event.key == SDLK_f and SDLK_f in pressed and screen == 'play'
                            and world.recording is not None and world.recording.monster_kind == 'crawler'):
                        pending_web = True
                    pressed.discard(event.key)
                if screen == 'intro' and stage_entry is None:
                    if event.type in (SDL_MOUSEMOTION, SDL_MOUSEBUTTONDOWN):
                        event.y = HEIGHT - 1 - event.y  # pico2d는 마우스 y를 위에서부터 센다.
                    action = menu.handle(event)
                    if action == 'quit':
                        return
                    if action == 'start' or action and action.startswith('stage:'):
                        index = int(action.split(':')[1]) if ':' in action else 0
                        world = World(index, weapon_index=world.weapon_index, xp=world.xp, monster_echoes=world.monster_echoes)
                        screen = 'play'
                        pressed.clear()
                        accumulator = 0.0
                    elif action == 'back':
                        menu.open('main')
                    elif action == 'audio':
                        volume = 0 if menu.muted else round(menu.volume * 128 / 100)
                        canvas.Mix_Volume(-1, volume)
                        canvas.Mix_VolumeMusic(volume)
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
                if screen == 'play' and world.pending_monster_echo:
                    if key in (SDLK_0 + 1, SDLK_0 + 2):
                        world.resolve_monster_echo(key - SDLK_0 - 1)
                    elif key in (SDLK_0 + 3, SDLK_ESCAPE, SDLK_BACKSPACE):
                        world.resolve_monster_echo()
                    pressed.clear()
                    pending_stairs = 0
                    pending_jump = False
                    pending_attack = False
                    accumulator = 0.0
                    continue
                if screen == 'play' and world.echo_selecting:
                    if key == SDLK_0 + 1:
                        world.start_recording()
                    elif SDLK_0 + 2 <= key <= SDLK_0 + 3:
                        slot = key - SDLK_0 - 2
                        if slot < len(world.monster_echoes):
                            world.start_recording(world.monster_echoes[slot])
                    elif key in (SDLK_ESCAPE, SDLK_BACKSPACE):
                        world.echo_selecting = False
                    pressed.clear()
                    pending_stairs = 0
                    pending_jump = False
                    pending_attack = False
                    accumulator = 0.0
                    continue
                if boss_selector is not None:
                    choice = boss_selector.handle(key)
                    if choice == 'cancel':
                        boss_selector = None
                    elif choice is not None:
                        world = World(choice, weapon_index=world.weapon_index, xp=world.xp, monster_echoes=world.monster_echoes)
                        world.warp_to_boss()
                        screen = 'play'
                        boss_selector = None
                    accumulator = 0.0
                    continue
                if stage_entry is not None:
                    if key == SDLK_ESCAPE or key == SDLK_p:
                        stage_entry = None
                    elif key == SDLK_BACKSPACE:
                        stage_entry = stage_entry[:-1]
                    elif SDLK_0 <= key <= SDLK_9 and len(stage_entry) < len(str(len(STAGE_GROUPS))):
                        stage_entry += str(key - SDLK_0)
                    elif key == SDLK_RETURN and stage_entry:
                        number = int(stage_entry)
                        if 1 <= number <= len(STAGE_GROUPS):
                            world = World(STAGE_GROUPS[number - 1][0], weapon_index=world.weapon_index, xp=world.xp, monster_echoes=world.monster_echoes)
                            screen = 'play'
                            stage_entry = None
                    accumulator = 0.0
                    continue
                if floor_entry is not None:
                    if key in (SDLK_ESCAPE, canvas.SDLK_MINUS, canvas.SDLK_KP_MINUS):
                        floor_entry = None
                    elif key == SDLK_BACKSPACE:
                        floor_entry = ''
                    elif SDLK_0 <= key <= SDLK_9:
                        floor_entry = str(key - SDLK_0)
                    elif key in (SDLK_RETURN, canvas.SDLK_KP_ENTER) and floor_entry:
                        if world.warp_to_floor(int(floor_entry) - 1):
                            floor_entry = None
                    accumulator = 0.0
                    continue
                if key in (canvas.SDLK_PLUS, canvas.SDLK_KP_PLUS, canvas.SDLK_EQUALS):
                    view.toggle_free_camera()
                    pressed.clear()
                    pending_stairs = 0
                    pending_jump = False
                    pending_attack = False
                    accumulator = 0.0
                    continue
                if view.free_camera:
                    if key == SDLK_ESCAPE:
                        view.toggle_free_camera()
                        pressed.clear()
                    elif key in (SDLK_LEFT, SDLK_RIGHT, SDLK_UP, SDLK_DOWN):
                        pressed.add(key)
                    continue
                if key in (canvas.SDLK_MINUS, canvas.SDLK_KP_MINUS):
                    floor_entry = ''
                    pressed.clear()
                    pending_stairs = 0
                    pending_jump = False
                    pending_attack = False
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
                if key == SDLK_b:
                    boss_selector = BossSelector()
                    pressed.clear()
                    pending_stairs = 0
                    pending_jump = False
                    pending_attack = False
                    accumulator = 0.0
                    continue
                if key == SDLK_r or (key == SDLK_RETURN and world.result == 'cleared'):
                    group = stage_group_index(world.index)
                    index = STAGE_GROUPS[group if key == SDLK_r else (group + 1) % len(STAGE_GROUPS)][0]
                    world = World(index, weapon_index=world.weapon_index, xp=world.xp, monster_echoes=world.monster_echoes)
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
                elif (key == SDLK_DOWN and SDLK_f in pressed and world.recording is not None
                      and world.recording.monster_kind == 'crawler'):
                    # F를 누른 채 ↓를 누르면 거미줄 조준을 취소한다. F를 떼도 발사되지 않는다.
                    pressed.discard(SDLK_f)
                    world.notify('거미줄 조준을 취소했습니다.')
                elif key in (SDLK_UP, SDLK_DOWN):
                    pending_stairs = 1 if key == SDLK_UP else -1
                    if world.recording is not None and world.recording.monster_kind == 'crawler':
                        pressed.add(key)
                elif key == SDLK_c and key not in pressed:
                    pressed.add(key)
                    if (world.recording is None and world.monster_echoes
                            and world.player.elevator_target is None
                            and world.player.jump_time <= 0 and not world.lift_riding):
                        world.echo_selecting = True
                        pressed.clear()
                        pending_stairs = 0
                        pending_jump = False
                    else:
                        world.toggle_recording()
                    pending_attack = False
                elif key == SDLK_BACKSPACE:
                    world.cancel_recording()
                elif key == SDLK_e and key not in pressed:
                    pressed.add(key)
                    world.toggle_lever()
                elif key == SDLK_d and key not in pressed:
                    pressed.add(key)
                    pending_release = True   # 거미줄에 매달려 있으면 그 자리에서 놓는다
                elif key == SDLK_f and key not in pressed:
                    pressed.add(key)
                    if world.recording is not None and world.recording.monster_kind == 'watcher':
                        pending_web = True   # 외눈 유령 분신: F로 레이더를 켜고 끈다
                elif SDLK_0 <= key <= SDLK_4:
                    world.select_weapon(key - SDLK_0)
                elif key in (SDLK_a, SDLK_s) and world.recording is None:
                    pending_attack = 'slash' if key == SDLK_a else 'thrust'

            while accumulator >= STEP:
                if screen == 'play' and stage_entry is None and boss_selector is None and floor_entry is None:
                    horizontal = int(SDLK_RIGHT in pressed) - int(SDLK_LEFT in pressed)
                    if view.free_camera:
                        vertical = int(SDLK_UP in pressed) - int(SDLK_DOWN in pressed)
                        view.move_free_camera(world, horizontal, vertical, STEP)
                        world.step(Motion())
                    else:
                        stairs = pending_stairs
                        if world.recording is not None and world.recording.monster_kind == 'crawler':
                            stairs = int(SDLK_UP in pressed) - int(SDLK_DOWN in pressed)
                        world.step(Motion(horizontal, stairs, pending_jump, pending_web,
                                          SDLK_SPACE in pressed, SDLK_f in pressed,
                                          release=pending_release), pending_attack)
                    next_world = advance_stage_section(world)
                    if next_world is not world:
                        world = next_world
                        pressed.clear()
                pending_stairs = 0
                pending_jump = False
                pending_web = False
                pending_release = False
                pending_attack = False
                accumulator -= STEP

            clear_canvas()
            view.draw(world, screen, menu)
            if screen == 'play' and world.echo_selecting:
                view.draw_echo_selector(world)
            if screen == 'play' and world.pending_monster_echo:
                view.draw_echo_replacement(world)
            if stage_entry is not None:
                view.draw_stage_selector(stage_entry)
            if floor_entry is not None:
                view.draw_floor_selector(floor_entry, world.stage.floors)
            if boss_selector is not None:
                view.draw_boss_selector(boss_selector)
            update_canvas()
            delay(0.001)
    finally:
        del view
        close_canvas()


if __name__ == '__main__':
    main()
