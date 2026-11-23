"""PixelLab API로 거미 도트 시트(걷기 8, 이빨 물기 8, 대기 4)를 만든다.

사용: python tools/monster_pixel/pixellab_spider.py [원본 일러스트.png]
  원본을 주면 기본 도트(spider_base.png)부터 새로 만들고, 없으면 있는 기본 도트로 동작만 만든다.
결과: assets/몬스터_도트/pixellab/spider.png, spider_echo.png (한 칸 160 × 112, 왼쪽을 봄)
필요: 환경변수 PIXELLAB_TOKEN
"""
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'hero_pixel'))
from pixellab_hero_anims import b64, call, unb64, animate, to_palette, drop_specks  # noqa: E402
from make_monsters import echo  # noqa: E402

OUT = HERE.parents[1] / 'assets' / '몬스터_도트' / 'pixellab'
W, H = 160, 112            # 한 칸. 물기 때 앞(왼쪽)으로 뻗고 몸을 드니 왼쪽·위를 넉넉히
FEET, LEFT = 106, 40       # 기본 자세의 발밑 줄, 몸 왼쪽 끝
ROWS = (                   # 줄 순서는 monster_sprite.py와 같다: 걷기, 공격, 대기
    ('walk', 8, 'spider crawling forward to the left, eight legs stepping in alternating tetrapod gait, body level, side view'),
    ('attack', 8, 'spider bite attack: rear back raising the front legs and opening the fangs, then lunge forward to the left and bite down hard with the fangs, then pull back, side view'),
    ('idle', 4, 'spider idle, body gently bobbing up and down, legs twitching slightly, fangs moving, side view'),
)


def make_base(src_path):
    """일러스트 → 128칸 도트(원본 반영 300) → 회색 배경 제거 → 24색."""
    src = Image.open(src_path).convert('RGBA')
    solid = src.getchannel('A').point(lambda v: 255 if v > 128 else 0)   # 원본의 옅은 얼룩은 버린다
    box = solid.getbbox()
    body = src.crop(box)
    body.putalpha(solid.crop(box))
    side = round(body.width * 128 / 100)        # 거미 폭이 128칸 중 100칸
    sq = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    sq.paste(body, ((side - body.width) // 2, (side - body.height) // 2))
    sq = sq.resize((512, 512), Image.LANCZOS)
    r = call('POST', '/image-to-pixelart', {
        'image': b64(sq), 'image_size': {'width': 512, 'height': 512},
        'output_size': {'width': 128, 'height': 128}, 'init_image_strength': 300, 'seed': 7})
    img = unb64(r['image'])
    px = img.load()
    bg = px[0, 0]

    def near(p, tol):
        return all(abs(p[i] - bg[i]) <= tol for i in range(3))

    # 가장자리에서 이어진 회색 배경을 지우고, 다리 사이에 갇힌 배경색도 지운다
    stack, seen = [(x, y) for x in range(128) for y in (0, 127)] + [(x, y) for y in range(128) for x in (0, 127)], set()
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < 128 and 0 <= y < 128) or not near(px[x, y], 14):
            continue
        seen.add((x, y))
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    for y in range(128):
        for x in range(128):
            if (x, y) in seen or near(px[x, y], 4):
                px[x, y] = (0, 0, 0, 0)
    alpha = img.getchannel('A')
    img = img.convert('RGB').quantize(24, method=Image.Quantize.MEDIANCUT).convert('RGBA')
    img.putalpha(alpha)
    img = img.crop(img.getbbox())
    base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    base.paste(img, (LEFT, FEET - img.height))
    return base


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    base_path = OUT / 'spider_base.png'
    if len(sys.argv) > 1:
        make_base(sys.argv[1]).save(base_path)
        print('base saved')
    base = Image.open(base_path).convert('RGBA')
    palette = sorted({c[:3] for c in base.get_flattened_data() if c[3]})
    sheet = Image.new('RGBA', (W * 8, H * len(ROWS)), (0, 0, 0, 0))
    for row, (name, count, action) in enumerate(ROWS):
        frames = animate(base, name, count, action)
        frames = frames[1:] if name == 'attack' else frames[:count]   # 공격은 기본 자세 칸을 빼고 바로 준비부터
        for column, frame in enumerate(frames[:count]):
            sheet.paste(drop_specks(to_palette(frame, palette), keep=8), (column * W, row * H))
        print(name, len(frames))
    sheet.save(OUT / 'spider.png')
    echo(sheet).save(OUT / 'spider_echo.png')
