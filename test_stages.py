"""스테이지 공략 검증. `python test_stages.py`로 실행한다.

화면 없이 World만 돌린다. 스테이지마다 (1) 아래 공략대로 하면 깨지고
(2) 분신 없이 달리며 베기만 해서는 못 깨는지를 확인한다.
SOLUTIONS는 막혔을 때 읽는 공략집이기도 하다.
"""
import copy
import sys

import boss_skills
from stages import BOSS_KINDS, LEFT, MOVE_SPEED, RIGHT, SKY_ROOMS, SKY_STEP, STAGES, STEP
from math import hypot

from world import JUMP_DURATION, JUMP_HEIGHT, SKY_FLY, SKY_PIN, Actor, Echo, Motion, World


class Bot:
    def __init__(self, index):
        self.w = World(index)
        self.frames = 0

    @property
    def me(self):  # 지금 조작 중인 대상
        return self.w.recording.preview if self.w.recording else self.w.player

    def tick(self, horizontal=0, stairs=0, jump=False, attack=False, web=False, held=False, dash=False):
        while self.w.pending_monster_echo:
            self.w.resolve_monster_echo()
        self.w.step(Motion(horizontal, stairs, jump, web, held, dash=dash), attack)
        self.frames += 1

    def go(self, x, slash=False):
        """x까지 걷는다. slash=True면 걸으면서 계속 벤다."""
        recording = self.w.recording is not None
        for _ in range(1500):
            if self.w.result != 'playing' or abs(self.me.x - x) < 3:
                return
            assert recording == (self.w.recording is not None), f'녹화 시간이 모자랍니다 → {x} {self}'
            self.tick(1 if x > self.me.x else -1, attack='slash' if slash else False)
        raise AssertionError(f'{x}에 도착하지 못했습니다 {self}')

    def wait(self, seconds, slash=False):
        for _ in range(round(seconds / STEP)):
            self.tick(attack='slash' if slash else False)

    def until(self, condition, limit=30):
        """조건이 참이 될 때까지 가만히 기다린다."""
        for _ in range(round(limit / STEP)):
            if condition(self.w):
                return
            self.tick()
        raise AssertionError(f'기다리던 상황이 오지 않았습니다 {self}')

    def portal_room(self, portal):
        """밟은 하늘 포털 너머 방을 그 방의 공략대로 깨고 열쇠를 들고 돌아온다."""
        assert self.w.room_request is not None and SKY_ROOMS[self.w.room_request] == portal, f'{portal + 1}번 포털에 들어가지 않았습니다 {self}'
        room = Bot.__new__(Bot)
        room.w, room.frames = self.w.enter_room(), 0
        SOLUTIONS[room.w.index + 1](room)
        room.wait(1.0)
        assert room.w.result == 'cleared', f'포털 너머 방을 깨지 못했습니다 {room}'
        self.w = room.w.back_from_room()
        self.frames += room.frames
        assert portal in self.w.sky_keys, f'{portal + 1}번 열쇠를 얻지 못했습니다 {self}'

    def up(self):
        floor = self.me.floor
        self.tick(stairs=1)
        while self.me.elevator_target is not None:
            self.tick()
        assert self.me.floor == floor + 1, f'올라갈 사다리가 없습니다 {self}'

    def down(self):
        floor = self.me.floor
        self.tick(stairs=-1)
        while self.me.elevator_target is not None:
            self.tick()
        assert self.me.floor == floor - 1, f'내려갈 사다리가 없습니다 {self}'

    def jump(self, direction):
        """걷는 방향으로 한 번 뛰어 착지할 때까지 이동한다."""
        self.tick(direction, jump=True)
        while (self.me.jump_time > 0 or self.me.fall_speed) and self.w.result == 'playing':
            self.tick(direction)

    def hop(self, x):
        """보통 점프로 뛰어 x 쪽으로 몸을 틀며 착지한다."""
        self.tick(1 if x > self.me.x else -1, jump=True)
        while (self.me.jump_time > 0 or self.me.fall_speed) and self.w.result == 'playing':
            gap = x - self.me.x
            self.tick(0 if abs(gap) < 3 else 1 if gap > 0 else -1)

    def carry(self, index, x, height, climb=()):
        """마법책 분신: index번 하늘 땅 아래로 가서 마우스로 잡고 (x, 높이)로 끌어다 놓는다.
        climb이 있으면 땅을 쥔 채 그 x들을 차례로 뛰어올라 염력이 닿는 높이까지 간다."""
        self.go(self.w.sky_blocks[index][0])
        bx, bh = self.w.sky_blocks[index]
        assert self.w.sky_grab(bx, bh), f'하늘 땅을 잡지 못했습니다 {self}'
        self.w.sky_drag(x, height)
        if climb:
            self.go(climb[0] - 110)
            for step in climb:
                self.hop(step)
        else:
            self.go(x)
        self.w.sky_release()
        assert self.w.sky_blocks[index] == [x, height], f'하늘 땅이 제자리에 놓이지 않았습니다 {self}'

    def swing_across(self, direction):
        """거미 분신(녹화 중): 앞쪽 조각상에 줄을 쏘고(F) 곧바로 뛰어(Space) 날아가다가, 내려올 때 다음 조각상에
        줄을 다시 쏜다. 낭떠러지 건너편 땅에 내려설 때까지 되풀이한다."""
        self.tick(direction, web=True)
        assert self.me.web_time > 0, f'조각상에 줄이 닿지 않았습니다 {self}'
        while self.w.recording is not None and self.me.web_time > 0:
            me = self.me
            if not me.web_flying:
                self.tick(direction, jump=True)
                continue
            hit = self.w.spider_web_target(me, direction)
            self.tick(direction, web=hit is not None and (hit[0] - me.web_anchor_x) * direction > 60 and me.web_vy < 0)
        assert self.w.recording is not None and not self.w._over_pit(self.me.floor, self.me.x),             f'거미 분신이 낭떠러지에 떨어졌습니다 {self}'

    def follow(self, x):
        """본체: 재현 중인 거미 분신의 60px 뒤를 따라 거미줄 다리를 건너 x까지 간다."""
        for _ in range(round(15 / STEP)):
            if self.w.result != 'playing' or abs(self.me.x - x) < 3:
                return
            direction = 1 if x > self.me.x else -1
            target = x
            if self.w.echo is not None:
                behind = self.w.echo.actor.x - 60 * direction
                target = min(x, behind) if direction > 0 else max(x, behind)
            gap = target - self.me.x
            self.tick(0 if abs(gap) < 3 else 1 if gap > 0 else -1)
        raise AssertionError(f'거미줄을 따라 {x}에 가지 못했습니다 {self}')

    def web_climb(self, direction):
        """거미 분신(녹화 중): 앞 조각상에 줄을 쏘고, ↑로 줄을 감아 올라간 뒤 뛰어 다음(더 높은) 조각상에 줄을 쏜다.
        그 층 맨 위 밧줄 조각상에 매달릴 때까지 되풀이한다."""
        beams = self.w.stage.web_beams

        def beam_of(x, y):
            return next((i for i, b in enumerate(beams) if b.floor == self.me.floor and b.left <= x <= b.right
                         and abs(b.underside - y) < 0.01), None)

        self.tick(direction, web=True)
        current = beam_of(self.me.web_anchor_x, self.me.web_anchor_height + 34)
        assert self.me.web_time > 0 and current is not None, f'조각상에 줄이 닿지 않았습니다 {self}'
        top = max(i for i, b in enumerate(beams) if b.floor == self.me.floor and b.rope)
        for _ in range(round(10 / STEP)):
            me = self.me
            assert self.w.recording is not None and me.web_time > 0, f'거미 분신이 떨어졌습니다 {self}'
            if not me.web_flying:
                if current == top:
                    return
                if me.jump_height < beams[current].underside - 64 and me.web_length > 23:
                    self.tick(stairs=1)   # 줄을 감아 올라간다
                else:
                    self.tick(direction, jump=True)
                continue
            hit = self.w.spider_web_target(me, direction)
            index = beam_of(*hit) if hit else None
            if index is not None and index > current:
                self.tick(direction, web=True)
                current = index
            else:
                self.tick(direction)
        raise AssertionError(f'맨 위 조각상에 오르지 못했습니다 {self}')

    def rope_up(self, beam, direction):
        """본체: beam번 조각상에서 늘어진 거미 밧줄로 가서 ↑로 끝까지 오른 뒤 direction 쪽으로 뛰어내린다."""
        self.until(lambda w: any(rope[5] == beam for rope in w.ropes), limit=8)
        rope = next(rope for rope in self.w.ropes if rope[5] == beam)
        self.go(rope[1])
        for _ in range(round(6 / STEP)):
            if self.me.rope is not None and self.me.base >= rope[3]:
                break
            self.tick(stairs=1)
        else:
            raise AssertionError(f'밧줄 끝까지 오르지 못했습니다 {self}')
        self.jump(direction)
        assert self.w.result == 'playing', f'밧줄에서 뛰어내리다 떨어졌습니다 {self}'

    def rec(self):  # C 키
        self.w.toggle_recording()

    def lever(self):  # E 키
        self.w.toggle_lever()

    def kill(self, kind, within=None):
        """찌르기 거리에서 싸운다. 적이 공격을 준비하면 뒤로 빠졌다가 다시 찌른다. within=(왼쪽, 오른쪽)이면 그 안에서 나온 적만."""
        for _ in range(round((60 if kind == 'echo_knight' else 40) / STEP)):
            targets = [e for e in self.w.enemies if e.spawn.kind == kind and e.actor.floor == self.me.floor
                       and (within is None or within[0] <= e.spawn.point.x <= within[1])]
            if not targets or self.w.result != 'playing':
                return
            foe = min(targets, key=lambda e: abs(e.actor.x - self.me.x))
            gap = foe.actor.x - self.me.x
            toward = 1 if gap >= 0 else -1
            if kind in BOSS_KINDS and 0 < foe.windup <= 0.06 and abs(gap) < 110 and self.me.dash_cooldown == 0:
                self.tick(-toward, dash=True)   # 물러날 곳이 막혔으면 내려치는 순간 대시의 무적으로 피한다
                continue
            if self.dodge(foe):
                continue
            flying = getattr(foe, 'broom', None) is not None and foe.actor.base > 40
            if foe.windup > 0 and abs(gap) < 90:
                self.tick(-toward)
            elif flying and abs(gap) <= 118 and self.me.facing == toward:
                # 하늘의 대마녀: 점프 → 꼭대기에서 2단 점프하며 몸 높이에 닿으면 찌른다.
                me = self.me
                grounded = me.jump_time == 0 and not me.fall_speed
                reach = me.jump_height >= foe.actor.base - 30
                jump = grounded or (not me.air_jumped and me.jump_time >= 0.28)
                self.tick(jump=jump, attack='thrust' if reach else False)
            elif foe.windup > 0 and abs(gap) < 90:
                self.tick(-toward)
            elif abs(gap) > 118 or self.me.facing != toward:
                self.tick(toward)
            else:
                self.tick(attack='thrust')
        raise AssertionError(f'{kind}을 처치하지 못했습니다 {self}')

    def dodge(self, foe):
        """보스 스킬을 피한다. 피하는 동작을 했으면 True."""
        me = self.me
        skill = boss_skills.current(foe)
        # 돌진과 충격파는 예고가 끝나는 순간에 맞춰 뛴다.
        if skill and skill.name == 'charge' and skill.telegraph - 0.08 <= foe.skill_time and me.jump_time == 0 \
                and foe.skill_time < skill.telegraph + skill.active:
            self.tick(jump=True)
            return True
        if skill and skill.name == 'chain' and foe.skill_time < skill.telegraph + skill.active:
            # 쇠사슬은 닿는 거리 밖으로 물러난다.
            self.tick(-1 if foe.actor.x > me.x else 1)
            return True
        field = self.w.gravity_field
        if field is not None and field.captured:
            self.tick(field.escape_direction)   # 중력 구체에 갇히면 반대 방향키로 버틴다
            return True
        if (skill and skill.name == 'laser' and foe.skill_time < skill.telegraph + skill.active
                and (me.x - foe.actor.x) * foe.actor.facing > 0
                and abs(me.jump_height + boss_skills.BODY - foe.laser_h) <= boss_skills.LASER_HALF + 10):
            # 광선이 지나갈 높이에 있으면 예고 끝 무렵 점프하고, 꼭대기에서 2단 점프해 그 높이를 벗어난다.
            grounded = me.jump_time == 0 and not me.fall_speed
            if grounded and foe.skill_time >= skill.telegraph - 0.2:
                self.tick(jump=True)
                return True
            if not grounded and not me.air_jumped and me.jump_time >= 0.28:
                self.tick(jump=True)
                return True
        if (skill and skill.name == 'hands' and foe.skill_time < skill.telegraph
                and abs(me.x - foe.mark_x) < 110):
            # 그림자 손아귀: 발밑에 번진 어둠 밖으로 걸어 나간다.
            self.tick(1 if me.x >= foe.mark_x else -1)
            return True
        for effect in self.w.boss_effects:
            if effect.homing or effect.wave:
                # 추적 불빛·해골 불꽃·도깨비불은 닿기 직전 그쪽으로 대시해 무적 시간으로 뚫고 지나간다.
                gap = effect.x - me.x
                if (abs(gap) < 70 and abs(effect.lift + effect.hit_up - me.jump_height - boss_skills.BODY) < 60
                        and me.dash_cooldown == 0):
                    self.tick(1 if gap > 0 else -1, dash=True)
                    return True
                continue
            if effect.hit_at is None or effect.floor != me.floor or effect.age > effect.hit_at + effect.hit_for:
                continue
            distance = effect.x - me.x
            if effect.jumpable and not effect.speed:
                # 바닥에서 솟는 그림자 손은 솟기 직전에 뛰고, 정점에서 2단 점프로 손이 가라앉을 때까지 버틴다.
                if abs(distance) < effect.radius + 12 and effect.age >= effect.hit_at - 0.2:
                    if me.jump_time == 0 or (not me.air_jumped and me.jump_time >= 0.28):
                        self.tick(jump=True)
                        return True
            elif effect.jumpable:
                # 다가오는 구체는 닿기 직전에 뛰어넘는다.
                if me.jump_time == 0 and abs(distance) < 70:
                    self.tick(jump=True)
                    return True
            elif abs(distance) < effect.radius + 12:
                # 낙뢰 문양에서는 걸어서 벗어난다.
                self.tick(-1 if distance > 0 else 1)
                return True
        if me.jump_time > 0:
            self.tick()
            return True
        return False

    def __repr__(self):
        w = self.w
        echo = f'{w.echo.actor.x:.0f}/{w.echo.actor.floor + 1}F' if w.echo else '없음'
        enemies = ' '.join(f'{e.spawn.kind}@{e.actor.x:.0f}/{e.actor.floor + 1}F' for e in w.enemies)
        return (f'[{self.frames * STEP:.1f}초 본체 {w.player.x:.0f}/{w.player.floor + 1}F 체력 {w.health} '
                f'분신 {echo} 결과 {w.result} | {enemies} | {w.message}]')


