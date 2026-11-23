"""도트 몬스터(거미, 외눈 유령) 시트를 그린다. 시트는 tools/monster_pixel/make_monsters.py로 만든다.

원본 그림은 왼쪽을 보므로 오른쪽을 볼 때 뒤집는다. 그림 한 칸 = 화면 1px.
떠도는 유령은 외눈 유령 시트를 작게, 보랏빛 반투명으로 그린다.
"""
import json

from pico2d import pico2d as canvas
import sdl2

from animation import draw_region
from asset_paths import ASSET_ROOT

KINDS = frozenset(('crawler', 'watcher', 'tier_ghost'))
GHOST_SCALE, GHOST_TINT, GHOST_ALPHA = 0.75, (190, 170, 255), 205
HOVER = 4                      # 외눈 유령은 바닥에서 조금 떠 있다
WINDUP, RECOVERY, STRIKE = 0.31, 0.65, 0.4   # world.py의 준비·회복 시간, 회복 중 물기 동작 길이
# 거미·외눈 유령은 PixelLab 시트(tools/monster_pixel/pixellab_spider.py, pixellab_watcher.py)를 쓴다.
# 줄 순서는 같다. 거미 공격은 이빨 물기, 유령 떠다니기는 위아래로 둥실둥실.
# monster_sheets.json은 make_monsters.py가 다시 쓰므로 여기서 덮어쓴다.
SPIDER = {'sheet': 'pixellab/spider', 'size': (160, 112), 'feet': 106, 'center': 90}
WATCHER = {'sheet': 'pixellab/watcher', 'size': (112, 136), 'feet': 124, 'center': 56}


def attack_frame(windup, recovery):
    """공격 줄의 칸 번호 (준비 0~3, 물기·덮치기 4~7). 공격 중이 아니면 None."""
    if windup > 0:
        return min(3, int((1 - windup / WINDUP) * 4))
    if recovery > RECOVERY - STRIKE:
        return 4 + min(3, int((RECOVERY - recovery) / STRIKE * 4))
    return None


class MonsterSprite:
    def __init__(self, load):
        self.meta = json.loads((ASSET_ROOT / '몬스터_도트' / 'monster_sheets.json').read_text(encoding='utf-8'))
        self.meta['crawler'], self.meta['watcher'] = SPIDER, WATCHER
        self.sheets = {(kind, echo): load(f'몬스터_도트/{info["sheet"]}{"_echo" if echo else ""}.png')
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
        elif base == 'crawler':
            row, column = (0, int(actor.walk_distance / 10) % 8) if actor.moving else (2, int(time * 3) % 4)
        else:   # 떠다니기. 여러 마리가 같은 박자로 흔들리지 않게 위치로 어긋나게 한다.
            row, column = 0, int(time * 8 + actor.x * 0.05) % 16
        scale = GHOST_SCALE if ghost else 1.0
        if ghost and not echo:
            tint = tuple(min(a, b) for a, b in zip(tint, GHOST_TINT))
            opacity = min(opacity, GHOST_ALPHA)
        flip = actor.facing > 0
        center = (width - info['center']) if flip else info['center']
        bottom = floor_y - (height - info['feet']) * scale + (HOVER if base == 'watcher' else 0)
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
            ('crawler', False): load(f'몬스터_도트/{SPIDER["sheet"]}.png'),
            ('watcher', False): load(f'몬스터_도트/{WATCHER["sheet"]}.png'),
        }
        for image in self.sheets.values():
            sdl2.SDL_SetTextureScaleMode(image.texture, sdl2.SDL_ScaleModeNearest)
