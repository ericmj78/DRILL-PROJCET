"""도트 몬스터(거미, 외눈 유령, 마법책, 물약 슬라임) 시트를 그린다. 시트는 PixelLab으로 만든다 (assets/PixelLab/몬스터).

원본 그림은 왼쪽을 보므로 오른쪽을 볼 때 뒤집는다. 그림 한 칸 = 화면 1px.
떠도는 유령은 외눈 유령 시트를 작게, 보랏빛 반투명으로 그린다.
"""

from pico2d import pico2d as canvas
import sdl2

from animation import draw_region

KINDS = frozenset(('crawler', 'watcher', 'tier_ghost'))
GHOST_SCALE, GHOST_TINT, GHOST_ALPHA = 0.75, (190, 170, 255), 205
HOVER = {'watcher': 4, 'magic_book': 6}   # 바닥에서 조금 떠 있는 몬스터
WINDUP, RECOVERY, STRIKE = 0.31, 0.65, 0.4   # world.py의 준비·회복 시간, 회복 중 물기 동작 길이
# 모든 몬스터 시트는 PixelLab으로 만들어 assets/PixelLab/몬스터에 따로 둔다 (tools/monster_pixel/pixellab_*.py).
# 거미 공격은 이빨 물기, 유령 떠다니기는 위아래로 둥실둥실.
SPIDER = {'sheet': 'PixelLab/몬스터/spider', 'size': (192, 112), 'feet': 106, 'center': 110}
WATCHER = {'sheet': 'PixelLab/몬스터/watcher', 'size': (112, 136), 'feet': 124, 'center': 56}
# 마법책(pixellab_book.py): 떠다니기 16칸, 공격 8칸(발톱을 치켜들었다가 책을 닫으며 할퀸다). 어느 스테이지에서나 쓴다.
BOOK = {'sheet': 'PixelLab/몬스터/book', 'size': (160, 128), 'feet': 120, 'center': 86}
# 물약 슬라임(pixellab_slime.py): 걷기 8, 공격 8(몸을 늘였다가 내리쳐 물약이 튄다), 대기 4. 줄 순서는 거미와 같다.
SLIME = {'sheet': 'PixelLab/몬스터/slime', 'size': (160, 128), 'feet': 122, 'center': 86}
# 뿔짐승(pixellab_beast.py): 걷기 8, 공격 8(머리를 낮췄다가 몸을 뻗어 덮친다), 대기 4. 줄 순서는 거미와 같다.
BEAST = {'sheet': 'PixelLab/몬스터/beast', 'size': (224, 128), 'feet': 122, 'center': 130}
WALKERS = frozenset(('crawler', 'potion_slime', 'beast'))   # 걷기·공격·대기 줄을 쓰는 몬스터 (나머지는 떠다니기 16칸)
ANYWHERE = frozenset(('magic_book', 'potion_slime', 'beast'))   # 1스테이지 밖에서도 이 시트를 쓰는 몬스터


def attack_frame(windup, recovery):
    """공격 줄의 칸 번호 (준비 0~3, 물기·덮치기 4~7). 공격 중이 아니면 None."""
    if windup > 0:
        return min(3, int((1 - windup / WINDUP) * 4))
    if recovery > RECOVERY - STRIKE:
        return 4 + min(3, int((RECOVERY - recovery) / STRIKE * 4))
    return None


class MonsterSprite:
    def __init__(self, load):
        self.meta = dict(crawler=SPIDER, watcher=WATCHER, magic_book=BOOK, potion_slime=SLIME, beast=BEAST)
        self.sheets = {(kind, echo): load(f'{info["sheet"]}{"_echo" if echo else ""}.png')
                       for kind, info in self.meta.items() for echo in (False, True)}

    def draw(self, kind, actor, floor_y, time, windup=0.0, recovery=0.0, opacity=255,
             tint=(255, 255, 255), echo=False):
        ghost = kind == 'tier_ghost'
        base = 'watcher' if ghost else kind
        info = self.meta[base]
        width, height = info['size']
        frame = attack_frame(windup, recovery)
        if frame is not None:
            row, column = 1, frame
        elif base in WALKERS:
            row, column = (0, int(actor.walk_distance / 10) % 8) if actor.moving else (2, int(time * 3) % 4)
        else:   # 떠다니기. 여러 마리가 같은 박자로 흔들리지 않게 위치로 어긋나게 한다.
            row, column = 0, int(time * 8 + actor.x * 0.05) % 16
        scale = GHOST_SCALE if ghost else 1.0
        if ghost and not echo:
            tint = tuple(min(a, b) for a, b in zip(tint, GHOST_TINT))
            opacity = min(opacity, GHOST_ALPHA)
        flip = actor.facing > 0
        center = (width - info['center']) if flip else info['center']
        bottom = floor_y - (height - info['feet']) * scale + HOVER.get(base, 0)
        image = self.sheets[(base, echo)]
        canvas.SDL_SetTextureAlphaMod(image.texture, opacity)
        canvas.SDL_SetTextureColorMod(image.texture, *tint)
        draw_region(image, (column * width, row * height, width, height),
                    actor.x - center * scale, bottom, width * scale, height * scale, flip)
        canvas.SDL_SetTextureColorMod(image.texture, 255, 255, 255)
        canvas.SDL_SetTextureAlphaMod(image.texture, 255)


class StageOneFolderMonsters(MonsterSprite):
    """1스테이지 적에게만 사용하는 도트격자 폴더 기반 시트."""

    def __init__(self, load):
        self.meta = {
            'crawler': SPIDER,
            'watcher': WATCHER,
        }
        self.sheets = {
            ('crawler', False): load(f'{SPIDER["sheet"]}.png'),
            ('watcher', False): load(f'{WATCHER["sheet"]}.png'),
        }
        for image in self.sheets.values():
            sdl2.SDL_SetTextureScaleMode(image.texture, sdl2.SDL_ScaleModeNearest)