def enemy(w, kind):
    return next(e.actor for e in w.enemies if e.spawn.kind == kind)


SOLUTIONS = {}


def solution(number):
    def register(function):
        SOLUTIONS[number] = function
        return function
    return register


@solution(1)
def stage_1(b):
    # 1층: 분신이 A 발판을 오래 밟는 동안 A·B 문 사이의 거미를 잡는다.
    b.go(500)
    b.rec()
    b.go(267)
    b.wait(5)
    b.rec()
    b.go(1000, slash=True)
    while sum(e.spawn.kind == 'crawler' for e in b.w.enemies) > 1:
        b.tick(attack='slash')
    # A 문 바로 뒤에서 녹화하면 A 문이 열려 있어 분신이 B 발판으로 돌아갈 수 있다.
    b.go(790)
    b.rec()
    b.go(430)
    b.wait(6)
    b.rec()
    b.wait(0.6)    # 분신이 A 문을 지나갈 때까지 문 곁에 있는다
    b.go(1600)
    b.kill('crawler')
    b.go(1950)
    b.up()
    # 2층: 독 웅덩이는 쉬는 바닥 사이를 점프로 건넌다. 웅덩이마다 한 번은 맞는다.
    b.go(1505)
    b.jump(-1)
    b.go(1278)
    b.jump(-1)
    b.jump(-1)
    b.go(900)
    b.jump(-1)
    b.jump(-1)
    b.jump(-1)
    b.go(350)
    b.up()
    # 3층: 거미 분신이 조각상에 줄을 쏘고 뛰기를 되풀이해 낭떠러지를 건너고,
    # 본체는 그 아래 쳐지는 거미줄(3초 뒤 끊어진다)을 따라 건넌다.
    b.go(540)
    b.w.start_recording('crawler')   # C → 거미 분신
    b.swing_across(1)
    b.rec()
    b.follow(1800)
    b.go(2100)


