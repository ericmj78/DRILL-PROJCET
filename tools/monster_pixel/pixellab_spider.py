"""PixelLab API로 거미 도트 시트(걷기 8, 이빨 물기 8, 대기 4)를 만든다.

1) image-to-pixelart-pro: 일러스트를 도트로 (도트 크기는 PixelLab이 정한다, 폭 약 170)
2) resize: 도트 느낌을 지키며 폭 120으로 줄인다
3) animate-pixminimax: 걷기·물기·대기 (마지막 칸을 기본 자세로 고정)
사용: python tools/monster_pixel/pixellab_spider.py [원본 일러스트.png]
  원본을 주면 기본 도트(spider_base.png)부터 새로 만들고, 없으면 있는 기본 도트로 동작만 만든다.
결과: assets/몬스터_도트/pixellab/spider.png, spider_echo.png (한 칸 192 × 112, 왼쪽을 봄)
필요: 환경변수 PIXELLAB_TOKEN
"""
import sys
import time
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'hero_pixel'))
from pixellab_hero_anims import b64, call, unb64, animate, to_palette, drop_specks  # noqa: E402,F401
from make_monsters import echo  # noqa: E402

OUT = HERE.parents[1] / 'assets' / '몬스터_도트' / 'pixellab'
W, H = 192, 112            # 한 칸. 물기 때 앞(왼쪽)으로 덮치니 왼쪽을 넉넉히
FEET, LEFT = 106, 50       # 기본 자세의 발밑 줄, 몸 왼쪽 끝
WIDTH = 120                # 거미 몸 폭
LOOK = 'side view giant purple spider, crisp dark outline, orange eyes, web pattern on abdomen'
SUBJECT = {'subject_description': 'a giant purple spider with orange eyes and curved fangs',
           'initial_pose': 'standing on its eight legs', 'direction': 'west', 'view': 'side'}
ROWS = (                   # 줄 순서는 monster_sprite.py와 같다: 걷기, 공격, 대기 / (이름, 칸 수, 시드, 동작)
    ('walk', 8, 2, 'crawls forward in place with a smooth looping walk cycle, the eight legs step in alternating groups, the body stays level and bobs slightly'),
    ('attack', 8, 2, 'rears back slightly with the front legs, then lunges its whole body forward and bites hard with its fangs, the fangs open wide and snap shut, then pulls back to the starting pose'),
    ('idle', 4, 1, 'breathes slowly in place, the body rises and sinks a little, the fangs twitch, the legs stay planted'),
)
# 물기 줄 칸마다 몸을 옮기는 양(+ 뒤, - 앞=왼쪽). PixelLab은 몸을 거의 제자리에 둬서 덮치는 이동은 코드로 준다.
LUNGE = (0, 2, 4, 4, -10, -16, -12, -4)


def wait(job):
    while True:
        time.sleep(5)
        st = call('GET', f'/background-jobs/{job["background_job_id"]}')
        if st['status'] == 'completed':
            return st['last_response']
        if st['status'] == 'failed':
            raise RuntimeError(st)


def pixelize(src_path, width=None, height=None):
    """(외눈 유령용) 일러스트 → 128칸 도트(원본 반영 300) → 회색 배경 제거 → 몸에 맞춰 자른 그림.
    width나 height를 주면 몸 폭(또는 높이)이 128칸 중 그만큼이 되게 맞춘다."""
    src = Image.open(src_path).convert('RGBA')
    solid = src.getchannel('A').point(lambda v: 255 if v > 128 else 0)   # 원본의 옅은 얼룩은 버린다
    box = solid.getbbox()
    body = src.crop(box)
    body.putalpha(solid.crop(box))
    side = round(body.width * 128 / width) if width else round(body.height * 128 / height)
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
    return img.crop(img.getbbox())   # 색 수를 줄이지 않는다: 줄이면 6픽셀짜리 주황 눈이 사라진다


def make_base(src_path):
    src = Image.open(src_path).convert('RGBA')
    solid = src.getchannel('A').point(lambda v: 255 if v > 128 else 0)   # 원본의 옅은 얼룩은 버린다
    box = solid.getbbox()
    body = src.crop(box)
    body.putalpha(solid.crop(box))
    pad = Image.new('RGBA', (body.width + 80, body.height + 80), (0, 0, 0, 0))
    pad.paste(body, (40, 40))
    img = unb64(wait(call('POST', '/image-to-pixelart-pro', {'image': b64(pad), 'seed': 2, 'description': LOOK}))['image'])
    px = img.load()
    for y in range(img.height):          # 흰 배경 (가장자리와 다리 사이 모두)
        for x in range(img.width):
            if px[x, y][3] and min(px[x, y][:3]) >= 235:
                px[x, y] = (0, 0, 0, 0)
    img = img.crop(img.getbbox())
    size = {'width': WIDTH, 'height': round(img.height * WIDTH / img.width)}
    img = unb64(call('POST', '/resize', {
        'description': LOOK, 'reference_image': b64(img),
        'reference_image_size': {'width': img.width, 'height': img.height}, 'target_size': size,
        'view': 'side', 'direction': 'west', 'no_background': True, 'color_image': b64(img), 'seed': 1})['image'])
    img = img.crop(img.getbbox())
    base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    base.paste(img, (LEFT, FEET - img.height))
    return base


def animate_pm(base, count, seed, action):
    """PixMiniMax. 마지막 칸을 기본 자세로 고정한다 (걷기·대기는 끊김 없이 반복, 물기는 제자리로 돌아온다).
    돌려받는 칸: 0 = 입력, 1..count = 생성 (count번째 = 기본 자세)."""
    return [unb64(i) for i in wait(call('POST', '/animate-pixminimax', {
        **SUBJECT, 'first_frame': b64(base), 'last_frame': b64(base), 'description': action,
        'frame_count': count, 'seed': seed, 'no_background': True}))['images']]


def lunge(frame, dx):
    """칸 안에서 그림을 dx만큼 옆으로 옮긴다. 칸 밖으로 잘려 나가면 안 된다."""
    box = frame.getbbox()
    assert box is None or (box[0] + dx >= 0 and box[2] + dx <= frame.width), (box, dx)
    out = Image.new('RGBA', frame.size, (0, 0, 0, 0))
    out.paste(frame, (dx, 0))
    return out


def build_sheet(base, rows):
    """rows: 이름 → 생성된 칸 목록(animate_pm 결과). 걷기·대기는 0번부터, 물기는 1번부터 쓴다."""
    palette = sorted({c[:3] for c in base.get_flattened_data() if c[3]})
    sheet = Image.new('RGBA', (W * 8, H * len(ROWS)), (0, 0, 0, 0))
    for row, (name, count, _, _) in enumerate(ROWS):
        frames = rows[name][1:count + 1] if name == 'attack' else rows[name][:count]
        for column, frame in enumerate(frames):
            frame = drop_specks(to_palette(frame, palette), keep=30)
            if name == 'attack':
                frame = lunge(frame, LUNGE[column])
            sheet.paste(frame, (column * W, row * H))
    return sheet


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    base_path = OUT / 'spider_base.png'
    if len(sys.argv) > 1:
        make_base(sys.argv[1]).save(base_path)
        print('base saved')
    base = Image.open(base_path).convert('RGBA')
    rows = {name: animate_pm(base, count, seed, action) for name, count, seed, action in ROWS}
    sheet = build_sheet(base, rows)
    sheet.save(OUT / 'spider.png')
    echo(sheet).save(OUT / 'spider_echo.png')
