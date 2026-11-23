"""PixelLab API로 뿔짐승 도트 시트(걷기 8, 뿔 들이받기 8, 대기 4)를 만든다. 방법은 거미와 같다.

사용: python tools/monster_pixel/pixellab_beast.py [원본 일러스트.png]
  원본을 주면 기본 도트(beast_base.png)부터 새로 만들고, 없으면 있는 기본 도트로 동작만 만든다.
결과: assets/PixelLab/몬스터/beast.png, beast_echo.png (한 칸 224 × 128, 왼쪽을 봄)
필요: 환경변수 PIXELLAB_TOKEN
"""
import sys

from PIL import Image

from pixellab_spider import OUT, animate_pm, build_sheet, echo, make_base

SIZE, LEFT, FEET, WIDTH = (224, 128), 60, 122, 140   # 들이받을 때 앞(왼쪽)으로 나가니 왼쪽을 넉넉히
LOOK = 'side view horned purple wolf beast with spiky magenta mane, crisp dark outline, orange eyes'
SUBJECT = {'subject_description': 'a horned purple wolf-like beast with a spiky magenta mane and orange eyes',
           'initial_pose': 'standing on four legs in a low prowling stance', 'direction': 'west', 'view': 'side'}
ROWS = (                   # 줄 순서는 monster_sprite.py와 같다: 걷기, 공격, 대기 / (이름, 칸 수, 시드, 동작)
    ('walk', 8, 1, 'walks forward in place with a smooth looping four-legged gait, the legs step in a diagonal pattern, the mane bounces slightly'),
    ('attack', 8, 1, 'lowers its head and crouches back, then charges forward and rams hard with its curved horns, then steps back to the starting pose'),
    ('idle', 4, 1, 'breathes slowly in place, the mane rises and falls, the tail sways, the legs stay planted'),
)
# 공격 줄 칸마다 몸을 옮기는 양(+ 뒤, - 앞=왼쪽). 시드 1은 PixelLab이 이미 앞으로 약 50px 덮쳐서 조금만 더한다.
# (시드 2는 덮칠 때 몸이 카메라 쪽으로 돌아갔다)
RAM = (0, 2, 4, 4, -4, -6, -4, 0)

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    base_path = OUT / 'beast_base.png'
    if len(sys.argv) > 1:
        make_base(sys.argv[1], LOOK, WIDTH, SIZE, LEFT, FEET).save(base_path)
    base = Image.open(base_path).convert('RGBA')
    rows = {name: animate_pm(base, count, seed, action, SUBJECT) for name, count, seed, action in ROWS}
    sheet = build_sheet(base, rows, ROWS, RAM)
    sheet.save(OUT / 'beast.png')
    echo(sheet).save(OUT / 'beast_echo.png')