@solution(2)
def stage_2(b):
    """거미 둥지: 사냥터 → 거미줄 협곡과 A 문 → 밧줄 탑 → 꼭대기 출구. 모든 길을 거미 분신으로 연다."""
    b.w.xp = 45                        # 1스테이지를 지나며 쌓인 경험치 (레벨 2)
    b.w.health = b.w.max_health
    b.kill('crawler', within=(150, 560))
    assert b.w.hunt_open(b.w.stage.hunt_gates[0]), f'사냥 문이 열리지 않았습니다 {b}'
    # [거미줄 협곡] 거미 분신이 조각상 셋을 타고 건너, A 문을 타고 넘어(↑) A 발판에서 녹화가 끝날 때까지 버틴다.
    b.go(680)
    b.w.start_recording('crawler')
    b.swing_across(1)
    door, plate = b.w.stage.gates[0].door, b.w.stage.gates[0].plate
    if b.me.x < door.x:
        b.go(door.x - 30)
        b.tick(stairs=1)
        while b.me.door_climb_time > 0:
            b.tick()
    b.go(plate.x)
    b.until(lambda w: w.recording is None, limit=12)
    # 본체는 거미줄을 따라 건너고, 분신이 발판을 밟아 A 문이 열리면 지나간다.
    b.follow(1330)
    b.until(lambda w: w.doors[0].open, limit=8)
    b.go(1700)
    b.kill('crawler', within=(1700, 2192))
    # [밧줄 탑] 거미 분신이 조각상 셋을 줄을 감아 오르며 잡고, 본체는 재현 때 늘어진 밧줄로 턱 셋을 오른다.
    b.go(2130)
    b.w.start_recording('crawler')
    b.web_climb(-1)
    b.wait(0.5)                        # 맨 위 조각상에 잠깐 매달려 있다가 녹화를 끝낸다
    b.rec()
    for beam in (3, 4, 5):             # 밧줄 → 턱(185) → 밧줄 → 턱(420) → 밧줄 → 턱(655)
        b.rope_up(beam, -1)
    b.go(1110)


@solution(3)
def stage_3(b):
    # 간수의 방: 층 없는 보스방에서 쇠사슬 간수를 처치하고 출구로.
    b.kill('jailer_boss')
    b.go(2100)


