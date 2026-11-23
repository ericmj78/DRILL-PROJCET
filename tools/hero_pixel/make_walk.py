"""사용자가 그린 걷기 그림으로 주인공 걷기 시트를 만든다: python tools/hero_pixel/make_walk.py

walk_source/walk_0.png ~ walk_8.png (128 × 128, 그림 한 칸 = 화면 1px, 발밑 124줄, 제자리 걷기).
walk_8은 walk_0과 거의 같은 서 있는 자세라서 0~7을 한 바퀴로 쓴다.

걷기 그림은 키가 106px로 대기·공격 그림(92px)보다 길쭉하다. 그대로 쓰면 걸을 때마다
캐릭터가 길어 보이므로, 얼굴은 그대로 두고 목 아래 몸통·다리에서 가로줄을 고르게 빼
키를 92px에 맞춘다. 모든 프레임에서 같은 줄을 빼서 걷는 동작이 흔들리지 않는다.
(통째로 줄이면 도트가 뭉개진다.)

결과: assets/주인공_도트/hero_walk.png, hero_walk_echo.png (8칸 가로, 발밑 124줄 그대로)
"""
from pathlib import Path

from PIL import Image

from make_hero import echo

HERE = Path(__file__).resolve().parent
TARGET = HERE.parent.parent / 'assets' / '주인공_도트'
FRAMES, SIZE = 8, 128
FEET = 124                 # 발밑 (이 줄 위가 그림)
NECK = 54                  # 이 줄 위(머리)는 줄을 빼지 않는다
HEIGHT_NOW, HEIGHT_GOAL = 106, 92   # 걷기 그림 키 → 대기·공격 그림 키


def removed_rows():
    """목 아래부터 발 바로 위까지 고르게 뺄 줄 번호."""
    count = HEIGHT_NOW - HEIGHT_GOAL
    span = FEET - 3 - NECK          # 발바닥 세 줄은 남긴다
    return {NECK + round((k + 0.5) * span / count) for k in range(count)}


def squash(frame, remove):
    """remove 줄을 빼고 남은 줄을 발밑에 맞춰 아래로 붙인다."""
    out = Image.new('RGBA', frame.size)
    target = FEET - 1
    for y in range(FEET - 1, -1, -1):
        if y in remove:
            continue
        out.paste(frame.crop((0, y, SIZE, y + 1)), (0, target))
        target -= 1
    return out


def main():
    remove = removed_rows()
    sheet = Image.new('RGBA', (SIZE * FRAMES, SIZE))
    for index in range(FRAMES):
        frame = Image.open(HERE / 'walk_source' / f'walk_{index}.png').convert('RGBA')
        sheet.alpha_composite(squash(frame, remove), (SIZE * index, 0))
    sheet.save(TARGET / 'hero_walk.png')
    echo(sheet).save(TARGET / 'hero_walk_echo.png')
    box = sheet.crop((0, 0, SIZE, SIZE)).getbbox()
    assert box[3] == FEET and abs(box[3] - box[1] - HEIGHT_GOAL) <= 2, box   # 원본 키가 프레임마다 104~106px
    print('saved hero_walk.png', sheet.size, 'height', box[3] - box[1], 'removed rows', sorted(remove))


if __name__ == '__main__':
    main()
