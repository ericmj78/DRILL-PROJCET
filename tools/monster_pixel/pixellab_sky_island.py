"""PixelLab API로 3스테이지 하늘 섬(날개 달린 돌 발판) 날갯짓 시트를 만든다.

1) image-to-pixelart-pro: 일러스트를 도트로 (폭 약 250)
2) 돌 윗면이 게임의 밟는 면(SkyPuzzle.width 100)에 맞게 평균 축소 + Pro 결과 팔레트로 다시 칠한다
   (/resize는 200px 넘는 그림을 받지 않고, image-to-pixelart로 줄이면 외곽선이 뭉개졌다)
3) animate-pixminimax: 날개가 위아래로 펄럭인다 (마지막 칸 = 첫 칸이라 끊김 없이 반복)
4) 플레이어가 서는 돌 부분(LOCK 열)은 모든 칸을 기본 그림으로 덮어 움직이지 않게 한다
사용: python tools/monster_pixel/pixellab_sky_island.py [원본 일러스트.png]
결과: assets/PixelLab/스테이지/sky_island.png (가로 8칸, 한 칸 176 × 80, 돌 윗면 35줄)
필요: 환경변수 PIXELLAB_TOKEN
"""
import sys

from PIL import Image

from pixellab_spider import OUT, b64, call, to_palette, unb64, wait

DIR = OUT.parent / '스테이지'
W, H, TOP = 176, 80, 24     # 한 칸, 섬 그림 윗줄 (날개를 치켜올릴 자리를 둔다)
SLAB = 182                  # Pro 결과에서 돌 윗면 폭 → 100으로 줄인다
LOCK = (33, 142)            # 금기둥까지 포함한 돌 부분 열 (그 바깥이 날개)
FLAP = ('the two feathered wings on the left and right ends flap up and down like a bird in a smooth loop, '
        'the stone platform in the middle stays completely still')


def make_base(src_path):
    src = Image.open(src_path).convert('RGBA')
    solid = src.getchannel('A').point(lambda v: 255 if v > 128 else 0)   # 원본의 반투명 가장자리는 버린다
    box = solid.getbbox()
    body = src.crop(box)
    body.putalpha(solid.crop(box))
    pad = Image.new('RGBA', (body.width + 80, body.height + 80), (0, 0, 0, 0))
    pad.paste(body, (40, 40))
    img = unb64(wait(call('POST', '/image-to-pixelart-pro', {
        'image': b64(pad), 'seed': 1,
        'description': 'floating stone sky island platform with two feathered angel wings, crisp dark outline, side view game sprite'}))['image'])
    # 흰 배경은 가장자리에서 이어진 것만 지운다 (날개가 흰색에 가까워 색으로만 지우면 날개도 사라진다)
    px = img.load()
    bg = px[0, 0]
    stack, seen = [(x, y) for x in range(img.width) for y in (0, img.height - 1)], set()
    stack += [(x, y) for y in range(img.height) for x in (0, img.width - 1)]
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
    small = img.resize((round(img.width * 100 / SLAB), round(img.height * 100 / SLAB)), Image.BOX)
    small.putalpha(small.getchannel('A').point(lambda v: 255 if v > 110 else 0))
    small = to_palette(small, palette)
    base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    base.paste(small, ((W - small.width) // 2, TOP))
    return base


def build_sheet(base, frames):
    """frames: animate-pixminimax 결과 (0 = 입력 … 8 = 첫 칸과 같음). 0~7을 쓰고 돌 부분은 고정한다."""
    sheet = Image.new('RGBA', (W * 8, H), (0, 0, 0, 0))
    stone = base.crop((LOCK[0], 0, LOCK[1], H))
    for column, frame in enumerate(frames[:8]):
        frame = frame.copy()
        frame.paste(stone, (LOCK[0], 0))
        sheet.paste(frame, (column * W, 0))
    return sheet


if __name__ == '__main__':
    DIR.mkdir(parents=True, exist_ok=True)
    base_path = DIR / 'sky_island_base.png'
    if len(sys.argv) > 1:
        make_base(sys.argv[1]).save(base_path)
    base = Image.open(base_path).convert('RGBA')
    frames = [unb64(i) for i in wait(call('POST', '/animate-pixminimax', {
        'first_frame': b64(base), 'last_frame': b64(base), 'description': FLAP,
        'subject_description': 'a floating stone sky island platform with a feathered wing on each end',
        'view': 'side', 'frame_count': 8, 'seed': 2, 'no_background': True}))['images']]
    build_sheet(base, frames).save(DIR / 'sky_island.png')
