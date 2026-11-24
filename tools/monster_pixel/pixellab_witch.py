"""PixelLab API로 2스테이지 보스(대마녀) 도트 시트를 만든다. 방법은 쇠사슬 간수와 같다.

줄: 걷기 8, 기본 공격(지팡이 휘두르기) 8, 대기 4, 중력(손을 뻗어 끌어당기기) 8, 낙뢰(지팡이를 치켜들기) 8,
마력 구체(지팡이를 앞으로 내밀어 쏘기) 8. 화면 키가 약 245라 절반 크기(키 132)로 만들고 게임에서 2배로 그린다.
사용: python tools/monster_pixel/pixellab_witch.py [원본 일러스트.png]
결과: assets/PixelLab/몬스터/grand_witch.png, grand_witch_echo.png (한 칸 256 × 176, 왼쪽을 봄)
필요: 환경변수 PIXELLAB_TOKEN
"""
import sys

from PIL import Image

from pixellab_spider import OUT, animate_pm, build_sheet, echo, make_base

SIZE, LEFT, FEET, WIDTH = (256, 176), 96, 170, 102   # 지팡이를 앞(왼쪽)·위로 휘두르니 왼쪽과 위를 넉넉히
LOOK = ('grand witch boss with huge purple pointed hat, long silver hair, ornate purple and gold robes, '
        'crystal staff, crisp dark outline, side view game sprite')
SUBJECT = {'subject_description': 'a tall grand witch with a huge purple pointed hat, long silver hair, '
                                  'ornate purple and gold robes and a crystal staff',
           'initial_pose': 'standing upright holding the crystal staff in her front hand', 'direction': 'west'}
ROWS = (                   # 줄 순서는 monster_sprite.py(GRAND_WITCH의 skills)와 같다 / (이름, 칸 수, 시드, 동작)
    # 걷기 시드 1은 지팡이 머리가 떨어져 위에 떠다녔다
    ('walk', 8, 2, 'walks forward in place step by step in a looping walk cycle, the hem of the long robe swings with '
                   'each step and the body bobs slightly, she keeps holding the staff upright in her front hand the whole time'),
    ('attack', 8, 1, 'swings the crystal staff forward in a sharp magic strike in front of her, then returns to her stance'),
    ('idle', 4, 1, 'breathes slowly in place, the hair and robes drift gently, the crystal on the staff glimmers'),
    ('gravity', 8, 1, 'spreads her free hand forward and pulls it back toward herself as if drawing everything in, '
                      'the robes billow inward, then returns to her stance'),
    ('bolts', 8, 1, 'raises the crystal staff high above her head to call down lightning from the sky, then brings it down, '
                    'then returns to her stance'),
    ('orb', 8, 1, 'thrusts the crystal staff forward to the left to launch a glowing magic orb, then returns to her stance'),
)
STILL = (0,) * 8

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    base_path = OUT / 'grand_witch_base.png'
    if len(sys.argv) > 1:
        make_base(sys.argv[1], LOOK, WIDTH, SIZE, LEFT, FEET).save(base_path)
    base = Image.open(base_path).convert('RGBA')
    rows = {name: animate_pm(base, count, seed, action, SUBJECT) for name, count, seed, action in ROWS}
    sheet = build_sheet(base, rows, ROWS, STILL)
    sheet.save(OUT / 'grand_witch.png')
    echo(sheet).save(OUT / 'grand_witch_echo.png')
