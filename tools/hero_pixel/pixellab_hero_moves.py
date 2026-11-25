"""PixelLab(PixMiniMax)으로 주인공 1단 점프·2단 점프·대시 시트를 만든다.

- 점프(시드 1): 웅크림 → 무릎을 당겨 도약 → 정점 → 다리를 뻗어 착지 (마지막 칸 = 기본 자세)
- 2단 점프(시드 1): 공중에서 앞으로 한 바퀴 돌고 흰 초승달 궤적, 발밑에 바람이 터진다
- 대시(시드 2): 낮게 숙여 돌진, 흰 속도선과 바람 자국 (시드 1은 회색 사각형이 생겼다)
PixelLab이 캐릭터를 칸 안에서 위로 올려 그리므로, 칸마다 몸(흰 효과 제외)의 아래쪽을 발밑 줄에 맞춘다.
높이는 게임 물리(jump_height)가 준다.
사용: python tools/hero_pixel/pixellab_hero_moves.py
결과: assets/PixelLab/주인공/hero_{jump,double_jump,dash}_sheet.png, _echo.png (가로 9칸, 160 × 160, 대시만 224 × 160)
"""
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'monster_pixel'))
from pixellab_hero_anims import OUT, drop_specks, to_palette  # noqa: E402
from make_hero import echo  # noqa: E402
from pixellab_spider import b64, call, unb64, wait  # noqa: E402

FEET = 156
SUBJECT = {'subject_description': 'a young swordsman with dark messy hair, a navy hooded cloak and brown boots, '
                                  'holding a sword low in his right hand',
           'initial_pose': 'standing upright holding the sword low', 'direction': 'east', 'view': 'side'}
MOVES = {   # 이름: (칸 폭, 캐릭터 x, 시드, 마지막 칸을 기본 자세로 고정, 동작)
    'jump': (160, 16, 1, True, 'crouches down, then springs powerfully upward with knees tucked and the cloak billowing below, '
                               'reaches the top of the jump, then comes down with legs extended and lands softly back in the starting pose'),
    'double_jump': (160, 16, 1, False, 'in mid-air he does a fast forward somersault, curling his body into a ball and spinning one full turn '
                                       'with the cloak wrapping around him, a burst of white wind and feathers puffs out under his feet, then he uncurls'),
    'dash': (224, 80, 2, True, 'dashes forward to the right very fast in a low lean, body almost horizontal, the cloak streaming straight back, '
                               'bright white speed lines and a wind streak trail behind him, then straightens up'),
}


def ground(frame):
    """몸(흰 효과 제외)의 아래쪽을 발밑 줄에 맞춘다."""
    a = frame.load()
    rows = [y for y in range(frame.height) for x in range(frame.width) if a[x, y][3] and min(a[x, y][:3]) < 200]
    if not rows:
        return frame
    out = Image.new('RGBA', frame.size, (0, 0, 0, 0))
    out.paste(frame, (0, FEET - 1 - max(rows)))
    return out


def build(name, frames, palette):
    """생성 칸(0 = 입력) → 9칸 시트. 2단 점프는 공중에서 시작하므로 서 있는 0번 칸을 빼고 마지막 칸을 한 번 더 쓴다."""
    frames = frames[1:9] + frames[8:9] if name == 'double_jump' else frames[:9]
    width = frames[0].width
    sheet = Image.new('RGBA', (width * 9, 160), (0, 0, 0, 0))
    for column, frame in enumerate(frames):
        sheet.paste(ground(drop_specks(to_palette(frame, palette), keep=4)), (column * width, 0))
    return sheet


if __name__ == '__main__':
    hero = Image.open(OUT / 'hero_base.png').convert('RGBA')   # 128칸, 발밑 124줄
    palette = sorted({c[:3] for c in hero.get_flattened_data() if c[3]})
    for name, (width, x, seed, lock_end, action) in MOVES.items():
        base = Image.new('RGBA', (width, 160), (0, 0, 0, 0))
        base.paste(hero, (x, 32))
        body = {**SUBJECT, 'first_frame': b64(base), 'description': action, 'frame_count': 8, 'seed': seed,
                'no_background': True}
        if lock_end:
            body['last_frame'] = b64(base)
        frames = [unb64(i) for i in wait(call('POST', '/animate-pixminimax', body))['images']]
        sheet = build(name, frames, palette)
        sheet.save(OUT / f'hero_{name}_sheet.png')
        echo(sheet).save(OUT / f'hero_{name}_echo.png')
