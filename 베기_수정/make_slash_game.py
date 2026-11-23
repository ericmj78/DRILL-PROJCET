"""Pixel slash driven by the game's own slash data (player_attack.py) and sword-slash effect."""
import json
import math
import sys
from PIL import Image

PROJECT = r'C:\Users\USER\Documents\ChatGPT\2D 프로그래밍\DRILL-PROJCET'
sys.path.insert(0, PROJECT)
import player_attack as pa  # noqa: E402  (same keyframes/timing the game uses)
from make_slash import (SHOULDER, draw_capsule, draw_glove, draw_sword, ik, n0, outline,  # noqa: E402
                        pose_body, shift_at, SLEEVE, CUFF)

DURATION = 0.28          # world.py: slash attack_duration
FRAMES = 10              # equal-time frames over the attack
ACTOR_X, FLOOR = 71, 121.5  # art px: body centre and feet line of the 160px frame
# The game's fist sheet is a low stance; this body stands upright, so heights are scaled to keep
# the hand at chest level instead of in front of the face.
HEIGHT_SCALE = 0.78
REACH = 99               # 한손검 reach in stages.WEAPONS

fx_img = Image.open('git_slashfx.png').convert('RGBA')
fx_meta = json.load(open('git_slashfx.json', encoding='utf-8'))['meta']['pixelfx']


def effect_layer(age, shift):
    """Same placement as player_attack.draw_attack_effect, in art px (y down)."""
    name, lead, forward, lift, scale, _color = pa.EFFECTS['slash']
    t = age - DURATION * pa.HIT_AT + lead
    frame = int(t * fx_meta['fps'])
    if t < 0 or frame >= fx_meta['frames']:
        return None
    w, h = fx_meta['frameSize']
    px, py = fx_meta['pivot']
    s = scale * REACH / 99
    src = fx_img.crop((frame % fx_meta['columns'] * w, frame // fx_meta['columns'] * h,
                       frame % fx_meta['columns'] * w + w, frame // fx_meta['columns'] * h + h))
    src = src.resize((round(w * s), round(h * s)), Image.NEAREST)
    layer = Image.new('RGBA', (160, 160))
    layer.alpha_composite(src, (round(ACTOR_X + forward - px * s), round(FLOOR - lift - py * s)))
    return layer


def hand_angle(progress):
    fwd, height, angle, lunge = pa.weapon_pose('slash', progress)
    return (ACTOR_X + fwd, FLOOR - height * HEIGHT_SCALE), 90 - angle, lunge  # game angle: 0 up / 90 forward


def sword_layer(hand, ang, alpha=1.0):
    layer = Image.new('RGBA', (160, 160))
    draw_sword(layer, hand[0], hand[1], ang)
    outline(layer)
    if alpha < 1:
        a = layer.getchannel('A').point(lambda v: round(v * alpha))
        layer.putalpha(a)
    return layer


def render(progress):
    hand, ang, lunge = hand_angle(progress)
    lean = max(-2, min(3, round(lunge / 3)))
    crouch = 1 if abs(lunge) > 3 else 0
    dx = round(lunge)                      # the game slides the body by the lunge
    body = pose_body(lean, crouch)
    shifted = Image.new('RGBA', (320, 320))
    shifted.alpha_composite(body, (2 * dx, 0))
    s = (SHOULDER[0] + dx + shift_at(lean, crouch, SHOULDER[1] * 2)[0], SHOULDER[1] + crouch)
    elbow, h = ik(s, (hand[0], hand[1] + crouch), 14, 14)
    behind = ang > 120

    arm = Image.new('RGBA', (160, 160))
    draw_capsule(arm, s, elbow, 2.3, SLEEVE)
    fore = (elbow[0] + (h[0] - elbow[0]) * 0.7, elbow[1] + (h[1] - elbow[1]) * 0.7)
    draw_capsule(arm, elbow, fore, 2.1, SLEEVE)
    draw_capsule(arm, fore, (elbow[0] + (h[0] - elbow[0]) * 0.85, elbow[1] + (h[1] - elbow[1]) * 0.85), 2.4,
                 (CUFF, CUFF))
    draw_glove(arm, h[0], h[1])
    outline(arm)

    ghosts = []
    for past, strength in pa.trail(progress):  # same afterimages as view.py
        ph, pang, plunge = hand_angle(past)
        ps = (SHOULDER[0] + round(plunge), SHOULDER[1])
        _, gh = ik(ps, ph, 14, 14)
        ghosts.append(sword_layer(gh, pang, strength))

    up = lambda im: im.resize((320, 320), Image.NEAREST)
    out = Image.new('RGBA', (320, 320))
    sword = sword_layer(h, ang)
    fx = effect_layer(progress * DURATION, dx)
    if behind:
        out.alpha_composite(up(sword))
    out.alpha_composite(shifted)
    for g in ghosts:
        out.alpha_composite(up(g))
    if fx:
        out.alpha_composite(up(fx))
    out.alpha_composite(up(arm))
    if not behind:
        out.alpha_composite(up(sword))
        g = Image.new('RGBA', (160, 160))
        draw_glove(g, h[0], h[1])
        out.alpha_composite(up(g))
    return out


def main():
    attack = [render((i + 0.5) / FRAMES) for i in range(FRAMES)]  # frame i covers [i/N, (i+1)/N)
    sheet = Image.new('RGBA', (320 * FRAMES, 320))
    for i, f in enumerate(attack):
        sheet.alpha_composite(f, (320 * i, 0))
    sheet.save('slash_game_sheet.png')

    def white(f):
        bg = Image.new('RGBA', f.size, 'white')
        bg.alpha_composite(f)
        return bg.convert('RGB').resize((640, 640), Image.NEAREST)

    ms = round(DURATION * 1000 / FRAMES)
    seq = [white(n0)] + [white(f) for f in attack]
    seq[0].save('slash_game.gif', save_all=True, append_images=seq[1:],
                duration=[400] + [ms] * FRAMES, loop=0)
    seq[0].save('slash_game_slow.gif', save_all=True, append_images=seq[1:],
                duration=[400] + [ms * 4] * FRAMES, loop=0)
    print('ok', FRAMES, 'frames at', ms, 'ms')


if __name__ == '__main__':
    main()