@solution(4)
def stage_4(b):
    # 하늘 섬 21개가 1~21단에 하나씩 좌우로 떠다닌다. 바로 윗단 섬이 점프 거리 안에 오면 뛰어 갈아타며
    # 1번(왼쪽 10단)·2번(왼쪽 22단)·3번(오른쪽 16단) 턱에 오른다. 서 있는 섬이 실어 나르니 기다리면 온다.
    half = b.w.stage.sky.width / 2
    reach = MOVE_SPEED * JUMP_DURATION * 0.7

    def footing():
        """지금 선 자리(바닥·섬·턱)에서 걸어도 안 떨어지는 x 범위."""
        me = b.me
        if me.base == 0:
            return LEFT + 10, RIGHT - 10
        for x, height in b.w.sky_blocks:
            if height == me.base and abs(me.x - x) <= half:
                return x - half + 8, x + half - 8
        for p in b.w.stage.platforms:
            if p.height == me.base and p.left <= me.x <= p.right:
                return p.left + 8, p.right - 8
        return me.x, me.x

    def jump_to(target):
        """보통 점프로 뛰어 움직이는 target()을 따라가며 착지한다."""
        b.tick(1 if target() > b.me.x else -1, jump=True)
        while (b.me.jump_time > 0 or b.me.fall_speed) and b.w.result == 'playing':
            gap = target() - b.me.x
            b.tick(0 if abs(gap) < 3 else 1 if gap > 0 else -1)

    def climb(ledge, ledge_x):
        """ledge단 턱(ledge_x)까지 한 단씩 섬을 갈아탄다. 떨어지면 바닥부터 다시."""
        for _ in range(round(600 / STEP)):
            k = round(b.me.base / SKY_STEP)
            if k == ledge:
                return
            target = (lambda: ledge_x) if k == ledge - 1 else (lambda i=k: b.w.sky_blocks[i][0])  # i번 섬은 i+1단
            if abs(target() - b.me.x) <= reach:
                jump_to(target)
                continue
            left, right = footing()                # 윗단 섬 쪽 끝으로 가서 기다린다
            gap = min(max(target(), left), right) - b.me.x
            b.tick(0 if abs(gap) < 3 else 1 if gap > 0 else -1)
        raise AssertionError(f'{ledge}단 턱에 오르지 못했습니다 {b}')

    def descend(direction):
        """턱이나 섬 끝으로 걸어 나가 바닥까지 내려온다 (떨어지다 섬에 앉으면 그 섬에서도 걸어 나간다)."""
        for _ in range(round(20 / STEP)):
            if b.me.base == 0 and not b.me.fall_speed:
                return
            b.tick(direction)
        raise AssertionError(f'바닥으로 내려오지 못했습니다 {b}')

    b.kill('magic_book')
    b.kill('potion_slime')
    b.kill('magic_armor')
    climb(3, 115)
    b.portal_room(0)
    climb(7, 115)
    b.portal_room(1)
    descend(1)
    climb(5, 2125)
    b.portal_room(2)
    descend(-1)
    b.go(1240)


def portal_room(b):
    """하늘 포털 너머 방: 몬스터를 모두 처치하면 가운데에 포털이 열리고, 다가가면 빨려 들어간다."""
    for kind in ('magic_armor', 'potion_slime', 'magic_book'):
        b.kill(kind)
    assert not b.w.enemies and b.w.portal_opened_at is not None, f'몬스터를 다 잡았는데 포털이 열리지 않았습니다 {b}'
    b.go(b.w.stage.exit.x)


for _room in SKY_ROOMS:
    SOLUTIONS[_room + 1] = portal_room


@solution(10)
def stage_10(b):
    """마녀의 실험 금고: 물약 슬라임 분신이 포털을 던지고, 마법책 분신이 포털 붙은 땅을 금고에 밀어 넣는다."""
    def attempt(w, frames, facing):
        """facing 쪽을 보고 F를 frames 프레임 눌렀다 떼고, 물약이 떨어질 때까지 기다린다. 새 포털을 돌려준다."""
        slot = w.portal_next
        steps = 0
        if w.recording.preview.facing != facing:
            w.step(Motion(facing))
            steps += 1
        for _ in range(frames):
            w.step(Motion(web_aiming=True))
        w.step(Motion())
        steps += frames + 1
        while w.potions and w.recording is not None:
            w.step(Motion())
            steps += 1
        return (w.portals[slot] if w.portal_next != slot else None), steps

    def throw(wanted, facings=(1, -1)):
        """wanted(포털)이 참이 되는 힘과 방향을 미리 돌려 보고 그대로 던진다. 없으면 한 프레임 기다린다."""
        for _ in range(round(15 / STEP)):
            for facing in facings:
                for frames in range(0, 61, 3):
                    portal, _ = attempt(copy.deepcopy(b.w), frames, facing)
                    if portal is not None and wanted(portal):
                        portal, steps = attempt(b.w, frames, facing)
                        b.frames += steps
                        assert portal is not None and wanted(portal), f'미리 본 대로 떨어지지 않았습니다 {b}'
                        return
            b.tick()
        raise AssertionError(f'물약을 맞힐 때를 찾지 못했습니다 {b}')

    def enter():
        """본체가 가까운 포털로 걸어 들어가 다른 쪽 포털로 나온다."""
        points = [b.w.portal_point(i) for i in range(2)]
        index = min(range(2), key=lambda i: abs(points[i][1] - b.me.x))
        for _ in range(round(10 / STEP)):
            _, x, height = b.w.portal_point(1 - index)
            if abs(b.me.x - x) < 1 and b.me.base == height:
                return
            gap = b.w.portal_point(index)[1] - b.me.x
            b.tick(0 if abs(gap) < 2 else 1 if gap > 0 else -1)
        raise AssertionError(f'포털로 들어가지 못했습니다 {b}')

    def on_ground(near, far):
        return lambda p: p[1] is None and p[3] == 0 and near <= p[2] <= far

    b.kill('potion_slime')
    b.kill('magic_book')
    # [창살 방] 발밑(왼쪽)과 창살 너머에 포털 한 쌍
    b.go(600)
    b.w.start_recording('potion_slime')
    throw(on_ground(500, 600), (-1,))
    throw(on_ground(670, 800), (1,))
    b.rec()
    enter()
    assert b.me.x > 650, f'창살을 건너지 못했습니다 {b}'
    # [독 수조] 떠다니는 땅 A(0번)에 포털을 붙이고 건너가 실려 간다
    b.go(790)
    b.w.start_recording('potion_slime')
    throw(on_ground(700, 800), (-1,))
    throw(lambda p: p[1] == 0)
    b.rec()
    enter()
    b.until(lambda w: w.sky_blocks[0][0] >= 1150)
    for _ in range(round(3 / STEP)):
        if b.me.base == 0 and not b.me.fall_speed and b.me.x > 1300:
            break
        b.tick(1)
    assert b.me.x > 1300 and b.me.base == 0, f'독 수조를 건너지 못했습니다 {b}'
    # [봉인 금고] 땅 B(1번)에 포털을 붙이고, 마법책 분신이 땅 B를 금고 안으로 끌어 놓는다
    b.go(1500)
    b.w.start_recording('potion_slime')
    throw(on_ground(1400, 1490), (-1,))
    throw(lambda p: p[1] == 1)
    b.rec()
    b.w.start_recording('magic_book')
    b.go(1720)
    b.until(lambda w: w.sky_grab(*w.sky_blocks[1]), limit=8)
    b.w.sky_drag(1900, 290)
    b.wait(0.5)   # 잡은 땅이 날아와 자리를 잡을 때까지
    b.w.sky_release()
    b.rec()
    _, x, height = b.w.portal_point(1 - b.w.portal_next)
    assert 1780 < x < 2120, f'포털이 금고에 들어가지 않았습니다 {b} {x}'
    enter()
    b.go(2050)
    assert b.w.portal_open, f'금고 스위치가 눌리지 않았습니다 {b}'
    b.go(2155)


