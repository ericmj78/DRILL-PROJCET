"""도트 주인공 그림(칼 없음)의 뒤쪽 손에 한손검을 찍는다. 색은 원본 그림 팔레트에서만 고른다.

사용: python add_sword.py <원본128.png> <결과.png>
"""
import sys

from PIL import Image

OUTLINE = (8, 10, 20, 255)
SHINE, LIGHT, MID, DARK = (254, 254, 254, 255), (172, 159, 145, 255), (126, 116, 110, 255), (77, 85, 104, 255)
GRIP, BRASS = (80, 54, 46, 255), (188, 125, 82, 255)
GLOVE_BOX = (56, 73, 66, 87)        # 뒤쪽 장갑: 손잡이를 덮도록 원본 픽셀을 다시 올린다
HAND = (60, 80)
SLOPE = 0.42                         # 원본 일러스트의 칼 기울기 (오른쪽 아래)
BLADE = (70, 105)                    # 칼날이 시작하고 끝나는 x


def add_sword(src):
    img = src.copy()
    put = img.putpixel

    def blade_y(x):
        return round(HAND[1] + 3 + SLOPE * (x - BLADE[0]))

    # 칼날: 위 가장자리는 밝게, 아래는 어둡게, 위아래 외곽선. 끝 4칸은 가늘게.
    for x in range(BLADE[0], BLADE[1] + 1):
        y = blade_y(x)
        thin = x > BLADE[1] - 4
        put((x, y - 1), OUTLINE)
        put((x, y), LIGHT)
        if thin:
            put((x, y + 1), MID)
            put((x, y + 2), OUTLINE)
        else:
            put((x, y + 1), SHINE)       # 가운데 줄(혈조)을 밝게
            put((x, y + 2), MID)
            put((x, y + 3), OUTLINE)
    put((BLADE[1] + 1, blade_y(BLADE[1])), OUTLINE)
    put((BLADE[1] + 1, blade_y(BLADE[1]) + 1), OUTLINE)

    # 코등이: 칼날과 수직(왼쪽 아래 ↔ 오른쪽 위), 놋쇠 2칸 두께
    gx = BLADE[0] - 2
    gy = blade_y(BLADE[0]) + 1
    for i in range(-4, 5):
        x, y = gx - round(i * 0.4), gy + i
        put((x - 1, y), OUTLINE); put((x, y), BRASS); put((x + 1, y), LIGHT if abs(i) < 4 else OUTLINE)
        put((x + 2, y), OUTLINE)
    for i in (-5, 5):
        x, y = gx - round(i * 0.4), gy + i
        put((x, y), OUTLINE); put((x + 1, y), OUTLINE)

    # 손잡이와 폼멜: 손 뒤쪽(왼쪽 위)
    for x in range(HAND[0] - 8, gx - 1):
        y = round(gy + SLOPE * (x - gx))
        put((x, y - 1), OUTLINE); put((x, y), GRIP); put((x, y + 1), OUTLINE)
    px, py = HAND[0] - 9, round(gy + SLOPE * (HAND[0] - 9 - gx))
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        put((px + dx, py + dy), MID)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)):
        put((px + dx, py + dy), OUTLINE)
    put((px, py), LIGHT)

    # 장갑을 다시 위에 올려 손잡이를 쥔 모양으로
    x0, y0, x1, y1 = GLOVE_BOX
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b, a = src.getpixel((x, y))
            if a and r > b and r > 40:   # 갈색 계열(장갑)만
                put((x, y), (r, g, b, a))
    return img


if __name__ == '__main__':
    out = add_sword(Image.open(sys.argv[1]).convert('RGBA'))
    out.save(sys.argv[2])
