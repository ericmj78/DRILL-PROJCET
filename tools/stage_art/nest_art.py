"""2스테이지 거미 둥지의 구조물 도트 그림을 PixelLab /create-image-pixflux(글 → 도트)로 만든다.

턱(돌 발판), 거미줄 트램펄린, 무너지는 거미줄 발판, 흔들리는 판, 거미 알, 매달린 거미.
모두 옆 시점, 배경 없음. 매달린 거미는 기존 거미 도트(spider_base.png)의 색을 따라 그리게 한다.
이미 만든 그림은 다시 만들지 않는다. 다시 만들려면 그 파일을 지우고 실행한다.
사용: python tools/stage_art/nest_art.py   (필요: 환경변수 PIXELLAB_TOKEN)
결과: assets/PixelLab/스테이지/둥지/*.png (그림 테두리에 맞춰 자른다)
"""
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / 'assets' / 'PixelLab'
OUT = ROOT / '스테이지' / '둥지'
sys.path.insert(0, str(HERE.parent / 'monster_pixel'))

STYLE = 'crisp dark outline, dark gothic castle palette, side view game sprite, pixel art'
ART = {   # 이름: (설명, 폭, 높이, 시드, 색을 따를 그림)
    '턱': ('a flat dark purple stone ledge platform with a perfectly flat top surface, cracked bricks underneath, '
          'thin white spider webs hanging from its underside', 192, 64, 3, None),
    '트램펄린': ('a bouncy white spider web net stretched tight between two short bone posts, '
              'like a trampoline, the net sags slightly in the middle', 96, 48, 5, None),
    '무너지는발판': ('a fragile thin wooden plank wrapped in torn white spider silk, cracked and splintered, '
                 'about to break', 96, 32, 7, None),
    '흔들판': ('a short flat wooden plank platform hanging level, purple iron rings on both ends, '
            'wrapped with a little white spider silk', 96, 32, 9, None),
    '거미알': ('a cluster of three glowing violet spider eggs wrapped in white silk cocoon, '
             'soft magical glow', 48, 48, 11, None),
    '매달린거미': ('a giant purple spider hanging upside down, head pointing down, all eight legs spread out, '
               'orange eyes, curved fangs, web pattern on the abdomen, front view', 96, 96, 13,
               ROOT / '몬스터' / 'spider_base.png'),
}


def generate(name, description, width, height, seed, palette):
    from pixellab_spider import b64, call, unb64
    body = {'description': f'{description}, {STYLE}', 'image_size': {'width': width, 'height': height},
            'view': 'side', 'no_background': True, 'seed': seed}
    if palette is not None:
        body['color_image'] = b64(Image.open(palette).convert('RGBA'))
    image = unb64(call('POST', '/create-image-pixflux', body)['image'])
    box = image.getchannel('A').point(lambda v: 255 if v > 128 else 0).getbbox()
    return image.crop(box)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (description, width, height, seed, palette) in ART.items():
        path = OUT / f'{name}.png'
        if path.exists():
            continue
        image = generate(name, description, width, height, seed, palette)
        image.save(path)
        print(name, image.size)


if __name__ == '__main__':
    main()
