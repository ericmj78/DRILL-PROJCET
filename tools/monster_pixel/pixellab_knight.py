"""PixelLab API로 최종 보스(뒤틀린 잔향의 기사) 도트 시트를 만든다. 방법은 쇠사슬 간수·대마녀와 같다.

줄: 걷기 8, 기본 공격(대검 내려베기) 8, 대기 4, 돌진 8, 마력 구체 8, 낙뢰 8.
화면 키가 약 240이라 절반 크기(키 약 120)로 만들고 게임에서 2배로 그린다.
사용: python tools/monster_pixel/pixellab_knight.py [원본 일러스트.png]
결과: assets/PixelLab/몬스터/echo_knight.png, echo_knight_echo.png (한 칸 256 × 176, 왼쪽을 봄)
필요: 환경변수 PIXELLAB_TOKEN
"""
import sys

from PIL import Image

from pixellab_spider import OUT, animate_pm, build_sheet, echo, make_base

SIZE, LEFT, FEET, WIDTH = (256, 176), 80, 170, 116   # 대검이 앞(왼쪽) 아래로 뻗어 있고 휘두를 때 위로 올라간다
LOOK = ('dark armored knight boss with a spiked helmet, glowing violet eye slit, grey hair, tattered purple cape, '
        'cracked black armor with glowing gold veins, long cursed greatsword, crisp dark outline, side view game sprite')
SUBJECT = {'subject_description': 'a tall dark armored knight with a spiked helmet, a glowing violet eye slit, a tattered '
                                  'purple cape and a long cursed greatsword with purple flames',
           'initial_pose': 'standing upright holding the greatsword low in front of him', 'direction': 'west'}
ROWS = (                   # 줄 순서는 monster_sprite.py(KNIGHT의 skills)와 같다 / (이름, 칸 수, 시드, 동작)
    ('walk', 8, 1, 'walks forward to the left with slow heavy armored steps in a looping walk cycle: his body rises and dips '
                   'with every step, the armored legs stride one after the other, the greatsword drags low in front, '
                   'the tattered cape sways behind him'),
    ('attack', 8, 1, 'raises the greatsword high over his head and slashes it down hard in front of him with a purple trail, '
                     'then returns to his stance'),
    ('idle', 4, 1, 'breathes slowly in place, the tattered cape and hair drift gently, the eye slit glows'),
    ('charge', 8, 1, 'lowers his body and holds the greatsword forward, then lunges forward to the left in a fast charge, '
                     'the cape streaming behind, then returns to his stance'),
    ('orb', 8, 1, 'thrusts his free hand forward to the left to launch a glowing purple magic orb, then returns to his stance'),
    ('bolts', 8, 1, 'raises the greatsword straight up above his head to call down lightning from the sky, then brings it '
                    'down, then returns to his stance'),
)
STILL = (0,) * 8

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    base_path = OUT / 'echo_knight_base.png'
    if len(sys.argv) > 1:
        make_base(sys.argv[1], LOOK, WIDTH, SIZE, LEFT, FEET).save(base_path)
    base = Image.open(base_path).convert('RGBA')
    rows = {name: animate_pm(base, count, seed, action, SUBJECT) for name, count, seed, action in ROWS}
    sheet = build_sheet(base, rows, ROWS, STILL)
    sheet.save(OUT / 'echo_knight.png')
    echo(sheet).save(OUT / 'echo_knight_echo.png')
