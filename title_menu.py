"""타이틀 화면 메뉴. 버튼 배치와 키보드·마우스 선택을 맡고, 그리기는 view.py가 한다.

좌표는 게임 화면 좌표(왼쪽 아래가 0, 0)이며 버튼은 (left, bottom, right, top)이다.
"""
from pico2d import (
    SDL_BUTTON_LEFT, SDL_KEYDOWN, SDL_MOUSEBUTTONDOWN, SDL_MOUSEMOTION,
    SDLK_0, SDLK_9, SDLK_DOWN, SDLK_ESCAPE, SDLK_LEFT, SDLK_RETURN, SDLK_RIGHT, SDLK_SPACE, SDLK_UP, SDLK_b,
)

from stages import BOSS_KINDS, STAGES

MAIN = (
    ('start', '게임 시작'), ('stages', '스테이지 선택'), ('controls', '조작법'),
    ('settings', '설정'), ('quit', '게임 종료'),
)
PAGE_TITLES = {'stages': '스테이지 선택', 'controls': '조작법', 'settings': '설정'}
CONTROLS = (
    ('← →', '이동'), ('Space', '점프'), ('↑ ↓', '사다리 · 승강기'), ('C', '분신 녹화 시작 / 재현'),
    ('Backspace', '녹화 취소'), ('A / S', '베기 / 찌르기'), ('E', '레버'), ('0 – 4', '무기 바꾸기'),
    ('R', '스테이지 다시 시작'), ('P', '스테이지 바로 이동'), ('B', '보스방으로 바로 이동'), ('Esc', '타이틀 화면으로'),
)
BACK = ('back', '뒤로', (90, 70, 260, 112))
MOVES = {SDLK_UP: (0, -1), SDLK_DOWN: (0, 1), SDLK_LEFT: (-1, 0), SDLK_RIGHT: (1, 0)}


class BossSelector:
    def __init__(self):
        self.stages = [i for i, stage in enumerate(STAGES)
                       if any(enemy.kind in BOSS_KINDS for enemy in stage.enemies)]
        self.index = 0

    def handle(self, key):
        if key in (SDLK_ESCAPE, SDLK_b):
            return 'cancel'
        if not self.stages:
            return None
        if key in (SDLK_UP, SDLK_LEFT):
            self.index = (self.index - 1) % len(self.stages)
        elif key in (SDLK_DOWN, SDLK_RIGHT):
            self.index = (self.index + 1) % len(self.stages)
        elif key in (SDLK_RETURN, SDLK_SPACE):
            return self.stages[self.index]
        elif SDLK_0 < key <= SDLK_9:
            selected = key - SDLK_0 - 1
            if selected < len(self.stages):
                return self.stages[selected]
        return None


class TitleMenu:
    def __init__(self):
        self.page = 'main'
        self.index = 0
        self.fullscreen = True

    def open(self, page):
        self.page = page
        self.index = 0

    def buttons(self):
        """지금 페이지의 (동작, 글자, 버튼 사각형) 목록."""
        if self.page == 'main':
            return [(action, label, (62, 212 - row * 42, 330, 246 - row * 42))
                    for row, (action, label) in enumerate(MAIN)]
        if self.page == 'stages':
            return [(f'stage:{index}', stage.title,
                     (90 + index % 5 * 192, 400 - index // 5 * 150, 262 + index % 5 * 192, 520 - index // 5 * 150))
                    for index, stage in enumerate(STAGES)] + [BACK]
        if self.page == 'settings':
            return [('fullscreen', '화면 모드', (90, 500, 620, 552)), BACK]
        return [BACK]

    def move(self, dx, dy):
        # 스테이지 카드는 한 줄에 5장이라 위아래로 5칸씩 움직인다.
        step = dx + dy * (5 if self.page == 'stages' else 1)
        self.index = max(0, min(len(self.buttons()) - 1, self.index + step))

    def point(self, x, y):
        """(x, y) 아래의 버튼을 선택하고 그 동작을 돌려준다. 버튼이 없으면 None."""
        for index, (action, _, (left, bottom, right, top)) in enumerate(self.buttons()):
            if left <= x <= right and bottom <= y <= top:
                self.index = index
                return action
        return None

    def handle(self, event):
        """이벤트 하나를 처리하고, 실행할 동작이 생기면 돌려준다. 마우스 y는 아래가 0이어야 한다."""
        if event.type == SDL_MOUSEMOTION:
            self.point(event.x, event.y)
            return None
        if event.type == SDL_MOUSEBUTTONDOWN:
            return self.point(event.x, event.y) if event.button == SDL_BUTTON_LEFT else None
        if event.type != SDL_KEYDOWN:
            return None
        action = self.buttons()[self.index][0]
        if event.key in (SDLK_LEFT, SDLK_RIGHT) and action == 'fullscreen':
            return action
        if event.key in MOVES:
            self.move(*MOVES[event.key])
            return None
        if event.key in (SDLK_RETURN, SDLK_SPACE):
            return action
        if event.key == SDLK_ESCAPE:
            return 'quit' if self.page == 'main' else 'back'
        return None


if __name__ == '__main__':
    from types import SimpleNamespace as Event

    def key(code):
        return Event(type=SDL_KEYDOWN, key=code)

    menu = TitleMenu()
    assert menu.handle(key(SDLK_RETURN)) == 'start'
    menu.handle(key(SDLK_DOWN))
    assert menu.handle(key(SDLK_RETURN)) == 'stages'
    menu.open('stages')
    menu.handle(key(SDLK_DOWN))           # 1번 카드 → 6번 카드
    menu.handle(key(SDLK_RIGHT))
    assert menu.handle(key(SDLK_RETURN)) == 'stage:6'
    menu.handle(key(SDLK_DOWN))           # 마지막 줄 아래는 '뒤로'
    assert menu.handle(key(SDLK_RETURN)) == 'back'
    assert menu.handle(key(SDLK_ESCAPE)) == 'back'
    # 마우스: 3번 카드 가운데를 가리키고 클릭
    left, bottom, right, top = menu.buttons()[2][2]
    menu.handle(Event(type=SDL_MOUSEMOTION, x=(left + right) / 2, y=(bottom + top) / 2))
    assert menu.index == 2
    assert menu.handle(Event(type=SDL_MOUSEBUTTONDOWN, button=SDL_BUTTON_LEFT, x=left + 1, y=bottom + 1)) == 'stage:2'
    assert menu.handle(Event(type=SDL_MOUSEBUTTONDOWN, button=SDL_BUTTON_LEFT, x=5, y=5)) is None
    menu.open('main')
    assert menu.handle(key(SDLK_ESCAPE)) == 'quit'
    print('title menu ok')
