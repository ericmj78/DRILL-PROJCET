"""스테이지 공략 검증. `python test_stages.py`로 실행한다.

화면 없이 World만 돌린다. 스테이지마다 (1) 아래 공략대로 하면 깨지고
(2) 분신 없이 달리며 베기만 해서는 못 깨는지를 확인한다.
SOLUTIONS는 막혔을 때 읽는 공략집이기도 하다.
"""
import sys

from stages import STAGES, STEP
from world import Motion, World


class Bot:
    def __init__(self, index):
        self.w = World(index)
        self.frames = 0

    @property
    def me(self):  # 지금 조작 중인 대상
        return self.w.recording.preview if self.w.recording else self.w.player

    def tick(self, horizontal=0, stairs=0, jump=False, attack=False):
        self.w.step(Motion(horizontal, stairs, jump), attack)
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
        while self.me.jump_time > 0:
            self.tick(direction)

    def rec(self):  # C 키
        self.w.toggle_recording()

    def lever(self):  # E 키
        self.w.toggle_lever()

    def kill(self, kind):
        """찌르기 거리에서 싸운다. 적이 공격을 준비하면 뒤로 빠졌다가 다시 찌른다."""
        for _ in range(round(40 / STEP)):
            targets = [e for e in self.w.enemies if e.spawn.kind == kind and e.actor.floor == self.me.floor]
            if not targets or self.w.result != 'playing':
                return
            foe = min(targets, key=lambda e: abs(e.actor.x - self.me.x))
            gap = foe.actor.x - self.me.x
            toward = 1 if gap >= 0 else -1
            if foe.windup > 0 and abs(gap) < 90:
                self.tick(-toward)
            elif abs(gap) > 118 or self.me.facing != toward:
                self.tick(toward)
            else:
                self.tick(attack='thrust')
        raise AssertionError(f'{kind}을 처치하지 못했습니다 {self}')

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
    # A 발판과 A 문 사이에서 녹화를 시작해야 분신과 본체가 걷는 거리가 둘 다 짧다.
    b.go(500)
    b.rec()
    b.go(267)      # A 발판: 본체가 A 문에 들어설 때까지
    b.wait(0.4)
    b.go(430)      # B 발판: 본체가 B 문까지 달릴 동안
    b.wait(2.6)
    b.rec()
    b.go(2100, slash=True)


@solution(2)
def stage_2(b):
    b.go(659)
    b.until(lambda w: enemy(w, 'beast').x < 850)   # 짐승이 사다리 쪽에 있을 때 미끼를 보낸다
    b.rec()
    b.down()
    b.go(380)
    b.wait(3.0)
    b.rec()
    b.until(lambda w: enemy(w, 'beast').x < 620)   # 짐승이 사다리 밑을 지나간 뒤
    b.down()
    b.go(1200)
    b.up()
    b.rec()                                        # 짐승이 돌아오기 전에 감시 구역으로
    b.down()
    b.go(1300)
    b.wait(3.5)
    b.rec()
    b.go(2100, slash=True)


@solution(3)
def stage_3(b):
    b.kill('crawler')
    b.go(151)
    b.rec()
    b.go(324)
    b.wait(2.1)
    b.rec()
    b.up()
    b.go(600)                                      # 본체가 C 발판을 밟은 채로 녹화한다
    b.rec()
    b.go(1000)
    b.wait(1.9)
    b.rec()
    b.until(lambda w: w.echo.actor.x > 840)        # 분신이 C 문을 지나면 출발
    b.go(700)
    b.up()
    b.go(960)
    b.kill('watcher')
    b.go(1800)
    b.up()
    b.kill('watcher')
    b.kill('crawler')
    b.go(400)
    b.up()
    b.kill('jailer_boss')
    b.go(2100)


@solution(4)
def stage_4(b):
    b.kill('magic_book')
    b.go(500)
    b.rec()
    b.go(160)
    b.wait(0.6)
    b.rec()
    b.go(960)
    b.kill('potion_slime')
    b.kill('magic_armor')
    b.go(1220)
    b.rec()
    b.jump(1)       # 2번 위를 뛰어넘는다
    b.go(1500)      # 1번 통과
    b.go(1262)      # 되돌아와 2번 통과
    b.jump(1)       # 2번과 1번을 연달아 뛰어넘는다
    b.jump(1)
    b.go(1660)      # 3번 통과
    b.rec()
    b.until(lambda w: w.sequence_unlocked, limit=6)
    b.go(1890)
    b.kill('witch')
    b.go(2100)


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
    b.go(104)


@solution(6)
def stage_6(b):
    b.kill('magic_armor')
    b.go(680)
    b.up()
    b.kill('magic_book')
    b.go(680)
    b.rec()
    b.down()
    b.go(1000)
    b.wait(0.8)
    b.rec()
    b.go(1250)
    b.until(lambda w: enemy(w, 'beast').x > 1720)   # 짐승이 오른쪽 끝에 있을 때
    b.rec()
    b.down()
    b.go(1610)
    b.wait(0.3)
    b.rec()
    b.go(1850)
    b.down()
    b.kill('witch')
    b.go(2100)


@solution(7)
def stage_7(b):
    b.kill('magic_book')
    b.go(160)
    b.rec()
    b.go(145)
    b.up()
    b.go(440)
    b.wait(1.6)
    b.rec()
    b.go(860)
    b.kill('magic_armor')
    b.go(1250)
    b.rec()
    b.go(1150)      # C 발판: 본체가 C 문에 들어설 때까지
    b.wait(0.3)
    b.go(1300)      # 균형 발판: 승강 발판이 다 오를 때까지
    b.wait(1.6)
    b.rec()
    b.go(1450)
    b.until(lambda w: w.player.floor == 1, limit=5)
    b.kill('potion_slime')
    b.go(400, slash=True)
    b.up()
    b.kill('magic_book')
    b.kill('potion_slime')
    b.go(1800)
    b.up()
    b.kill('witch')
    b.kill('magic_armor')
    b.go(400)
    b.up()
    b.kill('grand_witch')
    b.go(2100)


@solution(8)
def stage_8(b):
    b.go(400)
    b.rec()
    b.go(245)
    b.wait(0.4)
    b.rec()
    b.go(600)
    b.kill('crawler')
    b.go(1300)
    b.up()
    b.rec()
    b.down()
    b.go(1490)      # B 발판: 본체가 B 문에 들어설 때까지
    b.wait(0.3)
    b.go(790)       # 아래층 감지선을 왼쪽으로 통과
    b.rec()
    b.go(860)
    b.until(lambda w: w.echo.actor.x < 900)        # 아래층 분신과 나란히 감지선을 넘는다
    b.go(520)
    b.kill('watcher')
    b.go(105)


@solution(9)
def stage_9(b):
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
    b.kill('crawler')
    b.go(950)
    b.up()
    b.kill('watcher')
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


@solution(10)
def stage_10(b):
    b.go(350)
    b.rec()
    b.go(252)
    b.wait(0.6)
    b.rec()
    b.go(670)
    b.up()
    b.until(lambda w: enemy(w, 'beast').x > 1050)  # 짐승이 B 발판에서 가장 멀 때
    b.rec()
    b.down()
    b.go(820)
    b.wait(1.5)
    b.rec()
    b.go(1060)
    b.kill('watcher')
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


def main():
    failed = False
    for index, stage in enumerate(STAGES):
        number = index + 1
        bot = Bot(index)
        try:
            SOLUTIONS[number](bot)
            bot.wait(0.2)
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
