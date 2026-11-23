"""PixelLab API로 외눈 유령 도트 시트(떠다니기 16, 공격 8)를 만든다.

사용: python tools/monster_pixel/pixellab_watcher.py [원본 일러스트.png]
  원본을 주면 기본 도트(watcher_base.png)부터 새로 만들고, 없으면 있는 기본 도트로 동작만 만든다.
결과: assets/PixelLab/몬스터/watcher.png, watcher_echo.png (한 칸 112 × 136, 왼쪽을 봄)
필요: 환경변수 PIXELLAB_TOKEN
"""
import sys
from math import pi, sin

from PIL import Image

from pixellab_spider import OUT, animate, drop_specks, echo, lunge, pixelize, to_palette

W, H = 112, 136
BOTTOM = 124               # 기본 자세의 촉수 끝 줄 (위아래로 떠다닐 여유를 둔다)
BOB = 4                    # 떠다니기 한 바퀴(16칸) 동안 위아래로 움직이는 폭(px)
ROWS = (                   # 줄 순서는 monster_sprite.py와 같다: 떠다니기, 공격 / (이름, 칸 수, 시드, 동작)
    ('float', 16, 0, 'floating one-eyed ghost hovering in place, tentacles and ragged cloak gently waving and swaying, eye blinks once, side view facing left'),
    # 처음 지시(눈을 부릅뜨고 들이받기)는 파란 불꽃 오라만 커지고 돌아오지 않았다. 시드 3·13·23 중 3을 골랐다.
    ('attack', 8, 3, 'one-eyed ghost ram attack: it shrinks back and tilts away, then dashes forward to the left and rams with its horned head, then floats back to its starting pose. no fire, no glow, no aura, no effects, the body keeps its colors. side view'),
)
# 공격 줄 칸마다 몸을 옮기는 양(+ 뒤, - 앞=왼쪽). PixelLab은 몸을 거의 제자리에 둬서 들이받는 이동은 코드로 준다.
RAM = (2, 4, 6, 6, -8, -14, -8, -2)


def make_base(src_path):
    img = pixelize(src_path, height=100)
    base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    base.paste(img, ((W - img.width) // 2, BOTTOM - img.height))
    return base


def shift(frame, dy):
    out = Image.new('RGBA', frame.size, (0, 0, 0, 0))
    out.paste(frame, (0, dy))
    return out


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    base_path = OUT / 'watcher_base.png'
    if len(sys.argv) > 1:
        make_base(sys.argv[1]).save(base_path)
        print('base saved')
    base = Image.open(base_path).convert('RGBA')
    palette = sorted({c[:3] for c in base.get_flattened_data() if c[3]})
    sheet = Image.new('RGBA', (W * 16, H * len(ROWS)), (0, 0, 0, 0))
    for row, (name, count, seed, action) in enumerate(ROWS):
        # 마지막 칸을 기본 자세로 고정한다: 떠다니기는 끊김 없이 반복되고, 공격은 떠다니기로 자연스럽게 돌아간다.
        frames = animate(base, name, count, action, seed, last_frame=base)
        frames = frames[:count] if name == 'float' else frames[1:]   # 떠다니기는 마지막(=첫 칸)을, 공격은 첫 칸을 뺀다
        for column, frame in enumerate(frames[:count]):
            frame = drop_specks(to_palette(frame, palette), keep=30)
            if name == 'float':   # 둥실둥실: 한 바퀴에 한 번 위로 올라갔다 내려온다
                frame = shift(frame, round(-BOB * sin(2 * pi * column / count)))
            else:
                frame = lunge(frame, RAM[column])
            sheet.paste(frame, (column * W, row * H))
        print(name, len(frames))
    sheet.save(OUT / 'watcher.png')
    echo(sheet).save(OUT / 'watcher_echo.png')