@solution(5)
def stage_5(b):
    b.until(lambda w: enemy(w, 'magic_armor_guard').x < 1300)   # 갑옷이 왼쪽에 있어야 분신이 오래 버틴다
    b.rec()
    b.go(2030)
    b.down()
    b.go(1700)
    b.wait(3.0)
    b.rec()
    b.go(1320, slash=True)
    b.until(lambda w: enemy(w, 'magic_armor_guard').x >= 1540, limit=5)
    b.lever()
    assert b.w.isolation_closed, f'갑옷을 가두지 못했습니다 {b}'
    b.go(800)
    b.kill('magic_armor')
    b.kill('potion_slime')
    b.go(180)
    b.up()
    b.up()
    b.go(104)


@solution(6)
def stage_6(b):
    # 대마녀의 방: 층 없는 보스방에서 대마녀를 처치하고 출구로.
    b.kill('grand_witch')
    b.go(2100)


@solution(11)
def stage_11(b):
    """사슬 뱀의 탑. 1층: 뱀 꼬리에 올라 머리 바로 뒤를 따라 걸으면 세로 몸을 타고 2층으로 오른다.
    2층: 뱀 B를 따라가다 B가 솟은 윗길(200)에서 바로 위를 지나는 뱀 C(240)로 뛰어 갈아타고 C를 따라 3층으로.
    3층: 시작 바닥 끝(375)에 서 있으면 도는 뱀이 태워 올린다. 윗길 오른쪽 끝(1430 넘음)에서 출구 쪽으로 뛰어내린다."""
    import chain_snake
    tower = b.w.stage.tower

    def head(index):
        return chain_snake.point(tower.snakes[index], b.w.snake_state[index][0])

    def toward(x, margin=3):
        return 1 if x > b.me.x + margin else (-1 if x < b.me.x - margin else 0)

    for _ in range(round(150 / STEP)):
        w, me = b.w, b.me
        if w.result != 'playing':
            return
        grounded = me.jump_time == 0 and not me.fall_speed
        under = w._snake_under(me)
        if me.floor == 0:
            b.tick(toward(head(0)[0] - 20))
        elif me.floor == 1:
            if under and under[0] == 2 or me.base >= 230:
                b.tick(toward(head(2)[0] + 20))
            elif grounded and me.base == 200 and w.snake_state[1][1]:
                above = [s for s in chain_snake.surfaces(tower.snakes[2], w.snake_state[2][0])
                         if s[1] <= me.x <= s[2] and s[3] == 240]
                b.tick(toward(head(1)[0] + 20), jump=bool(above))
            else:
                b.tick(toward(head(1)[0] + 20) if w.snake_state[1][1] else -1)
        elif me.base == 0 and me.x < 400 and grounded and under is None:
            b.tick(toward(375, 1))
        elif under is not None and me.base >= 300 and me.x > 1430 and grounded:
            b.tick(1, jump=True)
        elif not grounded:
            b.tick(1 if me.x < 2100 else 0)
        elif me.base == 0 and me.x >= 1650:
            b.tick(toward(2100))
        else:
            hx, _, dx, _ = head(3)
            b.tick(toward(hx - 20 * dx) if me.base >= 300 else 0)
    raise AssertionError(f'사슬 뱀의 탑을 오르지 못했습니다 {b}')


@solution(7)
def stage_7(b):
    b.go(400)
    b.rec()
    b.go(245)
    b.wait(0.4)
    b.rec()
    b.go(600)
    b.kill('broken_jester')
    b.go(1300)
    b.up()
    b.rec()
    b.down()
    b.go(1490)      # B 발판: 본체가 B 문에 들어설 때까지
    b.wait(0.3)
    b.go(800)       # 아래층 동시 발판에 서서 기다린다
    b.rec()
    b.go(800)       # 위층 동시 발판에서 분신이 도착하기를 기다린다
    b.until(lambda w: w.sync_unlocked, limit=6)
    b.go(520)
    b.kill('cursed_lantern')
    b.go(150)
    b.up()
    b.go(1850)
    b.up()
    b.go(150)
    b.up()
    b.go(2100)


@solution(8)
def stage_8(b):
    b.go(380)
    b.rec()
    b.go(220)
    b.wait(0.5)
    b.rec()
    b.go(690)
    b.up()
    b.rec()
    b.go(548)
    b.wait(0.6)
    b.rec()
    b.go(870)
    b.go(950, slash=True)
    b.up()
    b.kill('cursed_lantern')
    b.go(1000)
    b.rec()         # 첫 분신: 함정을 비추며 앞서 걷는다
    b.go(1850)
    b.wait(0.6)
    b.rec()
    b.go(1230)
    b.jump(1)
    b.go(1450)
    b.jump(1)
    b.go(1670)
    b.jump(1)
    b.go(1850)
    b.rec()         # 새 분신: 되돌아가 D 발판을 밟는다
    b.go(1080)
    b.wait(0.8)
    b.rec()
    b.go(2100)


@solution(9)
def stage_9(b):
    b.go(350)
    b.rec()
    b.go(252)
    b.wait(0.6)
    b.rec()
    b.go(670)
    b.up()
    b.until(lambda w: enemy(w, 'broken_jester').x > 1050)  # 광대가 B 발판에서 멀 때
    b.rec()
    b.down()
    b.go(820)
    b.wait(1.5)
    b.rec()
    b.go(1060)
    b.kill('cursed_lantern')
    b.go(1300)
    b.up()
    b.rec()
    b.go(1470)
    b.wait(1.5)
    b.rec()
    b.down()
    b.wait(0.5)
    b.up()
    b.go(1472)
    b.until(lambda w: w.guard_open_time > 0)
    b.go(1560)
    b.rec()         # 함정을 비출 분신
    b.go(2000)
    b.wait(0.5)
    b.rec()
    b.go(1630)
    b.jump(1)
    b.go(1830)
    b.jump(1)
    b.go(2000)
    b.up()
    b.kill('echo_knight')
    b.go(2100)


def rush(index):
    """분신 없이 출구 쪽으로 달리며 베기만 한다. 사다리가 보이면 출구 층 쪽으로 탄다."""
    bot = Bot(index)
    stage = STAGES[index]
    for _ in range(round(40 / STEP)):
        if bot.w.result != 'playing':
            break
        player = bot.w.player
        stairs = (stage.exit.floor > player.floor) - (stage.exit.floor < player.floor)
        bot.tick(1 if stage.exit.x > player.x else -1, stairs=stairs, attack='slash')
    return bot.w.result


