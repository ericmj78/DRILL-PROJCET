"""PixelLab(PixMiniMax)으로 대마녀 2페이즈(빗자루) 시트를 만든다.

줄: 빗자루 타기 8(서 있다가 빗자루를 불러 걸터앉아 떠오른다) / 비행 8(둥실둥실 반복) / 빗자루 공격 8(급강하하며 지팡이로 베기).
비행·공격은 타기의 마지막 장면(빗자루에 앉아 떠 있는 자세)에서 시작해 그 자세로 돌아온다.
대마녀 시트(grand_witch.png)와 같은 칸(256 × 176, 게임에서 2배)이다. 빗자루는 서 있는 대마녀 팔레트에 없는 색이라
팔레트로 다시 칠하지 않는다.
사용: python tools/monster_pixel/pixellab_witch_broom.py
결과: assets/PixelLab/몬스터/grand_witch_broom.png, grand_witch_broom_echo.png
"""
from PIL import Image

from pixellab_spider import OUT, animate_pm, drop_specks, echo
from pixellab_witch import SUBJECT

W, H = 256, 176
MOUNT = (1, 'a long wooden broomstick appears under her, she sits sideways on the broom holding the crystal staff, and rises '
            'up into the air riding the broom, ending floating on the broom with her robe and hair flowing')
RIDING = {**SUBJECT, 'initial_pose': 'sitting sideways on a flying broomstick, holding the crystal staff'}
ROWS = (   # (이름, 시드, 동작). 시드 2의 타기는 마지막에 서 있는 자세로 돌아갔다
    ('fly', 1, 'hovers in the air riding the broomstick in a smooth loop, bobbing gently up and down, the robe, cape and '
               'long hair flowing in the wind, the broom bristles fluttering'),
    ('attack', 1, 'leans forward and swoops down to the left on the broomstick, swinging the crystal staff in a sweeping magic '
                  'slash with a glowing purple trail, then pulls back up to the starting pose'),
)


def build(mount, fly, attack):
    """생성 칸(0 = 입력) → 3줄 시트. 타기·공격은 1~8번, 반복하는 비행은 0~7번 칸을 쓴다."""
    sheet = Image.new('RGBA', (W * 8, H * 3), (0, 0, 0, 0))
    for row, frames in enumerate((mount[1:9], fly[:8], attack[1:9])):
        for column, frame in enumerate(frames):
            sheet.paste(drop_specks(frame, keep=4), (column * W, row * H))
    return sheet


if __name__ == '__main__':
    base = Image.open(OUT / 'grand_witch_base.png').convert('RGBA')
    mount = animate_pm(base, 8, MOUNT[0], MOUNT[1], SUBJECT)
    ride = mount[8]
    rows = {name: animate_pm(ride, 8, seed, action, RIDING) for name, seed, action in ROWS}
    sheet = build(mount, rows['fly'], rows['attack'])
    sheet.save(OUT / 'grand_witch_broom.png')
    echo(sheet).save(OUT / 'grand_witch_broom_echo.png')
