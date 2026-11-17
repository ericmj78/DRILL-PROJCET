"""Swing the sword arm while walking: make_sword_walk.py <input sheet> <output sheet> [amplitude degrees]

The input is the 4x2 walking sheet where the sword arm never moves. For every frame the
arm below the elbow (rolled cuff, forearm, glove) and the sword it holds are lifted out
as one piece, the hole is filled from the surrounding pixels, and the piece is pasted
back rotated about the elbow so the arm swings back and forth with the stride.
"""
import ctypes
import math
import sys

import sdl2
import sdl2.sdlimage

source, target = sys.argv[1], sys.argv[2]
AMPLITUDE = float(sys.argv[3]) if len(sys.argv) > 3 else 14.0

surface = sdl2.SDL_ConvertSurfaceFormat(sdl2.sdlimage.IMG_Load(source.encode('utf-8')),
                                        sdl2.SDL_PIXELFORMAT_RGBA32, 0).contents
W, H, PITCH = surface.w, surface.h, surface.pitch
data = (ctypes.c_uint8 * (PITCH * H)).from_address(surface.pixels)
CELL_W, CELL_H = W // 4, H // 2
# Measured on the input sheet (cell coordinates): where the glove and the pommel are in each frame.
GLOVES = ((185, 255), (178, 253), (178, 250), (177, 257), (185, 255), (190, 257), (193, 255), (173, 257))
POMMELS = ((152, 249), (145, 251), (143, 241), (145, 247), (152, 250), (157, 249), (153, 252), (145, 250))
ELBOW = (184, 190)  # under the sleeve, just above the rolled cuff


def get(x, y):
    o = y * PITCH + x * 4
    return data[o], data[o + 1], data[o + 2], data[o + 3]


def put(x, y, rgba):
    o = y * PITCH + x * 4
    data[o:o + 4] = bytes(rgba)


def in_arm_area(x, y, glove, pommel):
    """Rough outline of cuff, forearm, glove and pommel in one frame (cell coordinates)."""
    gx, gy = glove
    px, py = pommel
    return ((160 <= x <= 208 and 192 <= y <= 219) or (168 <= x <= 206 and 212 <= y <= 234)
            or (gx - 26 <= x <= gx + 26 and gy - 32 <= y <= gy + 32)
            or (px - 14 <= x <= gx and py - 14 <= y <= py + 14))


def is_cloth(r, g, b, a):
    # Tunic, trousers and cape are dark and cool; the arm (skin, leather, cuff, steel) is warm or bright.
    return a < 150 or (max(r, g, b) < 110 and b >= r - 4)


def is_steel(r, g, b, a):
    return a > 150 and max(r, g, b) > 105 and max(r, g, b) - min(r, g, b) < 34


def frame_angle(index):
    # Arms are furthest out when the legs are furthest apart (frames 0 and 4). In frame 0 the
    # near leg is forward, so the near (sword) arm is back. Positive angle swings the hand forward.
    return -AMPLITUDE * math.cos(index / 8 * 2 * math.pi)


for index in range(8):
    left, top = index % 4 * CELL_W, index // 4 * CELL_H
    glove, pommel = GLOVES[index], POMMELS[index]
    arm = {(left + x, top + y) for y in range(185, 300) for x in range(120, 240)
           if in_arm_area(x, y, glove, pommel) and not is_cloth(*get(left + x, top + y))}
    # The blade: the largest connected piece of steel below the hand.
    steel = {(left + x, top + y) for y in range(235, 420) for x in range(120, min(CELL_W, 420))
             if is_steel(*get(left + x, top + y))}
    seen, blade = set(), set()
    for start in steel:
        if start in seen:
            continue
        part, stack = {start}, [start]
        seen.add(start)
        while stack:
            x, y = stack.pop()
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    q = (x + dx, y + dy)
                    if q in steel and q not in seen:
                        seen.add(q)
                        part.add(q)
                        stack.append(q)
        if len(part) > len(blade):
            blade = part
    arm |= blade
    # Grow by 4 px to take the dark outline and soft edges with it.
    piece = {(x + dx, y + dy) for x, y in arm for dx in range(-4, 5) for dy in range(-4, 5)
             if y + dy >= top + 192}
    # The input has a red fringe around the blade; clear it with the hole instead of leaving it behind.
    piece |= {(x + dx, y + dy) for x, y in blade for dx in range(-10, 11, 2) for dy in range(-10, 11, 2)
              if 0 <= x + dx - left < CELL_W and 0 <= y + dy - top < CELL_H
              and (lambda c: c[3] > 60 and c[0] > 120 and c[0] - c[1] > 55 and c[0] - c[2] > 55)(get(x + dx, y + dy))}
    original = {p: get(*p) for p in piece}
    ex, ey = left + ELBOW[0], top + ELBOW[1]

    # 1) Fill the hole from the nearest untouched pixels above, below, left and right.
    fill = {}
    for x, y in piece:
        total, weight = [0.0, 0.0, 0.0, 0.0], 0.0
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            step, nx, ny = 1, x + dx, y + dy
            while (nx, ny) in piece and step < 60:
                step, nx, ny = step + 1, nx + dx, ny + dy
            if not (left <= nx < left + CELL_W and top <= ny < top + CELL_H):
                continue
            c = get(nx, ny)
            w = 1 / step ** 2
            weight += w
            for i in range(4):
                total[i] += c[i] * w
        c = [round(v / weight) for v in total] if weight else [0, 0, 0, 0]
        fill[(x, y)] = (0, 0, 0, 0) if c[3] < 128 else (c[0], c[1], c[2], 255)
    for p, c in fill.items():
        put(*p, c)

    # 2) Paste the arm and sword rotated about the elbow.
    angle = math.radians(frame_angle(index))
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    reach = max(math.hypot(x - ex, y - ey) for x, y in piece) + 2
    for y in range(max(top, int(ey - reach)), min(top + CELL_H, int(ey + reach) + 1)):
        for x in range(max(left, int(ex - reach)), min(left + CELL_W, int(ex + reach) + 1)):
            # Inverse of the forward swing (dx' = dx cos + dy sin, dy' = -dx sin + dy cos).
            dx, dy = x - ex, y - ey
            sx = round(ex + dx * cos_a - dy * sin_a)
            sy = round(ey + dx * sin_a + dy * cos_a)
            c = original.get((sx, sy))
            if c is None:
                continue
            # Arm pixels always; the grown edge only where it is dark outline, not borrowed cloth.
            if (sx, sy) in arm or (c[3] > 150 and max(c[:3]) < 60):
                put(x, y, c)
    print(f'frame {index}: arm {len(arm)} px (blade {len(blade)}), angle {frame_angle(index):+.1f}')

sdl2.sdlimage.IMG_SavePNG(ctypes.pointer(surface), target.encode('utf-8'))
print('saved', target)