def check_balance():
    """BALANCE.md의 레벨 표와 피해 공식이 코드와 맞는지 확인한다."""
    w = World(0)
    assert (w.level, w.max_health, w.health, w.xp_progress()) == (1, 25, 25, (0, 30))
    for xp, level, top in ((29, 1, 25), (30, 2, 28), (75, 3, 31), (575, 8, 46), (915, 10, 52), (5000, 10, 52)):
        w.xp = xp
        assert (w.level, w.max_health) == (level, top), (xp, w.level, w.max_health)
    assert w.xp_progress()[1] == 0                      # 최대 레벨
    w = World(0)                                        # 거미: 체력 10, 피해 7
    crawler = w.enemies[0]
    assert (crawler.health, w.enemy_damage(crawler)) == (10, 7)
    w.player.x, w.player.facing, crawler.actor.x = 500, 1, 560
    w.weapon_index, w.attack_kind = 2, 'slash'          # 한손검 베기 1레벨: 4 + 0 + 1 = 5
    w._apply_attack()
    assert crawler.health == 5, crawler.health
    late = World(8)                                     # 후반 강화 ×1.6
    thief = next(e for e in late.enemies if e.spawn.kind == 'time_thief')
    assert (thief.health, late.enemy_damage(thief)) == (32, 11)
    early = World(4)
    guard = next(e for e in early.enemies if e.spawn.kind == 'magic_armor_guard')
    assert early.enemy_damage(guard) == 10               # 25의 40%
    late.hurt(99, '테스트')
    assert (late.health, late.result) == (0, 'defeated')


def check_boss_warp():
    for index, stage in enumerate(STAGES):
        if not any(spawn.kind in BOSS_KINDS for spawn in stage.enemies):
            continue
        w = World(index)
        w.warp_to_boss()
        boss = next(e for e in w.enemies if e.spawn.kind in BOSS_KINDS)
        assert w.player.floor == boss.actor.floor and abs(w.player.x - boss.actor.x) > 200, (stage.title, w.player)
        for _ in range(30):                 # 도착하자마자 맞거나 끼지 않는다.
            w.step(Motion())
        assert w.result == 'playing' and w.health == w.max_health, stage.title


def check_floor_warp():
    """- 키: 스테이지의 모든 층으로 옮겨지고, 도착한 자리에서 바로 떨어지거나 다치지 않는다."""
    for index, stage in enumerate(STAGES):
        for floor in range(stage.floors):
            w = World(index)
            w.enemies = []
            assert w.warp_to_floor(floor), (stage.title, floor)
            for _ in range(30):
                w.step(Motion())
            assert (w.player.floor, w.result, w.health) == (floor, 'playing', w.max_health), (stage.title, floor, w.player)
    w = World(0)
    w.start_recording()
    assert not w.warp_to_floor(2) and w.player.floor == 0   # 녹화 중에는 옮기지 않는다


def check_late_stage_monsters():
    allowed = {'time_thief', 'cursed_lantern', 'broken_jester'}
    for stage in STAGES[6:9]:
        kinds = {spawn.kind for spawn in stage.enemies} - BOSS_KINDS
        assert kinds and kinds <= allowed, (stage.title, kinds)


