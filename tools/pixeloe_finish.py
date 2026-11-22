from PIL import Image
im = Image.open('oe_b.png').convert('RGBA'); w, h = im.size; px = im.load()
OUT = (19, 0, 24, 255)
FIX = {(92, 77, 139): (101, 58, 103), (24, 27, 37): OUT[:3], (184, 161, 193): (184, 116, 127)}  # 배경이 섞인 푸른 점
for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if a and (r, g, b) in FIX: px[x, y] = (*FIX[(r, g, b)], 255)
# 12픽셀 이하로 떨어진 덩어리 제거
seen = set()
for y in range(h):
    for x in range(w):
        if px[x, y][3] and (x, y) not in seen:
            comp, st = [], [(x, y)]; seen.add((x, y))
            while st:
                cx, cy = st.pop(); comp.append((cx, cy))
                for n in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
                    if 0 <= n[0] < w and 0 <= n[1] < h and px[n][3] and n not in seen: seen.add(n); st.append(n)
            if len(comp) <= 12:
                for p in comp: px[p] = (0, 0, 0, 0)
res = Image.new('RGBA', (w + 2, h + 2)); res.paste(im, (1, 1), im); rp = res.load()
for y in range(h + 2):
    for x in range(w + 2):
        if not rp[x, y][3] and any(0 <= x+dx < w+2 and 0 <= y+dy < h+2 and rp[x+dx, y+dy][3] == 255 and rp[x+dx, y+dy] != OUT for dx, dy in ((1,0),(-1,0),(0,1),(0,-1))):
            rp[x, y] = OUT
res.save('oe_final.png')
res.resize(((w+2)*8, (h+2)*8), Image.NEAREST).save('oe_final_x8.png')
print(res.size)
