"""Put the sword in the hand of every jump frame: make_sword_jump.py <jump sheet> <sword image> <output sheet>

The jump sheet is the 4x2 player jump sheet without a weapon. In every frame the sword
image is rotated and pasted with its grip on the hip-side glove, behind the glove so
the fist wraps the grip, and in front of everything else.
"""
import ctypes
import math
import sys

import sdl2
import sdl2.sdlimage

jump_path, sword_path, target = sys.argv[1:4]

# Measured on player_jump_sheet.png (cell coordinates): centre of the hip-side glove.
HANDS = ((160, 320), (155, 240), (205, 200), (205, 172), (192, 195), (187, 220), (195, 277), (182, 240))
# Clockwise from blade-up. ~125 hangs down and forward as in the walk; the tip trails low on
# take-off and landing and comes forward at the top of the jump.
ANGLES = (125, 137, 135, 115, 110, 125, 132, 136)  # kept low enough that the tip stays inside the cell
SWORD_REGION = (335, 48, 355, 1450)  # the sword inside weapons/sword-slim.png, blade up
GRIP = 0.84                           # grip height from the top, as a fraction of the sword
SWORD_LENGTH = 290                    # px on the jump sheet (65 px in game / (91 / 406))


def load(path):
    surface = sdl2.SDL_ConvertSurfaceFormat(sdl2.sdlimage.IMG_Load(path.encode('utf-8')),
                                            sdl2.SDL_PIXELFORMAT_RGBA32, 0).contents
    return surface, (ctypes.c_uint8 * (surface.pitch * surface.h)).from_address(surface.pixels)


sheet, data = load(jump_path)
sword, sword_data = load(sword_path)
CELL = sheet.w // 4


def get(surface, buf, x, y):
    o = y * surface.pitch + x * 4
    return buf[o], buf[o + 1], buf[o + 2], buf[o + 3]


def is_glove(r, g, b, a):
    return a > 150 and 45 < r < 150 and 28 < g < 105 and 18 < b < 85 and r - b > 18


sx0, sy0, sw, sh = SWORD_REGION
k = SWORD_LENGTH / sh
grip_u, grip_v = sw / 2, sh * GRIP
for index, ((hx, hy), degrees) in enumerate(zip(HANDS, ANGLES)):
    left, top = index % 4 * CELL, index // 4 * CELL
    hx, hy = left + hx, top + hy
    theta = math.radians(degrees)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    glove = {(x, y) for x in range(hx - 30, hx + 31) for y in range(hy - 30, hy + 31)
             if is_glove(*get(sheet, data, x, y))}
    pasted = 0
    for y in range(max(top, hy - SWORD_LENGTH), min(top + CELL, hy + SWORD_LENGTH)):
        for x in range(max(left, hx - SWORD_LENGTH), min(left + CELL, hx + SWORD_LENGTH)):
            if (x, y) in glove:
                continue
            dx, dy = x - hx, y - hy
            # Undo the clockwise rotation to find the point on the upright sword.
            u = (dx * cos_t + dy * sin_t) / k + grip_u
            v = (-dx * sin_t + dy * cos_t) / k + grip_v
            if not (0 <= u < sw and 0 <= v < sh):
                continue
            r, g, b, a = get(sword, sword_data, sx0 + int(u), sy0 + int(v))
            if a < 20:
                continue
            o = y * sheet.pitch + x * 4
            dr, dg, db, da = data[o:o + 4]
            t = a / 255
            data[o:o + 4] = bytes((round(r * t + dr * (1 - t)), round(g * t + dg * (1 - t)),
                                   round(b * t + db * (1 - t)), max(a, da)))
            pasted += 1
    print(f'frame {index}: hand ({hx - left}, {hy - top}), angle {degrees}, glove {len(glove)} px, sword {pasted} px')

sdl2.sdlimage.IMG_SavePNG(ctypes.pointer(sheet), target.encode('utf-8'))
print('saved', target)