def check_puzzles():
    """기획서 그림대로 바꾼 장치가 분신 없이는 통과되지 않는지 확인한다."""
    # 보스방 출구 포털: 보스를 처치하면 열리고, 가만히 서 있어도 가까우면 빨려 들어가 클리어, 멀면 그대로다.
    for distance, cleared in ((200, True), (320, False)):
        w = World(2)
        boss = next(e for e in w.enemies if e.spawn.kind in BOSS_KINDS)
        boss.health = 1
        w.player.x, w.player.facing = boss.actor.x - 40, 1
        w._attack()
        w._apply_attack()
        w.enemies = []
        w.player.x = w.stage.exit.x - distance
        for _ in range(round(4 / STEP)):
            w.step(Motion())
        assert w.portal_opened_at is not None and (w.result == 'cleared') == cleared, ('포털', distance, w.result, w.player.x)

    # 대시·2단 점프: 1스테이지와 2스테이지 점프맵에서는 못 쓰고, 간수의 방부터 쓴다.
    for index in (0, 1):
        w = World(index)
        w.enemies = []
        x = w.player.x
        w.step(Motion(dash=True))
        assert w.player.x - x < 10, ('대시를 쓸 수 없는 구역에서 대시했습니다', index)
    w = World(2)
    w.enemies = []
    x = w.player.x
    w.step(Motion(dash=True))
    assert not w.hurt(5, '대시'), '대시하는 동안 맞았습니다'
    for _ in range(20):
        w.step(Motion())
    assert 120 < w.player.x - x < 170, ('대시 거리', w.player.x - x)
    top = 0
    for frame in range(90):
        w.step(Motion(jump=frame in (0, 15)))
        top = max(top, w.player.jump_height)
    landed = w.player.jump_time == 0 and not w.player.fall_speed   # 바닥이나 발판(높이 45)에 내려섰다
    assert top > JUMP_HEIGHT + 20 and landed, ('2단 점프', top, w.player)
    # 점프 → 대시 → 2단 점프 → 대시: 공중에서는 점프 한 번에 대시 한 번
    w = World(2)
    w.enemies = []
    w.player.x = 1000
    dashes = 0
    for frame in range(60):
        before = w.player.dash_time
        w.step(Motion(1, jump=frame in (0, 18), dash=frame in (4, 10, 22)))
        dashes += w.player.dash_time > before
    assert dashes == 2, ('공중 대시는 1단·2단 점프에 한 번씩입니다', dashes)
    # 간수의 방 발판: 점프로는 못 오르고 2단 점프로 120→240, 가운데 220은 2단 점프로는 못 닿고 점프 + 위 대시로 오른다.
    def climb(x, base, jumps, dash_at=None):
        w = World(2)
        w.enemies = []
        w.player.x, w.player.base = x, base
        for frame in range(150):
            w.step(Motion(jump=frame in jumps, dash=frame == dash_at, dash_up=frame == dash_at))
        return w.player.base
    assert (climb(330, 0, (0,)), climb(330, 0, (0, 24)), climb(410, 120, (0, 24))) == (0, 120, 240), '간수의 방 양옆 발판'
    assert (climb(970, 0, (0, 24)), climb(970, 0, (0,), dash_at=24)) == (0, 220), '간수의 방 가운데 발판'
    # 위 대시는 약 145 솟구쳤다가 떨어지고, 대각선 위 대시는 옆·위로 약 100씩 간다.
    # 솟구치는 동안 Space는 1단 점프가 아니라 2단 점프로 친다 (공중 점프를 공짜로 얻지 못한다).
    for horizontal, up, side in ((0, 140, (-5, 5)), (1, 95, (90, 115))):
        w = World(2)
        w.enemies = []
        w.player.x = 1000
        top, jumps = 0, 0
        for frame in range(90):
            w.step(Motion(horizontal if frame == 0 else 0, jump=frame in (5, 7), dash=frame == 0,
                          dash_up=frame == 0))
            top = max(top, w.player.dash_to_h)
            jumps += frame in (5, 7) and w.player.jump_time == STEP
        assert top > up and side[0] < w.player.dash_to - w.player.dash_from < side[1], ('위·대각선 대시', top, w.player)
        assert jumps == 1 and w.player.jump_time == 0 and not w.player.fall_speed, ('위 대시 뒤 착지', jumps, w.player)

    # 간수의 낙석: 맞으면 잠시 기절해 걷기·점프·공격이 안 되고, 기절이 풀리면 다시 움직인다.
    w = World(2)
    w.warp_to_boss()
    w.enemies = []
    w.boss_effects.append(boss_skills.Effect('dirt-explosion', w.player.x, w.player.floor, hit_at=0.0,
                                             hit_for=0.10, radius=38, damage=5))
    w.step(Motion())
    start = w.player.x
    for _ in range(30):
        w.step(Motion(1, jump=True), 'slash')
    assert w.confused > 0 and w.player.x == start and w.player.jump_time == 0, '낙석에 맞고도 움직였습니다'
    for _ in range(round(boss_skills.CONFUSED_SECONDS / STEP)):
        w.step(Motion(1))
    assert w.player.x > start, '기절이 풀리지 않았습니다'

    # 마녀의 실험 금고: 금고 결계에 닿은 물약은 깨지고, 독 수조 위 땅 A는 염력으로 잡히지 않는다.
    w = World(9)
    w.enemies = []
    w.potions.append([1900, 0, 400, 0, 0])
    for _ in range(round(1 / STEP)):
        w.step(Motion())
    assert not w.potions and w.portals == [None, None], ('결계 안에 포털이 생겼습니다', w.portals)
    w.player.x = w.sky_blocks[0][0] - 150
    w.start_recording('magic_book')
    assert not w.sky_grab(*w.sky_blocks[0]), '염력이 통하지 않아야 할 땅을 잡았습니다'

    # 거미 둥지: 사냥터 거미가 남아 있으면 사냥 문이 닫혀 있고, 거미줄 없이 낭떠러지를 건너면 떨어진다.
    w = World(1)
    for _ in range(round(6 / STEP)):
        w.health = w.max_health
        w.step(Motion(1))
    assert w.player.x < w.stage.hunt_gates[0].door.x, '몬스터가 남았는데 사냥 문을 지났습니다'
    w.enemies = []
    for _ in range(round(6 / STEP)):
        w.step(Motion(1))
    assert w.result == 'defeated', ('거미줄 없이 낭떠러지를 건넜습니다', w.player)
    # 건너편 A 문은 발판을 밟고 있는 동안만 열린다 (본체는 문 앞에서 발판에 갈 수 없다).
    w = World(1)
    w.enemies = []
    w.player.x = 1350
    for _ in range(round(3 / STEP)):
        w.step(Motion(1, jump=True))
    assert w.player.x < w.stage.gates[0].door.x, ('발판 없이 A 문을 지났습니다', w.player)
    # 걸어가는 거미 분신은 낭떠러지에 떨어져 건너편까지 거미줄을 치지 못하고, 밧줄도 만들지 못한다.
    w = World(1)
    w.enemies = []
    w.echo = Echo(Actor(680, 0), (Motion(1),) * 120, monster_kind='crawler')
    for _ in range(120):
        w.step(Motion())
    assert w.echo is None and not any(w.bridge_tiles[0][5:]) and not w.ropes, '걸어서 거미줄을 끝까지 쳤습니다'
    # 거미 밧줄: 재현 거미가 밧줄 조각상에 줄을 붙이면 밧줄이 생기고, 본체는 ↑로 끝까지 오른다.
    # 6초 뒤 밧줄이 끊어지면 매달린 본체는 떨어진다.
    w = World(1)
    w.enemies = []
    w.echo = Echo(Actor(2130, 0, -1), (Motion(-1, web=True, aim_x=-1),) + (Motion(),) * 600, monster_kind='crawler')
    w.step(Motion())
    assert len(w.ropes) == 1 and w.ropes[0][2:4] == [0.0, 155], w.ropes
    w.player.x = w.ropes[0][1]
    for _ in range(round(1.5 / STEP)):
        w.step(Motion(stairs=1))
    assert w.player.rope is not None and w.player.base == 155, ('밧줄을 오르지 못했습니다', w.player)
    for _ in range(round(5.5 / STEP)):
        w.step(Motion())
    assert w.player.rope is None and w.player.base == 0 and not w.ropes, ('끊어진 밧줄에 매달려 있습니다', w.player)
    # 출구는 꼭대기 턱 높이에서만 나간다.
    w = World(1)
    w.enemies = []
    w.player.x = w.stage.exit.x
    w.step(Motion())
    assert w.result == 'playing', '바닥에서 꼭대기 출구로 나갔습니다'
    w.player.base = w.stage.exit_height
    w.step(Motion())
    assert w.result == 'cleared', ('꼭대기 출구로 나가지 못했습니다', w.result)
    # 거미 알: 닿으면 경험치를 얻고 한 번만 먹는다.
    w = World(1)
    w.enemies = []
    x, height, xp = w.stage.eggs[0]
    w.player.x, w.player.base = x, height
    w.step(Motion())
    assert w.xp == xp and not w.eggs, (w.xp, w.eggs)

    # 하늘 땅: 빠진 단이 있어 디딤돌만으로는 포털 턱에 못 오르고, 출구는 열쇠 3개를 모으기 전엔 잠겨 있다.
    w = World(3)
    sky = w.stage.sky
    w.enemies = []
    for block in w.sky_blocks:     # 떠다니는 섬은 가운데로 치워 둔다 (몇 초 안에는 벽까지 못 온다)
        block[0] = 1120
    for start, hops in ((300, (230, 130)), (1900, (2010, 2110))):
        w.player.x, w.player.base = start, 0
        for x in hops:
            w.step(Motion(1 if x > w.player.x else -1, jump=True))
            for _ in range(60):
                w.step(Motion(1 if x > w.player.x + 3 else -1 if x < w.player.x - 3 else 0))
        assert w.player.base <= SKY_STEP and w.room_request is None, ('빠진 단을 뛰어 올랐습니다', w.player)
    w.player.x, w.player.base = w.stage.exit.x, 0
    for _ in range(10):
        w.step(Motion())
    assert w.result == 'playing', '열쇠 없이 출구로 나갔습니다'
    # 염력은 녹화 중인 마법책 분신 둘레에만 닿고, 다른 분신이나 본체로는 땅을 못 잡는다.
    assert not w.sky_grab(*sky.blocks[0]), '마법책 분신 없이 하늘 땅을 잡았습니다'
    w.player.x = 100
    w.start_recording('magic_book')
    # 멀리 있는 땅도 잡히고, 순간이동하지 않고 SKY_FLY 빠르기로 분신 둘레 reach 안까지 날아온다.
    far = list(w.sky_blocks[3])
    assert w.sky_grab(*far), '멀리 있는 하늘 땅을 잡지 못했습니다'
    w.step(Motion())
    assert 0 < hypot(w.sky_blocks[3][0] - far[0], w.sky_blocks[3][1] - far[1]) <= SKY_FLY * STEP + 1, '잡은 땅이 날아오지 않았습니다'
    for _ in range(round(3 / STEP)):
        w.step(Motion())
    assert hypot(w.sky_blocks[3][0] - 100, w.sky_blocks[3][1] - 30) <= sky.reach + 1, ('잡은 땅이 분신 곁에 오지 않았습니다', w.sky_blocks[3])
    w.sky_release()
    w.sky_pin[3] = 0.0
    # 섬은 떠다니고, 위에 선 본체를 실어 나른다. 분신이 잡아 놓은 섬은 SKY_PIN초 멈췄다가 다시 떠다닌다.
    w.sky_blocks[0] = [100, SKY_STEP]
    assert w.sky_grab(100, SKY_STEP), '가까운 하늘 땅을 잡지 못했습니다'
    w.sky_drag(160, SKY_STEP)
    for _ in range(10):   # 60px를 날아온다
        w.step(Motion())
    w.sky_release()
    for _ in range(round((SKY_PIN - 0.2) / STEP)):
        w.step(Motion())
    assert w.sky_blocks[0] == [160, SKY_STEP], ('놓은 섬이 멈춰 있지 않았습니다', w.sky_blocks[0])
    w.cancel_recording()
    w.player.x, w.player.base = 160, SKY_STEP
    for _ in range(round(1 / STEP)):
        w.step(Motion())
    assert w.sky_blocks[0][0] != 160, '멈춘 섬이 다시 떠다니지 않았습니다'
    assert w.player.base == SKY_STEP and abs(w.player.x - w.sky_blocks[0][0]) < 1, ('섬이 본체를 실어 나르지 않았습니다', w.player)
    # 섬 위에 선 채로도 분신을 녹화하고, 재현 분신도 그 높이에서 출발한다.
    w.start_recording('magic_book')
    assert w.recording and w.recording.preview.base == SKY_STEP, '섬 위에서 분신 녹화가 시작되지 않았습니다'
    w.step(Motion())
    w.toggle_recording()
    assert w.echo and w.echo.actor.base == SKY_STEP, ('재현 분신이 섬 높이에서 출발하지 않았습니다', w.echo)
    w.echo = None
    # 포털은 순서 없이 들어가고, 열쇠를 얻은 포털은 다시 들어가지 않는다. 방에서는 몬스터를 다 잡기 전엔 못 나간다.
    w.player.x, w.player.base = sky.switches[2][0], sky.switches[2][1]
    w.step(Motion())
    assert w.room_request == 13, ('3번 포털이 방으로 보내지 않았습니다', w.room_request)
    room = w.enter_room()
    room.player.x = room.stage.exit.x
    for _ in range(10):
        room.step(Motion())
    assert room.result == 'playing', '몬스터를 남긴 채 방을 나갔습니다'
    room.result = 'cleared'
    assert room.back_from_room() is w and w.sky_keys == {2}, '열쇠를 들고 돌아오지 않았습니다'
    w.sky_on = None
    w.step(Motion())
    assert w.room_request is None, '열쇠를 얻은 포털에 다시 들어갔습니다'

    # 동시 발판: 본체 발판만 밟아서는 열리지 않는다.
    w = World(6)
    sync = w.stage.sync_gate
    w.enemies = []
    w.player.floor, w.player.x = sync.player_sensor.floor, sync.player_sensor.x
    for _ in range(round(1 / STEP)):
        w.step(Motion())
    assert w.sync_pressed[0] and not w.sync_unlocked, '본체 혼자 동시 발판문을 열었습니다'

    # 도발 발판: 분신이 서 있으면 수호자는 가까운 본체 대신 분신을 노린다.
    w = World(8)
    plate = w.taunt_plate()
    guard = next(e for e in w.enemies if e.spawn.point == w.stage.guard)
    w.enemies = [guard]
    w.player.floor, w.player.x = plate.floor, w.stage.guard.x + 40
    w.echo = Echo(Actor(plate.x, plate.floor), tuple([Motion()] * 120))
    for _ in range(10):
        w.step(Motion())
    assert guard.target is w.echo.actor, '도발 발판의 분신을 노리지 않습니다'


