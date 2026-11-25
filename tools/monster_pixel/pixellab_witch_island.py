"""PixelLab API로 대마녀의 방 하늘 섬(날개 달린 보라 석판, 눈과 이빨) 날갯짓 시트를 만든다.

방법은 3스테이지 하늘 섬(pixellab_sky_island.py)과 같다:
1) image-to-pixelart-pro → 가장자리에서 이어진 배경만 지운다 (이빨·금장식이 밝아 색으로 지우면 같이 지워진다)
2) 돌 윗면(Pro 결과의 x 35~248)이 게임의 밟는 폭 150이 되게 평균 축소 + Pro 팔레트
3) animate-pixminimax 날갯짓 (시드 1·2 중 날개를 더 크게 치는 2), 돌 부분(LOCK 열)은 모든 칸 고정
사용: python tools/monster_pixel/pixellab_witch_island.py <원본 일러스트.png>
결과: assets/PixelLab/스테이지/witch_island.png (가로 8칸, 한 칸 224 × 96, 돌 윗면 35줄)
"""
import sys

from PIL import Image

from pixellab_spider import OUT, b64, call, to_palette, unb64, wait

DIR = OUT.parent / '스테이지'
W, H, TOP = 224, 96, 30
SLAB, WIDTH = (35, 248), 150   # Pro 결과에서 돌 윗면 x 범위 → 게임 폭
LOCK = (34, 191)               # 날개를 뺀 돌 부분 열
FLAP = ('the two feathered wings on the left and right ends flap up and down like a bird in a smooth loop, '
        'the stone platform with the eyes and fangs in the middle stays completely still')


def make_base(src_path):
    src = Image.open(src_path).convert('RGBA')
    solid = src.getchannel('A').point(lambda v: 255 if v > 128 else 0)
    box = solid.getbbox()
    body = src.crop(box)
    body.putalpha(solid.crop(box))
    pad = Image.new('RGBA', (body.width + 80, body.height + 80), (0, 0, 0, 0))
    pad.paste(body, (40, 40))
    img = unb64(wait(call('POST', '/image-to-pixelart-pro', {
        'image': b64(pad), 'seed': 1,
        'description': 'floating purple stone sky island platform with feathered wings, glowing eyes and fangs, '
                       'gold ornaments, crisp dark outline, side view game sprite'}))['image'])
    px = img.load()
    bg = px[0, 0]
    stack = [(x, y) for x in range(img.width) for y in (0, img.height - 1)]
    stack += [(x, y) for y in range(img.height) for x in (0, img.width - 1)]
    seen = set()
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < img.width and 0 <= y < img.height) or \
                any(abs(px[x, y][i] - bg[i]) > 6 for i in range(3)):
            continue
        seen.add((x, y))
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    for p in seen:
        px[p] = (0, 0, 0, 0)
    img = img.crop(img.getbbox())
    palette = sorted({c[:3] for c in img.get_flattened_data() if c[3]})
    k = WIDTH / (SLAB[1] - SLAB[0])
    small = img.resize((round(img.width * k), round(img.height * k)), Image.BOX)
    small.putalpha(small.getchannel('A').point(lambda v: 255 if v > 110 else 0))
    base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    base.paste(to_palette(small, palette), ((W - small.width) // 2, TOP))
    return base


def build_sheet(base, frames):
    sheet = Image.new('RGBA', (W * 8, H), (0, 0, 0, 0))
    stone = base.crop((LOCK[0], 0, LOCK[1], H))
    for column, frame in enumerate(frames[:8]):
        frame = frame.copy()
        frame.paste(stone, (LOCK[0], 0))
        sheet.paste(frame, (column * W, 0))
    return sheet


if __name__ == '__main__':
    base = make_base(sys.argv[1])
    frames = [unb64(i) for i in wait(call('POST', '/animate-pixminimax', {
        'first_frame': b64(base), 'last_frame': b64(base), 'description': FLAP,
        'subject_description': 'a floating purple stone sky island platform with a feathered wing on each end',
        'view': 'side', 'frame_count': 8, 'seed': 2, 'no_background': True}))['images']]
    build_sheet(base, frames).save(DIR / 'witch_island.png')
