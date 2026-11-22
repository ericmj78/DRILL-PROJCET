"""Turn a sprite sheet into pixel art: pixelize_sheet.py <in.png> <out.png> <columns> <rows> <block> [colors] [solid]

The output keeps the same size and cell layout as the input, so it can replace it later.
Each cell is cut into block x block squares; every square becomes one art pixel
(alpha-weighted average colour, hard transparency). All cells share one palette so the
animation does not flicker, and every shape gets a one-pixel dark outline.
Background-removal leftovers (saturated magenta/blue/red fringes) are ignored.
"""
import ctypes
import sys

import sdl2
import sdl2.sdlimage

source, target, columns, rows, block = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
COLORS = int(sys.argv[6]) if len(sys.argv) > 6 else 16
SOLID = int(sys.argv[7]) if len(sys.argv) > 7 else 110  # 이보다 덜 덮인 칸은 투명. 반투명 빛이 많은 그림은 높인다.

surface = sdl2.SDL_ConvertSurfaceFormat(sdl2.sdlimage.IMG_Load(source.encode('utf-8')),
                                        sdl2.SDL_PIXELFORMAT_RGBA32, 0).contents
W, H, PITCH = surface.w, surface.h, surface.pitch
data = (ctypes.c_uint8 * (PITCH * H)).from_address(surface.pixels)
CELL_W, CELL_H = W // columns, H // rows


def is_fringe(r, g, b):
    return max(r, g, b) - min(r, g, b) > 150 and g < 60


# 1) One art pixel per block: (colour, alpha level) or None.
cells = []
for row in range(rows):
    for column in range(columns):
        left, top = column * CELL_W, row * CELL_H
        grid = []
        for gy in range(-(-CELL_H // block)):
            line = []
            for gx in range(-(-CELL_W // block)):
                r = g = b = weight = count = 0
                for y in range(top + gy * block, min(top + (gy + 1) * block, top + CELL_H, H)):
                    o = y * PITCH
                    for x in range(left + gx * block, min(left + (gx + 1) * block, left + CELL_W, W)):
                        p = o + x * 4
                        count += 1
                        a = data[p + 3]
                        if a < 20 or is_fringe(data[p], data[p + 1], data[p + 2]):
                            continue
                        r += data[p] * a
                        g += data[p + 1] * a
                        b += data[p + 2] * a
                        weight += a
                coverage = weight / count if count else 0
                if coverage < SOLID:
                    line.append(None)
                else:
                    level = 255 if coverage >= 200 else 175  # 반투명 몸통(분신)은 한 단계 투명하게 남긴다
                    line.append(((r // weight, g // weight, b // weight), level))
            grid.append(line)
        cells.append((left, top, grid))

# 2) Shared palette by median cut.
colours = [pixel[0] for _, _, grid in cells for line in grid for pixel in line if pixel]
boxes = [colours]
while len(boxes) < COLORS:
    boxes.sort(key=lambda bx: max(max(c[i] for c in bx) - min(c[i] for c in bx) for i in range(3)) if len(bx) > 1 else -1)
    widest = boxes.pop()
    if len(widest) < 2:
        boxes.append(widest)
        break
    channel = max(range(3), key=lambda i: max(c[i] for c in widest) - min(c[i] for c in widest))
    widest.sort(key=lambda c: c[channel])
    boxes += [widest[:len(widest) // 2], widest[len(widest) // 2:]]
palette = [tuple(sum(c[i] for c in bx) // len(bx) for i in range(3)) for bx in boxes if bx]
outline = tuple(v * 45 // 100 for v in min(palette, key=sum))
snapped = {}


def snap(colour):
    if colour not in snapped:
        snapped[colour] = min(palette, key=lambda p: sum((p[i] - colour[i]) ** 2 for i in range(3)))
    return snapped[colour]


# 3) Write every block back at full size, with a dark outline around the shapes.
for left, top, grid in cells:
    gh, gw = len(grid), len(grid[0])
    for gy in range(gh):
        for gx in range(gw):
            pixel = grid[gy][gx]
            if pixel is not None:
                rgba = (*snap(pixel[0]), pixel[1])
            elif any(0 <= gy + dy < gh and 0 <= gx + dx < gw and grid[gy + dy][gx + dx] is not None
                     for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                rgba = (*outline, 255)
            else:
                rgba = (0, 0, 0, 0)
            value = bytes(rgba)
            for y in range(top + gy * block, min(top + (gy + 1) * block, top + CELL_H, H)):
                o = y * PITCH
                for x in range(left + gx * block, min(left + (gx + 1) * block, left + CELL_W, W)):
                    data[o + x * 4:o + x * 4 + 4] = value

sdl2.sdlimage.IMG_SavePNG(ctypes.pointer(surface), target.encode('utf-8'))
print(f'saved {target}: {len(cells)} cells, block {block}px, {len(palette)} colours')
