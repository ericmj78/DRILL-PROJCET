"""PixelLab API로 물약 슬라임 도트 시트(걷기 8, 공격 8, 대기 4)와 지나간 자리에 남는 물약 자국을 만든다.

1) image-to-pixelart-pro: 일러스트를 도트로 (도트 크기는 PixelLab이 정한다, 폭 약 120)
2) resize: 도트 느낌을 지키며 폭 100으로 줄인다
3) animate-pixminimax: 걷기·공격·대기 (마지막 칸을 기본 자세로 고정)
4) create-image-pixflux: 바닥에 남는 물약 자국 (슬라임 팔레트)
사용: python tools/monster_pixel/pixellab_slime.py [원본 일러스트.png]
  원본을 주면 기본 도트(slime_base.png)부터 새로 만들고, 없으면 있는 기본 도트로 동작과 자국만 만든다.
결과: assets/PixelLab/몬스터/slime.png, slime_echo.png (한 칸 160 × 128, 덮치는 쪽은 왼쪽), slime_puddle.png
필요: 환경변수 PIXELLAB_TOKEN
"""
import sys

from PIL import Image

from pixellab_book import clear_white
from pixellab_spider import OUT, b64, call, drop_specks, echo, lunge, to_palette, unb64, wait

W, H = 160, 128
BOTTOM, LEFT = 122, 36     # 기본 자세의 발밑 줄, 몸 왼쪽 끝 (덮칠 왼쪽과 솟을 위쪽에 여유)
WIDTH = 100                # 슬라임(팔 포함) 폭
PRO_LOOK = 'green potion slime monster game sprite, crisp dark outline, broken glass bottle neck on its head, yellow eyes, glossy bubbles'
LOOK = 'green potion slime monster with a broken glass bottle neck on its head, yellow eyes, glossy bubbles'
SUBJECT = {'subject_description': 'a green potion slime monster with a broken glass bottle neck and cork on its head',
           'initial_pose': 'standing as a gooey blob with both slimy arms spread out', 'direction': 'south'}
ROWS = (                   # 줄 순서는 monster_sprite.py와 같다: 걷기, 공격, 대기 / (이름, 칸 수, 시드, 동작)
    ('walk', 8, 1, 'oozes forward in place with a looping slither, the gooey body squashes down and stretches up, slime drips from its arms, the bubbles bob'),
    ('attack', 8, 2, 'stretches up tall and pulls both slimy arms back, then lunges forward and slams both arms down with a big splash of potion, then oozes back into shape'),
    ('idle', 4, 1, 'wobbles gently in place like jelly, the bubbles drift, the cork bobs above the bottle'),
)
PUDDLE = 'a flat thin puddle of spilled green potion slime on the ground, wide flat ellipse lying flat on the floor, glossy highlight, splash droplets around the edge'
PUDDLE_SEED = 2
# 공격 줄 칸마다 몸을 옮기는 양(+ 뒤, - 앞=왼쪽). PixelLab은 몸을 거의 제자리에 둬서 덮치는 이동은 코드로 준다.
# 내리친 뒤(5~8칸)는 물보라가 칸 끝까지 퍼져서 조금만 옮긴다.
LUNGE = (2, 4, 6, 6, -10, -6, -3, -2)


def make_base(src_path):
    src = Image.open(src_path).convert('RGBA')
    solid = src.getchannel('A').point(lambda v: 255 if v > 128 else 0)   # 원본의 옅은 얼룩은 버린다
    box = solid.getbbox()
    body = src.crop(box)
    body.putalpha(solid.crop(box))
    pad = Image.new('RGBA', (body.width + 80, body.height + 80), (0, 0, 0, 0))
    pad.paste(body, (40, 40))
    img = unb64(wait(call('POST', '/image-to-pixelart-pro', {'image': b64(pad), 'seed': 1, 'description': PRO_LOOK}))['image'])
    img = clear_white(img.convert('RGBA'))
    size = {'width': WIDTH, 'height': round(img.height * WIDTH / img.width)}
    img = unb64(call('POST', '/resize', {
        'description': LOOK, 'reference_image': b64(img),
        'reference_image_size': {'width': img.width, 'height': img.height}, 'target_size': size,
        'no_background': True, 'color_image': b64(img), 'seed': 1})['image'])
    img = clear_white(img)
    base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    base.paste(img, (LEFT, BOTTOM - img.height))
    return base


def make_puddle(base):
    """바닥에 납작하게 남는 물약 자국. 슬라임 팔레트만 쓴다."""
    # '돌바닥 위'라고 쓰면 바닥 돌과 파이프까지 그리고, 옆 시점이면 볼록한 덩어리가 된다. 낮은 위 시점으로 웅덩이만 그린다.
    img = unb64(call('POST', '/create-image-pixflux', {
        'description': PUDDLE, 'image_size': {'width': 64, 'height': 32}, 'view': 'low top-down',
        'no_background': True, 'color_image': b64(base), 'seed': PUDDLE_SEED})['image'])
    return img.crop(img.getbbox())


def animate_pm(base, count, seed, action):
    """PixMiniMax. 마지막 칸을 기본 자세로 고정한다. 돌려받는 칸: 0 = 입력, 1..count = 생성 (count번째 = 기본 자세)."""
    return [unb64(i) for i in wait(call('POST', '/animate-pixminimax', {
        **SUBJECT, 'first_frame': b64(base), 'last_frame': b64(base), 'description': action,
        'frame_count': count, 'seed': seed, 'no_background': True}))['images']]


def build_sheet(base, rows):
    """rows: 이름 → animate_pm 결과. 걷기·대기는 0번부터(마지막 = 0번이라 뺀다), 공격은 1번부터 쓴다."""
    palette = sorted({c[:3] for c in base.get_flattened_data() if c[3]})
    sheet = Image.new('RGBA', (W * 8, H * len(ROWS)), (0, 0, 0, 0))
    for row, (name, count, _, _) in enumerate(ROWS):
        frames = rows[name][1:count + 1] if name == 'attack' else rows[name][:count]
        for column, frame in enumerate(frames):
            frame = drop_specks(to_palette(frame, palette), keep=6)   # 떨어지는 방울은 작아서 6픽셀까지 남긴다
            if name == 'attack':
                frame = lunge(frame, LUNGE[column])
            sheet.paste(frame, (column * W, row * H))
    return sheet


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    base_path = OUT / 'slime_base.png'
    if len(sys.argv) > 1:
        make_base(sys.argv[1]).save(base_path)
        print('base saved')
    base = Image.open(base_path).convert('RGBA')
    make_puddle(base).save(OUT / 'slime_puddle.png')
    rows = {name: animate_pm(base, count, seed, action) for name, count, seed, action in ROWS}
    sheet = build_sheet(base, rows)
    sheet.save(OUT / 'slime.png')
    echo(sheet).save(OUT / 'slime_echo.png')
