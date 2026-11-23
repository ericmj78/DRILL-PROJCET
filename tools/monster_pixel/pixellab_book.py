"""PixelLab API로 마법책 도트 시트(떠다니기 16, 공격 8)를 만든다.

1) image-to-pixelart-pro: 일러스트를 도트로 (도트 크기는 PixelLab이 정한다, 폭 약 170)
2) resize: 도트 느낌을 지키며 폭 100으로 줄인다
3) animate-pixminimax: 떠다니기·공격 (마지막 칸을 기본 자세로 고정)
사용: python tools/monster_pixel/pixellab_book.py [원본 일러스트.png]
  원본을 주면 기본 도트(book_base.png)부터 새로 만들고, 없으면 있는 기본 도트로 동작만 만든다.
결과: assets/PixelLab/몬스터/book.png, book_echo.png (한 칸 160 × 128, 앞을 봄. 덮치는 쪽은 왼쪽)
필요: 환경변수 PIXELLAB_TOKEN
"""
import sys
from math import pi, sin

from PIL import Image

from pixellab_spider import OUT, b64, call, drop_specks, echo, lunge, to_palette, unb64, wait

W, H = 160, 128
BOTTOM, LEFT = 120, 36     # 기본 자세의 아래 끝 줄, 몸 왼쪽 끝 (덮칠 왼쪽과 떠오를 위쪽에 여유)
WIDTH = 100                # 책(발톱 포함) 폭
BOB = 4                    # 떠다니기 한 바퀴(16칸) 동안 위아래로 움직이는 폭(px)
PRO_LOOK = 'floating evil magic spellbook monster game sprite, crisp dark outline, glowing blue eyes on the pages, ghostly blue claw hands, gold trim'
LOOK = 'floating evil magic spellbook monster, glowing blue eyes on the pages, ghostly blue claw hands, gold trim, front view'
SUBJECT = {'subject_description': 'a floating evil spellbook with glowing blue eyes on its pages and ghostly blue claw hands',
           'initial_pose': 'floating open with both ghostly claws spread out', 'direction': 'south'}
ROWS = (                   # 줄 순서는 monster_sprite.py와 같다: 떠다니기, 공격 / (이름, 칸 수, 시드, 동작)
    ('float', 16, 1, 'hovers in place, the pages flutter gently, the ghostly claw hands sway slowly and the blue wisps drift, a smooth looping idle'),
    ('attack', 8, 2, 'leans back and raises both ghostly claw hands, then lunges forward and slashes down hard with both claws while the pages snap together like jaws, then settles back'),
)
# 공격 줄 칸마다 몸을 옮기는 양(+ 뒤, - 앞=왼쪽). PixelLab은 몸을 거의 제자리에 둬서 덮치는 이동은 코드로 준다.
LUNGE = (2, 4, 6, 6, -10, -16, -10, -4)


def clear_white(img):
    """흰 배경을 지운다: 흰 덩어리 중 가장자리에 닿거나 6픽셀 이상인 것 (1~5픽셀짜리 눈 반짝이는 남긴다)."""
    px = img.load()
    w, h = img.size
    seen = set()
    for sy in range(h):
        for sx in range(w):
            if (sx, sy) in seen or not (px[sx, sy][3] and min(px[sx, sy][:3]) >= 240):
                continue
            group, stack = [], [(sx, sy)]
            seen.add((sx, sy))
            while stack:
                x, y = stack.pop()
                group.append((x, y))
                for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= n[0] < w and 0 <= n[1] < h and n not in seen and px[n][3] and min(px[n][:3]) >= 240:
                        seen.add(n)
                        stack.append(n)
            if len(group) >= 6 or any(x in (0, w - 1) or y in (0, h - 1) for x, y in group):
                for p in group:
                    px[p] = (0, 0, 0, 0)
    return img.crop(img.getbbox())


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


def animate_pm(base, count, seed, action):
    """PixMiniMax. 마지막 칸을 기본 자세로 고정한다 (떠다니기는 끊김 없이 반복, 공격은 제자리로 돌아온다).
    돌려받는 칸: 0 = 입력, 1..count = 생성 (count번째 = 기본 자세)."""
    return [unb64(i) for i in wait(call('POST', '/animate-pixminimax', {
        **SUBJECT, 'first_frame': b64(base), 'last_frame': b64(base), 'description': action,
        'frame_count': count, 'seed': seed, 'no_background': True}))['images']]


def shift(frame, dy):
    out = Image.new('RGBA', frame.size, (0, 0, 0, 0))
    out.paste(frame, (0, dy))
    return out


def build_sheet(base, rows):
    """rows: 이름 → animate_pm 결과. 떠다니기는 0~15번(16번 = 0번이라 뺀다), 공격은 1~8번을 쓴다."""
    palette = sorted({c[:3] for c in base.get_flattened_data() if c[3]})
    sheet = Image.new('RGBA', (W * 16, H * len(ROWS)), (0, 0, 0, 0))
    for row, (name, count, _, _) in enumerate(ROWS):
        frames = rows[name][:count] if name == 'float' else rows[name][1:count + 1]
        for column, frame in enumerate(frames):
            frame = drop_specks(to_palette(frame, palette), keep=30)
            if name == 'float':   # 둥실둥실: 한 바퀴에 한 번 위로 올라갔다 내려온다
                frame = shift(frame, round(-BOB * sin(2 * pi * column / count)))
            else:
                frame = lunge(frame, LUNGE[column])
            sheet.paste(frame, (column * W, row * H))
    return sheet


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    base_path = OUT / 'book_base.png'
    if len(sys.argv) > 1:
        make_base(sys.argv[1]).save(base_path)
        print('base saved')
    base = Image.open(base_path).convert('RGBA')
    rows = {name: animate_pm(base, count, seed, action) for name, count, seed, action in ROWS}
    sheet = build_sheet(base, rows)
    sheet.save(OUT / 'book.png')
    echo(sheet).save(OUT / 'book_echo.png')
