"""PixelLab API로 1스테이지 보스(쇠사슬 간수) 도트 시트를 만든다. 방법은 거미와 같다.

줄: 걷기 8, 기본 공격(주먹 내려치기) 8, 대기 4, 쇠사슬 채찍 8, 낙석(두 주먹으로 바닥 내리치기) 8, 돌진(어깨 박치기) 8.
보스는 화면에서 키가 약 280인데 PixMiniMax 칸은 256까지라, 절반 크기(키 136)로 만들고 게임에서 2배로 그린다.
사용: python tools/monster_pixel/pixellab_jailer.py [원본 일러스트.png]
  원본을 주면 기본 도트(jailer_base.png)부터 새로 만들고, 없으면 있는 기본 도트로 동작만 만든다.
결과: assets/PixelLab/몬스터/jailer.png, jailer_echo.png (한 칸 256 × 176, 왼쪽을 봄)
필요: 환경변수 PIXELLAB_TOKEN
"""
import sys

from PIL import Image

from pixellab_spider import OUT, animate_pm, build_sheet, echo, make_base

SIZE, LEFT, FEET, WIDTH = (256, 176), 120, 170, 120   # 쇠사슬이 앞(왼쪽)으로 길게 뻗으니 왼쪽을 넉넉히
LOOK = ('stone golem jailer boss with curved horns, rusty chains and shackles, tattered cloak, '
        'glowing orange eyes, crisp dark outline, side view game sprite')
SUBJECT = {'subject_description': 'a hulking stone golem jailer with curved horns, rusty shackles and chains, '
                                  'and a tattered purple cloak',
           'initial_pose': 'standing upright with fists down at its sides', 'direction': 'west'}
ROWS = (                   # 줄 순서는 monster_sprite.py(JAILER_SKILLS)와 같다 / (이름, 칸 수, 시드, 동작)
    ('walk', 8, 1, 'stomps forward in place with a heavy slow looping walk cycle, the chains on its wrists swing, the cloak sways'),
    ('attack', 8, 1, 'raises its right fist high and smashes it down hard in front of itself, then straightens back up'),
    ('idle', 4, 1, 'breathes slowly in place, the shoulders rise and fall, the chains sway slightly'),
    ('chain', 8, 1, 'swings the chain on its arm back, then whips the long chain forward to the left so it lashes far out in front, then pulls it back'),
    ('rockfall', 8, 1, 'raises both fists above its head, then slams them down onto the ground with a heavy quake, then stands back up'),
    ('charge', 8, 1, 'lowers its head and shoulder and braces, then lunges forward to the left in a powerful shoulder charge, then recovers'),
)
STILL = (0,) * 8           # PixelLab이 주먹·사슬을 충분히 앞으로 뻗어서 코드로 옮기지 않는다

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    base_path = OUT / 'jailer_base.png'
    if len(sys.argv) > 1:
        make_base(sys.argv[1], LOOK, WIDTH, SIZE, LEFT, FEET).save(base_path)
    base = Image.open(base_path).convert('RGBA')
    rows = {name: animate_pm(base, count, seed, action, SUBJECT) for name, count, seed, action in ROWS}
    sheet = build_sheet(base, rows, ROWS, STILL)
    sheet.save(OUT / 'jailer.png')
    echo(sheet).save(OUT / 'jailer_echo.png')
