"""PixelLab API로 4스테이지(염력의 하늘 땅) 스위치 자리에 놓을 포털 시트를 만든다.

1) create-image-pixflux: 글로 설명한 돌 아치 포털 한 장 (96 × 128) → sky_portal_base.png
   (이미 있으면 다시 만들지 않는다. 다시 만들려면 지우고 실행한다)
2) animate-pixminimax: 안쪽 소용돌이가 도는 8칸 (마지막 칸 = 첫 칸이라 끊김 없이 반복)
사용: python tools/stage_art/pixellab_sky_portal.py   (필요: 환경변수 PIXELLAB_TOKEN)
결과: assets/PixelLab/스테이지/sky_portal.png (가로 8칸, 한 칸 96 × 128, 아랫줄이 바닥)
"""
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'monster_pixel'))
from pixellab_spider import b64, call, unb64, wait  # noqa: E402

DIR = HERE.parents[1] / 'assets' / 'PixelLab' / '스테이지'
W, H = 96, 128
LOOK = ('a standing magic portal gate, an arch of lavender stone blocks with small violet crystals, '
        'swirling purple and cyan magic vortex inside the arch, crisp dark outline, side view game sprite')
SWIRL = 'the magic vortex inside the stone arch swirls and glows in a smooth loop, the stone arch stays completely still'


def make_base():
    img = unb64(call('POST', '/create-image-pixflux', {
        'description': LOOK, 'image_size': {'width': W, 'height': H}, 'view': 'side',
        'no_background': True, 'seed': 3})['image'])
    body = img.crop(img.getbbox())
    base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    base.paste(body, ((W - body.width) // 2, H - body.height))   # 아치 발이 칸 아랫줄에 닿게
    return base


if __name__ == '__main__':
    DIR.mkdir(parents=True, exist_ok=True)
    base_path = DIR / 'sky_portal_base.png'
    if not base_path.exists():
        make_base().save(base_path)
    base = Image.open(base_path).convert('RGBA')
    frames = [unb64(i) for i in wait(call('POST', '/animate-pixminimax', {
        'first_frame': b64(base), 'last_frame': b64(base), 'description': SWIRL,
        'subject_description': 'a stone arch magic portal with a swirling vortex inside',
        'view': 'side', 'frame_count': 8, 'seed': 2, 'no_background': True}))['images']]
    sheet = Image.new('RGBA', (W * 8, H), (0, 0, 0, 0))
    for column, frame in enumerate(frames[:8]):
        sheet.paste(frame, (column * W, 0))
    sheet.save(DIR / 'sky_portal.png')