def check_web_bridge():
    """1스테이지 3층 거미줄 다리: 거미줄이 없으면 떨어지고, 거미줄은 3초 뒤 끊어져 그 위에 선 본체도 떨어진다."""
    def edge():
        w = World(0)
        w.enemies = []
        w.player.floor, w.player.x = 2, 540
        return w

    w = edge()
    for _ in range(round(3 / STEP)):
        w.step(Motion(1))
    assert w.result == 'defeated', ('거미줄 없이 낭떠러지를 걸었습니다', w.player)
    w = edge()
    w.bridge_tiles[0][:3] = [3.0] * 3   # 560~680에 거미줄
    for _ in range(round(0.5 / STEP)):
        w.step(Motion(int(w.player.x < 620)))
    assert w.result == 'playing' and w.player.base == 0 and w.player.x > 600, ('거미줄 위에 서지 못했습니다', w.player)
    for _ in range(round(3 / STEP)):
        w.step(Motion())
    assert w.result == 'defeated', ('끊어진 거미줄 위에 서 있습니다', w.player)


def main():
    check_balance()
    check_web_bridge()
    check_puzzles()
    print('OK   퍼즐 장치')
    check_boss_warp()
    check_floor_warp()
    check_late_stage_monsters()
    print('OK   밸런스 표')
    failed = False
    for index, stage in enumerate(STAGES):
        if index in SKY_ROOMS:
            continue   # 포털 너머 방은 하늘 땅 공략 안에서 레벨을 올려 가며 차례로 깬다
        number = index + 1
        bot = Bot(index)
        try:
            SOLUTIONS[number](bot)
            bot.wait(1.0)   # 보스방은 포털에 빨려 들어가는 데 0.8초 걸린다
            assert bot.w.result == 'cleared', f'출구에 닿지 못했습니다 {bot}'
            assert rush(index) != 'cleared', '분신 없이 달리기만 해도 깨집니다'
            print(f'OK   {stage.title}  ({bot.frames * STEP:.0f}초, 남은 체력 {bot.w.health})')
        except (AssertionError, KeyError) as error:
            failed = True
            print(f'FAIL {stage.title}: {error!r}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
