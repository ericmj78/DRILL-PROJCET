"""PixelLab API로 주인공 대기/걷기/공격/점프 스트립 시트를 만든다.

사용: python tools/hero_pixel/pixellab_hero_anims.py assets/PixelLab/주인공/hero_ref.png [--skip-base]
원본은 칼 없는 128×128 도트 그림. 칼은 add_sword.py가 찍고, 결과 색은 그 팔레트로 맞춘다.
필요: 환경변수 PIXELLAB_TOKEN
"""
import base64, io, json, os, sys, time, urllib.request
from pathlib import Path
from PIL import Image

from add_sword import add_sword
from make_hero import echo

API = "https://api.pixellab.ai/v2"
TOKEN = os.environ["PIXELLAB_TOKEN"]
OUT = Path(__file__).resolve().parents[2] / "assets" / "PixelLab" / "주인공"
FRAME = 128   # 원본 도트 그림 크기
CANVAS = 160  # 시트 프레임 크기: 점프/공격 때 잘리지 않게 위·좌우 여백

ACTIONS = {
    "idle": (8, "idle breathing stance in place, holding sword low, cape gently swaying, side view facing right"),
    "walk": (8, "walking cycle in place facing right, holding sword low, cape flowing, side view"),
    "attack": (8, "sword slash attack: raise sword back, then swing it forward and down in a strong arc, recover, side view facing right"),
    "jump": (8, "jump in place: crouch, spring upward, airborne with knees tucked and cape flowing, land and crouch, side view facing right"),
    "thrust": (8, "fast fencing thrust attack: sword held level pointing forward the whole time, never raised overhead. brief pull back of the sword arm, then explosive lunge forward stabbing straight ahead to the right, sword arm fully extended and blade horizontal at chest height, hold the stab, then step back to stance. side view facing right"),
}
SEED = {"thrust": 22}  # 시드 11·22·33 중 칼을 머리 위로 들지 않는 22를 골랐다
WIDTH = {"thrust": 224}  # 찌르기는 칼끝이 앞으로 뻗으니 오른쪽만 넓힌다 (캐릭터 위치는 그대로)


def pad(base, width=CANVAS):
    c = Image.new("RGBA", (width, CANVAS), (0, 0, 0, 0))
    c.paste(base, ((CANVAS - FRAME) // 2, CANVAS - FRAME))
    return c


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{path}: {e.code} {e.read().decode('utf-8', 'replace')}") from None


def b64(img):
    buf = io.BytesIO(); img.save(buf, "PNG")
    return {"type": "base64", "base64": base64.b64encode(buf.getvalue()).decode(), "format": "png"}


def unb64(d):
    return Image.open(io.BytesIO(base64.b64decode(d["base64"]))).convert("RGBA")


def make_base(src):
    """칼 없는 128px 도트 주인공(hero_ref.png)에 칼을 찍는다. 생성권을 쓰지 않는다."""
    return add_sword(Image.open(src).convert("RGBA"))


def to_palette(frame, palette):
    """생성된 프레임을 기본 그림 팔레트의 가장 가까운 색으로 다시 칠해 색감을 맞춘다."""
    out = frame.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a < 128:
                px[x, y] = (0, 0, 0, 0)
            else:
                px[x, y] = min(palette, key=lambda c: (c[0] - r) ** 2 + (c[1] - g) ** 2 + (c[2] - b) ** 2) + (255,)
    return out


def drop_specks(frame, keep=20):
    """몸에서 떨어진 작은 픽셀 덩어리(잡티, 흩어진 이펙트 잔상)를 지운다."""
    out = frame.copy()
    px = out.load()
    seen = set()
    for sy in range(out.height):
        for sx in range(out.width):
            if px[sx, sy][3] == 0 or (sx, sy) in seen:
                continue
            group, stack = [], [(sx, sy)]
            seen.add((sx, sy))
            while stack:
                x, y = stack.pop()
                group.append((x, y))
                for nx in (x - 1, x, x + 1):
                    for ny in (y - 1, y, y + 1):
                        if 0 <= nx < out.width and 0 <= ny < out.height and (nx, ny) not in seen and px[nx, ny][3]:
                            seen.add((nx, ny)); stack.append((nx, ny))
            if len(group) < keep:
                for p in group:
                    px[p] = (0, 0, 0, 0)
    return out


def drop_head_sparkles(frame):
    """점프 때 PixelLab이 머리 위에 넣는 흰 반짝이를 지운다. 머리카락 위의 점은 주변 색으로 메운다."""
    out = frame.copy()
    px = out.load()

    def shiny(p):  # 흰색·밝은 회색 (피부는 붉은기가 커서 제외)
        return p[3] and sum(p[:3]) > 350 and p[0] - p[2] < 40

    body = [(x, y) for y in range(out.height) for x in range(out.width) if px[x, y][3] and not shiny(px[x, y])]
    head_top = min(y for _, y in body)
    for y in range(min(head_top + 10, out.height)):
        for x in range(out.width):
            if shiny(px[x, y]):
                near = [px[nx, ny] for nx in (x - 1, x, x + 1) for ny in (y - 1, y, y + 1)
                        if 0 <= nx < out.width and 0 <= ny < out.height and px[nx, ny][3] and not shiny(px[nx, ny])]
                px[x, y] = max(set(near), key=near.count) if len(near) >= 4 else (0, 0, 0, 0)
    return drop_specks(out)


def animate(base, name, n, action, seed=None, last_frame=None):
    body = {"first_frame": b64(base), "action": action, "frame_count": n, "no_background": True,
            "seed": SEED.get(name, 0) if seed is None else seed}
    if name == "jump":  # 착지 후 기본 자세로 돌아오게 고정 (없으면 마지막 프레임이 뭉개짐)
        last_frame = base
    if last_frame is not None:
        body["last_frame"] = b64(last_frame)
    job = call("POST", "/animate-with-text-v3", body)
    jid = job["background_job_id"]
    for _ in range(150):
        time.sleep(4)
        st = call("GET", f"/background-jobs/{jid}")
        if st["status"] == "completed":
            return [unb64(i) for i in st["last_response"]["images"]]
        if st["status"] == "failed":
            raise RuntimeError(f"{name}: {st.get('last_response')}")
    raise TimeoutError(name)


def save_strip(frames, name):
    w, h = frames[0].size
    sheet = Image.new("RGBA", (w * len(frames), h), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f.resize((w, h), Image.NEAREST), (i * w, 0))
    sheet.save(OUT / f"hero_{name}_sheet.png")
    echo(sheet).save(OUT / f"hero_{name}_echo.png")  # 은빛 분신용
    big = [f.resize((w * 3, h * 3), Image.NEAREST) for f in frames]
    big[0].save(OUT / f"hero_{name}_preview.gif", save_all=True, append_images=big[1:],
                duration=110, loop=0, disposal=2)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    base_path = OUT / "hero_base.png"
    if "--skip-base" in sys.argv and base_path.exists():
        base = Image.open(base_path).convert("RGBA")
    else:
        base = make_base(sys.argv[1]); base.save(base_path)
        print("base saved")
    palette = sorted({c[:3] for c in base.get_flattened_data() if c[3]})
    for name, (n, action) in ACTIONS.items():
        if (OUT / f"hero_{name}_sheet.png").exists():
            print("skip", name); continue
        first = pad(base, WIDTH.get(name, CANVAS))
        frames = [drop_specks(to_palette(f, palette)) for f in animate(first, name, n, action)]
        if name == "jump":
            frames = [drop_head_sparkles(f) for f in frames]
        save_strip(frames, name)
        print(name, len(frames), "frames")
