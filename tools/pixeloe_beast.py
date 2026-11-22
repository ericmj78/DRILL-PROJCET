import sys
import cv2, numpy as np
from PIL import Image, ImageEnhance
from pixeloe.legacy.pixelize import pixelize

SRC = sys.argv[1]; BOX = (25, 130, 250, 300); BG = np.array([43, 30, 32])  # BGR
img = cv2.imread(SRC)[BOX[1]:BOX[3], BOX[0]:BOX[2]]
for name, kw in {
    'oe_a': dict(target_size=56, patch_size=8, thickness=2, colors=16),
    'oe_b': dict(target_size=64, patch_size=8, thickness=1, colors=20),
}.items():
    sm = pixelize(img, mode='contrast', no_upscale=True, **kw)
    h, w = sm.shape[:2]
    # 테두리와 이어진 배경색만 투명 처리
    mask = np.zeros((h + 2, w + 2), np.uint8)
    near = (np.abs(sm.astype(int) - BG).sum(2) < 40)
    alpha = np.full((h, w), 255, np.uint8)
    seen = np.zeros((h, w), bool); stack = [(x, y) for x in range(w) for y in (0, h-1)] + [(x, y) for y in range(h) for x in (0, w-1)]
    while stack:
        x, y = stack.pop()
        if 0 <= x < w and 0 <= y < h and not seen[y, x] and near[y, x]:
            seen[y, x] = True; alpha[y, x] = 0
            stack += [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
    rgba = np.dstack([sm[..., ::-1], alpha])
    im = Image.fromarray(rgba, 'RGBA').crop(Image.fromarray(alpha).getbbox())
    # PixelOE의 채도·대비 옵션은 uint8 입력을 0~1로 잘라 버려서(라이브러리 버그) 여기서 보정
    rgb = ImageEnhance.Contrast(ImageEnhance.Color(im.convert('RGB')).enhance(1.35)).enhance(1.15).quantize(16, method=Image.MAXCOVERAGE, dither=Image.Dither.NONE).convert('RGBA')
    rgb.putalpha(im.getchannel('A')); im = rgb
    im.save(name + '.png')
    im.resize((im.width * 8, im.height * 8), Image.NEAREST).save(name + '_x8.png')
    print(name, im.size, len(np.unique(np.array(im)[..., :3].reshape(-1, 3), axis=0)))
