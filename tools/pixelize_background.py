"""Redraw a map background as pixel art at its in-game size.

pixelize_background.py <in.png> <out.png> <screen width> <screen height> [dot size] [colors]

The game stretches a floor background to screen width x height (stage 1: 2240 x 400), so
the art is made on a grid of (width / dot) x (height / dot) square dots and saved at the
screen size: drawn 1:1, every dot is a crisp dot x dot square.
1. Each dot is the average colour of the source area it covers.
2. Colours are reduced to one small palette (median cut).
3. Lone specks that differ from at least three of their four neighbours are cleaned up,
   which keeps one-dot lines such as window bars.
"""
import ctypes
import sys

import sdl2
import sdl2.sdlimage

source, target = sys.argv[1], sys.argv[2]
SCREEN_W, SCREEN_H = int(sys.argv[3]), int(sys.argv[4])
DOT = int(sys.argv[5]) if len(sys.argv) > 5 else 4
COLORS = int(sys.argv[6]) if len(sys.argv) > 6 else 24
GRID_W, GRID_H = SCREEN_W // DOT, SCREEN_H // DOT

surface = sdl2.SDL_ConvertSurfaceFormat(sdl2.sdlimage.IMG_Load(source.encode('utf-8')),
                                        sdl2.SDL_PIXELFORMAT_RGBA32, 0).contents
W, H, PITCH = surface.w, surface.h, surface.pitch
data = (ctypes.c_uint8 * (PITCH * H)).from_address(surface.pixels)

# 1) Area average per dot.
grid = []
for gy in range(GRID_H):
    y0, y1 = gy * H // GRID_H, max(gy * H // GRID_H + 1, (gy + 1) * H // GRID_H)
    row = []
    for gx in range(GRID_W):
        x0, x1 = gx * W // GRID_W, max(gx * W // GRID_W + 1, (gx + 1) * W // GRID_W)
        r = g = b = n = 0
        for y in range(y0, y1):
            o = y * PITCH
            for x in range(x0, x1):
                p = o + x * 4
                r += data[p]
                g += data[p + 1]
                b += data[p + 2]
                n += 1
        row.append((r // n, g // n, b // n))
    grid.append(row)

# 2) Palette by median cut, then snap every dot.
boxes = [[c for row in grid for c in row]]
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
cache = {}


def snap(colour):
    if colour not in cache:
        cache[colour] = min(palette, key=lambda p: sum((p[i] - colour[i]) ** 2 for i in range(3)))
    return cache[colour]


grid = [[snap(c) for c in row] for row in grid]

# 3) Clean lone specks.
cleaned = [row[:] for row in grid]
for y in range(1, GRID_H - 1):
    for x in range(1, GRID_W - 1):
        here = grid[y][x]
        around = [grid[y - 1][x], grid[y + 1][x], grid[y][x - 1], grid[y][x + 1]]
        if around.count(here) == 0:
            best = max(set(around), key=around.count)
            if around.count(best) >= 3:
                cleaned[y][x] = best
grid = cleaned

# 4) Write dot x dot squares at screen size.
out = sdl2.SDL_CreateRGBSurfaceWithFormat(0, SCREEN_W, SCREEN_H, 32, sdl2.SDL_PIXELFORMAT_RGBA32)
fmt = out.contents.format
for gy, row in enumerate(grid):
    for gx, (r, g, b) in enumerate(row):
        sdl2.SDL_FillRect(out, sdl2.SDL_Rect(gx * DOT, gy * DOT, DOT, DOT), sdl2.SDL_MapRGBA(fmt, r, g, b, 255))
sdl2.sdlimage.IMG_SavePNG(out, target.encode('utf-8'))
print(f'saved {target}: {GRID_W} x {GRID_H} dots of {DOT}px, {len(palette)} colours')
