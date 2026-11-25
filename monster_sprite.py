"""도트 몬스터(거미, 외눈 유령, 마법책, 물약 슬라임, 뿔짐승, 쇠사슬 간수, 대마녀) 시트를 그린다. 시트는 PixelLab으로 만든다 (assets/PixelLab/몬스터).

원본 그림은 왼쪽을 보므로 오른쪽을 볼 때 뒤집는다. 그림 한 칸 = 화면 1px.
떠도는 유령은 외눈 유령 시트를 작게, 보랏빛 반투명으로 그린다.
"""

from pico2d import pico2d as canvas
import sdl2

from animation import draw_region
from world import BROOM_MOUNT

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
# 1스테이지 보스 쇠사슬 간수(pixellab_jailer.py): 걷기·공격·대기 다음에 기술 줄(쇠사슬, 낙석, 돌진)이 있다.
# 화면 키가 약 280이라 PixMiniMax 칸(256)에 안 들어가 절반 크기로 만들고 2배로 그린다.
JAILER = {'sheet': 'PixelLab/몬스터/jailer', 'size': (256, 176), 'feet': 170, 'center': 173, 'scale': 2,
          'skills': {'chain': 3, 'rockfall': 4, 'charge': 5}}
# 2스테이지 보스 대마녀(pixellab_witch.py): 간수와 같은 줄 배치, 기술은 중력·낙뢰·마력 구체. 2배로 그린다.
GRAND_WITCH = {'sheet': 'PixelLab/몬스터/grand_witch', 'size': (256, 176), 'feet': 170, 'center': 144, 'scale': 2,
               'skills': {'gravity': 3, 'bolts': 4, 'orb': 5, 'teleport': 3, 'laser': 4, 'homing': 5}}
# 대마녀 2페이즈(pixellab_witch_broom.py): 빗자루 타기 8(바닥에 선 채 시작해 떠오른다) / 비행 8 / 빗자루 공격 8.
# 칸과 발밑은 대마녀 시트와 같아서, 탄 자세는 발밑보다 54px(27칸 × 2) 위에 그려진다.
BROOM = {**GRAND_WITCH, 'sheet': 'PixelLab/몬스터/grand_witch_broom'}
WALKERS = frozenset(('crawler', 'potion_slime', 'beast', 'jailer_boss', 'grand_witch'))   # 걷기·공격·대기 줄을 쓰는 몬스터 (나머지는 떠다니기 16칸)
ANYWHERE = frozenset(('magic_book', 'potion_slime', 'beast', 'jailer_boss', 'grand_witch'))   # 1스테이지 밖에서도 이 시트를 쓰는 몬스터


def attack_frame(windup, recovery):
    """공격 줄의 칸 번호 (준비 0~3, 물기·덮치기 4~7). 공격 중이 아니면 None."""
    if windup > 0:
        return min(3, int((1 - windup / WINDUP) * 4))
    if recovery > RECOVERY - STRIKE:
        return 4 + min(3, int((RECOVERY - recovery) / STRIKE * 4))
    return None


def skill_frame(phase, progress):
    """기술 줄의 칸 번호: 예고 0~3, 발동 4~6, 빈틈 7(기본 자세)."""
    if phase == 'telegraph':
        return min(3, int(progress * 4))
    if phase == 'active':
        return 4 + min(2, int(progress * 3))
    return 7


class MonsterSprite:
    def __init__(self, load):
        self.meta = dict(crawler=SPIDER, watcher=WATCHER, magic_book=BOOK, potion_slime=SLIME, beast=BEAST,
                         jailer_boss=JAILER, grand_witch=GRAND_WITCH, grand_witch_broom=BROOM)
        self.sheets = {(kind, echo): load(f'{info["sheet"]}{"_echo" if echo else ""}.png')
                       for kind, info in self.meta.items() for echo in (False, True)}
        for image in self.sheets.values():   # 2배로 키우는 보스도 도트가 흐려지지 않게
            sdl2.SDL_SetTextureScaleMode(image.texture, sdl2.SDL_ScaleModeNearest)

    def draw(self, kind, actor, floor_y, time, windup=0.0, recovery=0.0, opacity=255,
             tint=(255, 255, 255), echo=False, skill=None, broom=None):
        """skill: 보스 기술 (이름, 단계, 진행도) 또는 None. 기술 줄이 있는 몬스터만 쓴다.
        broom: 대마녀가 빗자루에 오른 뒤 지난 시간 또는 None."""
        ghost = kind == 'tier_ghost'
        base = 'watcher' if ghost else 'grand_witch_broom' if broom is not None else kind
        info = self.meta[base]
        width, height = info['size']
        scale = info.get('scale', 1) * (GHOST_SCALE if ghost else 1.0)
        frame = attack_frame(windup, recovery)
        if broom is not None:   # 타기 → 비행, 기본 공격과 마법은 빗자루 공격 줄
            if broom < BROOM_MOUNT:
                row, column = 0, min(7, int(broom / BROOM_MOUNT * 8))
            elif skill is not None or frame is not None:
                row, column = 2, skill_frame(*skill[1:]) if skill is not None else frame
            else:
                row, column = 1, int(time * 8) % 8
        elif skill is not None and skill[0] in info.get('skills', {}):
            row, column = info['skills'][skill[0]], skill_frame(*skill[1:])
        elif frame is not None:
            row, column = 1, frame
        elif base in WALKERS:   # 크게 그리는 몬스터는 보폭도 그만큼 길다
            row, column = (0, int(actor.walk_distance / (10 * scale)) % 8) if actor.moving else (2, int(time * 3) % 4)
        else:   # 떠다니기. 여러 마리가 같은 박자로 흔들리지 않게 위치로 어긋나게 한다.
            row, column = 0, int(time * 8 + actor.x * 0.05) % 16
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
