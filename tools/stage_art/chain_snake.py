"""사슬 뱀의 탑(4스테이지)의 돌 뱀 그림을 PixelLab 도트로 바꾸고 머리·몸통 한 칸·꼬리로 자른다.

원본: assets/사슬뱀/원본.png (2172 × 724, 오른쪽을 보는 뱀: 꼬리 고깔 + 몸통 칸 5개 + 머리)
1) PixelLab /image-to-pixelart-pro로 도트 그림(511 × 110)을 만든다 → assets/사슬뱀/도트_원본.png
   (이미 있으면 다시 만들지 않는다. 다시 만들려면 지우고 실행한다)
2) 가장자리에서 이어진 흰 배경을 지운다.
3) 이음 쇠고리의 가운데(가장 좁은 곳)에서 잘라 몸통 한 칸이 끊김 없이 이어지게 한다.
게임에서는 1배로 그린다: 몸 한 칸 66, 두께 28 (chain_snake.CELL, THICK).
사용: python tools/stage_art/chain_snake.py   (필요: 환경변수 PIXELLAB_TOKEN)
결과: assets/사슬뱀/머리.png, 몸통.png, 꼬리.png
"""
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / 'assets' / '사슬뱀'
sys.path.insert(0, str(HERE.parent / 'monster_pixel'))
LOOK = ('long segmented stone serpent made of lavender stone blocks with bronze chain joints, glowing violet crystals, '
        'snake head with open jaws, crisp dark outline, side view game sprite')
TOP, BOTTOM = 44, 72                   # 몸통의 위·아래 줄 (머리는 31줄부터 위로 솟는다)
PIECES = {                             # 이름: (왼쪽, 위, 오른쪽, 아래). 쇠고리 가운데 79·279·345·407
    '꼬리': (12, TOP, 79, BOTTOM),
    '몸통': (279, TOP, 345, BOTTOM),
    '머리': (407, 31, 501, BOTTOM),
}


def pixel_art():
    path = ROOT / '도트_원본.png'
    if not path.exists():
        from pixellab_spider import b64, call, unb64, wait
        src = Image.open(ROOT / '원본.png').convert('RGBA')
        solid = src.getchannel('A').point(lambda v: 255 if v > 128 else 0)
        box = solid.getbbox()
        body = src.crop(box)
        body.putalpha(solid.crop(box))
        pad = Image.new('RGBA', (body.width + 80, body.height + 80), (0, 0, 0, 0))
        pad.paste(body, (40, 40))
        job = call('POST', '/image-to-pixelart-pro', {'image': b64(pad), 'seed': 2, 'description': LOOK})
        unb64(wait(job)['image']).save(path)
    return Image.open(path).convert('RGBA')


def clear_background(image):
    """가장자리에서 이어진 흰 배경(PixelLab이 깔아 준다)을 투명하게 한다. 안쪽의 흰 반짝임은 남는다."""
    px, (w, h) = image.load(), image.size
    stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    seen = set()
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < w and 0 <= y < h) or min(px[x, y][:3]) < 235:
            continue
        seen.add((x, y))
        px[x, y] = (0, 0, 0, 0)
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return image


if __name__ == '__main__':
    sheet = clear_background(pixel_art())
    for name, box in PIECES.items():
        piece = sheet.crop(box)
        piece.save(ROOT / f'{name}.png')
        print(name, piece.size)
