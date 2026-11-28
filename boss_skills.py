"""보스 스킬 스크립트.

보스는 기본 공격 외에 아래 SKILLS 표의 스킬을 번갈아 쓴다. 스킬은 예고(telegraph) →
발동(active) → 빈틈(rest) 순서로 진행하고, 빈틈 동안 보스는 가만히 서 있어 반격할 수 있다.
화면 이펙트는 pixelfx 시트(assets/attack_fx)이고 World.boss_effects에 쌓아 두면 view가 그린다.
수치를 바꾸려면 SKILLS 표와 각 스킬의 Effect 값을 고치면 된다.
"""
from dataclasses import dataclass
from math import hypot, sin

from stages import LEFT, RIGHT, STEP

COOLDOWN = 2.4       # 스킬 하나를 끝낸 뒤 다음 스킬까지 쉬는 시간
FIRST_COOLDOWN = 1.2 # 보스가 표적을 처음 본 뒤 첫 스킬까지


@dataclass(frozen=True)
class Skill:
    name: str
    label: str        # 화면 알림에 쓰는 이름과 피하는 법
    telegraph: float  # 예고 시간
    active: float     # 발동 시간
    rest: float       # 끝난 뒤 빈틈
    near: float       # 표적까지 거리가 near~far일 때만 쓴다
    far: float
    damage: int = 0   # 맞았을 때 본체가 잃는 체력 (BALANCE.md)
    phase: int = 1    # 보스가 이 단계 이상일 때만 쓴다 (잔향 기사)


@dataclass
class Effect:
    sheet: str
    x: float
    floor: int
    facing: int = 1
    age: float = 0.0          # 음수면 그만큼 뒤에 시작한다
    scale: float = 1.0
    lift: float = 0.0         # 바닥 위 높이
    speed: float = 0.0        # 바닥을 따라 나아가는 속도
    life: float = 3.5
    hit_at: float | None = None  # 이 시각부터 hit_for초 동안 radius 안의 본체가 맞는다
    hit_for: float = 0.0
    radius: float = 0.0
    grow: float = 0.0         # 맞는 범위가 초당 넓어지는 속도(충격파)
    jumpable: bool = False    # 점프로 피할 수 있는가
    damage: int = 0
    drop: float = 0.0         # 이 높이에서 떨어지기 시작해 life가 끝날 때 바닥에 닿는다(낙석)
    shake: float = 0.0        # hit_at 순간에 화면을 흔드는 시간
    homing: bool = False      # 본체 몸 가운데를 쫓아 공중으로도 날아간다 (추적 불빛, 해골 불꽃). speed가 0이면 HOMING_SPEED
    vx: float = 0.0
    vh: float = 0.0
    wave: float = 0.0         # 0보다 크면 공중을 곧게 날며 base 높이에서 이만큼 위아래로 일렁인다 (도깨비불)
    base: float = 0.0
    burst: str = 'zap-hit'    # 공중을 나는 이펙트가 본체에 닿아 터질 때 그리는 시트
    burst_scale: float = 0.8
    hit_up: float = 0.0       # 그림의 기준점(아래)에서 맞는 가운데까지의 높이 (해골·도깨비불)
    sound: str = ''           # hit_at 순간에 내는 효과음 (sound.py)


@dataclass
class GravityField:
    x: float
    floor: int
    age: float = 0.0
    warning: float = 0.9
    duration: float = 4.0
    radius: float = 220.0
    captured: bool = False
    escape_direction: int = 0
    escape_time: float = 0.0
    damage_timer: float = 0.0
    escape_immunity: float = 0.0


SKILLS = {
    'jailer_boss': (
        Skill('chain', '간수의 쇠사슬! 뒤로 물러나 사슬 밖으로 나가세요.', 0.50, 0.15, 0.60, 40, 170, 10),
        Skill('rockfall', '낙석! 바닥의 그림자에서 벗어나세요.', 0.60, 1.50, 0.50, 0, 600, 9),
        Skill('charge', '간수의 돌진! 점프로 뛰어넘으세요.', 0.60, 0.55, 0.60, 140, 560, 11),
    ),
    'grand_witch': (
        Skill('gravity', '중력 생성! 반대 방향키로 저항하세요.', 0.90, 0.10, 0.40, 0, 900),
        Skill('laser', '마력 광선! 다른 높이로 피하세요 (2단 점프·섬).', 0.90, 0.70, 0.50, 0, 2200, 9),
        Skill('homing', '추적하는 불빛! 계속 움직이고, 닿기 직전 대시로 뚫으세요.', 0.60, 0.10, 0.60, 0, 2200, 5),
    ),
    # 빗자루를 탄 뒤(world.py의 broom): 본체 너머로 순간이동하며 광선과 불빛을 쏜다. 높이와 쫓아가기는 world.py가 맡는다.
    'grand_witch_broom': (
        Skill('teleport', '대마녀가 사라졌습니다!', 0.60, 0.45, 0.25, 0, 9999),
        Skill('laser', '마력 광선! 다른 높이로 피하세요 (2단 점프·섬).', 0.80, 0.70, 1.20, 0, 9999, 9),
        Skill('teleport', '대마녀가 사라졌습니다!', 0.60, 0.45, 0.25, 0, 9999),
        Skill('homing', '추적하는 불빛! 계속 움직이고, 닿기 직전 대시로 뚫으세요.', 0.50, 0.10, 1.20, 0, 9999, 5),
    ),
    # 잔향 기사: 보랏빛 영혼 불꽃(pixelfx Flying skull·Wisp를 보스방 색으로 바꿈)과 그림자 손(Grasping hands).
    # 3단계로 싸운다 (PHASES): 2단계에 빛의 기둥(Holy pillar)과 도깨비불이 더해지고, 3단계(부활)에는
    # 해골·도깨비불 줄·손·기둥이 늘어난다.
    'echo_knight': (
        Skill('charge', '잔향 기사의 돌진! 점프로 피하세요.', 0.60, 0.55, 0.60, 140, 560, 11),
        Skill('skulls', '해골 불꽃! 계속 움직이고, 닿기 직전 대시로 뚫으세요.', 0.70, 0.10, 0.80, 0, 2200, 9),
        Skill('pillar', '빛의 기둥! 바닥에 새겨지는 문양에서 벗어나세요.', 0.40, 0.10, 1.00, 0, 2200, 10, phase=2),
        Skill('wisps', '도깨비불 행렬! 비어 있는 높이로 피하거나 대시로 뚫으세요.', 0.80, 1.30, 0.60, 0, 2200, 8, phase=2),
        Skill('hands', '그림자 손아귀! 발밑의 어둠에서 벗어나세요.', 0.80, 0.10, 0.70, 0, 2200, 7),
    ),
}
CHARGE_SPEED = 520
CHAIN_REACH = 190  # 쇠사슬이 닿는 앞쪽 거리
ROCK_FALL = 0.9    # 바위가 떨어지는 데 걸리는 시간
CONFUSED_SECONDS = 1.2   # 낙석에 맞으면 이만큼 기절해 움직이지도 공격하지도 못한다
TELEPORT_PAST = 320      # 빗자루 대마녀는 본체 너머 이만큼 떨어진 자리로 순간이동한다
BODY = 45                # 본체 몸 가운데 높이 (발밑에서)
LASER_HALF = 32          # 광선 두께의 반. 몸 가운데가 이 안에 들면 맞는다
HOMING_SPEED = 170       # 추적 불빛의 속도 (본체 걸음 230보다 느리다)
HOMING_TURN = 2.2        # 불빛이 방향을 트는 빠르기 (초당)
SKULL_SPEED = 150        # 해골 불꽃은 추적 불빛보다 느리지만 오래 쫓는다
WISP_SPEED = 280
WISP_ROWS = (25, 105, 185)   # 도깨비불 줄이 지나가는 높이. 한 줄씩 비운다
HANDS_STUN = 1.0         # 그림자 손에 붙잡히면 이만큼 움직이지 못한다
# 잔향 기사의 단계: 체력이 2/3, 1/3 아래로 내려가면 단계가 오르고, 그동안(초) 무적으로 연출만 한다.
# 2단계는 기사 위로 빛의 기둥이 내리꽂히고, 3단계는 빛 속에서 날개를 펴며 되살아난다(Resurrection).
PHASES = {2: ('holy-pillar', 2.0, '잔향 기사가 빛의 기둥을 불러냅니다! (2단계)'),
          3: ('resurrection', 2.6, '잔향 기사가 날개를 펴고 되살아납니다! (3단계)')}


# 스킬을 쓰기 시작할 때(예고 동안) 보스 발밑에 생기는 시전 이펙트: (시트, 배율, 시트 시작 위치(초), 길이(초)).
# 대마녀의 마법진은 1.55초에 빛기둥이 솟으므로 예고가 끝나는 순간 솟게 앞당겨 시작한다(-1 = 예고 길이만큼 당김).
CAST = {'jailer_boss': ('heavy-landing', 1.5, 0.0, 1.6), 'grand_witch': ('magic-circle', 1.4, -1, 2.4),
        'echo_knight': ('rune-circle', 1.8, 0.0, 0.0)}
CAST_BURST = 1.55   # magic-circle 시트에서 빛기둥이 솟는 시각
# 스킬이 발동하는 순간 화면이 잠깐 그 보스의 색으로 번쩍인다
FLASH_SECONDS = 0.25
FLASH = {'jailer_boss': (255, 150, 60), 'grand_witch': (200, 120, 255), 'echo_knight': (130, 70, 220)}


def _flash(world, color):
    world.flash_color, world.flash_time = color, FLASH_SECONDS


# 스킬이 발동하는 순간(예고가 끝날 때) 내는 효과음 (sound.py). 바위·손·기둥은 땅에 닿는 순간 Effect.sound로 낸다.
SKILL_SOUNDS = {'chain': 'chain', 'rockfall': 'rockfall', 'charge': 'charge', 'gravity': 'gravity', 'laser': 'laser',
                'homing': 'homing', 'teleport': 'teleport', 'skulls': 'skulls', 'wisps': 'wisps'}


def current(enemy) -> Skill | None:
    return next((skill for skill in _skills(enemy) if skill.name == enemy.skill), None)


def phase(enemy):
    """화면이 보스 자세를 정할 때 쓴다. ('telegraph' | 'active' | 'rest', 그 단계의 진행도 0~1) 또는 None."""
    skill = current(enemy)
    if skill is None:
        return None
    time = enemy.skill_time
    if time < skill.telegraph:
        return 'telegraph', time / skill.telegraph
    if time < skill.telegraph + skill.active:
        return 'active', (time - skill.telegraph) / skill.active
    return 'rest', (time - skill.telegraph - skill.active) / skill.rest


def _flying(enemy) -> bool:
    return getattr(enemy, 'broom', None) is not None


def _skills(enemy):
    return SKILLS['grand_witch_broom'] if _flying(enemy) else SKILLS.get(enemy.spawn.kind, ())


def update_phase(world, enemy) -> bool:
    """잔향 기사의 단계를 체력에 맞춰 올린다. 단계가 오르는 연출 중이면 True(아무것도 하지 않고 맞지도 않는다)."""
    if enemy.spawn.kind == 'echo_knight' and enemy.health is not None:
        level = 1 + (enemy.health <= enemy.max_health * 2 / 3) + (enemy.health <= enemy.max_health / 3)
        if level > enemy.phase:
            sheet, seconds, label = PHASES[level]
            enemy.phase, enemy.phase_time = level, seconds
            enemy.skill, enemy.windup, enemy.recovery = '', 0, 0
            world.boss_effects = [effect for effect in world.boss_effects if not effect.damage]   # 남은 마법은 흩어진다
            world.sounds.append('phase_start')
            world.shake = max(world.shake, 0.3)
            actor = enemy.actor
            if level == 2:   # 해가 열리고 0.7초 뒤 빛줄기가 기사 발밑에 모이며 땅이 울린다
                world.boss_effects.append(Effect(sheet, actor.x, actor.floor, scale=1.6, life=3.5, hit_at=0.7, shake=0.5,
                                                 sound='phase'))
            else:            # 인형 기준 이펙트라 3배로 키우고 날개가 기사 어깨에 오게 띄운다. 2.3초에 날갯짓
                world.boss_effects.append(Effect(sheet, actor.x, actor.floor, scale=3.0, lift=100, life=4.8,
                                                 hit_at=2.3, shake=0.6, sound='phase'))
    if enemy.phase_time > 0:
        enemy.phase_time -= STEP
        return True
    return False


def update(world, enemy) -> bool:
    """보스 한 마리의 스킬을 한 스텝 진행한다. 스킬을 쓰는 중이면 True(기본 행동을 건너뛴다)."""
    skills = _skills(enemy)
    if not skills:
        return False
    actor, target = enemy.actor, enemy.target
    if _flying(enemy) and target is None:
        target = world.player   # 하늘의 대마녀는 높이가 달라 본체를 놓쳐도 스킬은 쓴다
    skill = current(enemy)
    if skill is None:
        if target is None:
            enemy.skill_cooldown = max(enemy.skill_cooldown, FIRST_COOLDOWN)
            return False
        enemy.skill_cooldown = max(0, enemy.skill_cooldown - STEP)
        if enemy.skill_cooldown > 0 or enemy.windup > 0 or enemy.recovery > 0:
            return False
        distance = abs(target.x - actor.x)
        for offset in range(len(skills)):
            index = (enemy.skill_index + offset) % len(skills)
            if skills[index].phase <= enemy.phase and skills[index].near <= distance <= skills[index].far:
                enemy.skill, enemy.skill_time = skills[index].name, 0.0
                enemy.skill_index = index + 1
                actor.facing = 1 if target.x >= actor.x else -1
                cast = CAST.get(enemy.spawn.kind)
                if cast and skills[index].name != 'teleport':
                    sheet, scale, start, life = cast
                    start = CAST_BURST - skills[index].telegraph if start < 0 else start
                    world.boss_effects.append(Effect(sheet, actor.x, actor.floor, age=start, scale=scale, lift=actor.base,
                                                     life=start + (life or skills[index].telegraph + 0.25)))
                if skills[index].name == 'gravity':
                    x = max(LEFT + 100, min(RIGHT - 100, target.x + actor.facing * 90))
                    world.gravity_field = GravityField(x, actor.floor)
                elif skills[index].name == 'laser':
                    # 광선은 지금 본체 몸 높이를 가로지른다. 예고 동안 다른 높이로 옮겨야 한다.
                    enemy.laser_h = max(20.0, min(560.0, target.jump_height + BODY))   # 맨 윗섬(360) + 2단 점프까지
                elif skills[index].name == 'hands':
                    enemy.mark_x = max(LEFT + 60, min(RIGHT - 60, target.x))   # 예고하는 동안 발밑에 어둠이 번진다
                elif skills[index].name == 'teleport':
                    side = 1 if target.x >= actor.x else -1   # 본체를 넘어 반대편으로
                    enemy.teleport_to = max(LEFT + 120, min(RIGHT - 120, target.x + side * TELEPORT_PAST))
                return True
        return False

    before = enemy.skill_time
    enemy.skill_time += STEP
    fired = before < skill.telegraph <= enemy.skill_time
    active = skill.telegraph <= enemy.skill_time < skill.telegraph + skill.active
    aim = target if target is not None else world.player
    effects = world.boss_effects
    if fired and skill.name in SKILL_SOUNDS:
        world.sounds.append(SKILL_SOUNDS[skill.name])
    if fired and skill.name != 'teleport':
        _flash(world, (255, 220, 130) if skill.name == 'pillar' else FLASH.get(enemy.spawn.kind, (255, 255, 255)))
    if skill.name == 'charge':
        if fired:
            effects.append(Effect('heavy-landing', actor.x, actor.floor, actor.facing, scale=1.6))
            world.shake = max(world.shake, 0.25)
        if active:
            if int(enemy.skill_time / 0.08) != int(before / 0.08):   # 달려가며 뒤로 먼지를 남긴다
                effects.append(Effect('heavy-landing', actor.x - actor.facing * 40, actor.floor, -actor.facing,
                                      scale=0.8, life=1.0))
            world._move_x(actor, actor.facing * CHARGE_SPEED * STEP)
            player = world.player
            if player.floor == actor.floor and player.jump_height < 30 and abs(player.x - actor.x) < 36:
                message = '잔향 기사의 돌진에 맞았습니다.' if enemy.spawn.kind == 'echo_knight' else '간수의 돌진에 맞았습니다.'
                if world.hurt(skill.damage, message):
                    effects.append(Effect('crit-hit', player.x, player.floor, actor.facing, scale=1.3))
                    world.shake = max(world.shake, 0.3)
            for echo in world.echo_actors():
                if echo.floor == actor.floor and echo.jump_height < 30 and abs(echo.x - actor.x) < 36:
                    world.hurt_echo(echo, skill.damage)
    elif skill.name == 'chain' and fired:
        player = world.player
        world.shake = max(world.shake, 0.25)
        # 사슬이 내려친 바닥이 갈라지며 녹슨 쇠 가시가 솟는다. pixelfx ice/ice-spikes를 녹·불씨 색, reach 112·높이 64로
        # 뽑아 1.7배로 그리면 길이가 CHAIN_REACH(190)와 같고 가시는 더 높다.
        effects.append(Effect('ground-slam', actor.x + actor.facing * 60, actor.floor, actor.facing, scale=0.9, life=1.6))
        effects.append(Effect('chain-spikes', actor.x + actor.facing * 10, actor.floor, actor.facing, scale=1.7))
        if player.floor == actor.floor and 0 < (player.x - actor.x) * actor.facing < CHAIN_REACH:
            world.hurt(skill.damage, '간수의 쇠사슬에 맞았습니다.')
        for echo in world.echo_actors():
            if echo.floor == actor.floor and 0 < (echo.x - actor.x) * actor.facing < CHAIN_REACH:
                world.hurt_echo(echo, skill.damage)
    elif skill.name == 'rockfall' and fired:
        # 바위 세 개가 표적 자리와 양옆에 차례로 떨어진다. 닿는 순간 터지고 화면이 흔들린다.
        effects.append(Effect('ground-slam', actor.x, actor.floor, actor.facing, scale=1.0, life=1.6))   # 바닥을 내리쳐 부른다
        for delay, offset in ((0.0, 0), (0.3, 130), (0.6, -130)):
            x = min(RIGHT - 30, max(LEFT + 30, aim.x + offset))
            effects.append(Effect('rock', x, actor.floor, age=-delay, scale=4.0, life=ROCK_FALL, drop=560))
            effects.append(Effect('dirt-explosion', x, actor.floor, age=-delay - ROCK_FALL, scale=1.1,
                                  hit_at=0.0, hit_for=0.10, radius=50, damage=skill.damage, shake=0.35,
                                  sound='rock'))
    elif skill.name == 'bolts' and fired:
        for delay, ahead in ((0.0, 0), (0.4, 130)):
            effects.append(Effect('lightning-strike', aim.x + aim.facing * ahead, actor.floor, age=-delay,
                                  hit_at=0.86, hit_for=0.10, radius=34, damage=skill.damage))
    elif skill.name == 'laser' and active:
        world.shake = max(world.shake, 0.06)   # 광선이 뻗는 동안 땅이 계속 웅웅 울린다
        if fired:
            world.shake = max(world.shake, 0.3)
            effects.append(Effect('mana-burst', actor.x + actor.facing * 60, actor.floor, lift=enemy.laser_h - 30,
                                  scale=1.6, life=1.0))
        for body in (world.player, *world.echo_actors()):
            if (body.floor == actor.floor and (body.x - actor.x) * actor.facing > 0
                    and abs(body.jump_height + BODY - enemy.laser_h) <= LASER_HALF):
                if body is world.player:
                    world.hurt(skill.damage, '대마녀의 마력 광선에 맞았습니다.')
                else:
                    world.hurt_echo(body, skill.damage)
    elif skill.name == 'homing' and fired:
        world.shake = max(world.shake, 0.12)
        effects.append(Effect('mana-burst', actor.x + actor.facing * 70, actor.floor, lift=actor.base + 100, scale=1.3,
                              life=1.0))
        # 지팡이 끝에서 불빛 셋이 위·앞·아래로 퍼져 나갔다가 본체를 쫓아온다.
        for vh in (220, 60, -100):
            effects.append(Effect('arcane-orb', actor.x + actor.facing * 70, actor.floor, scale=0.7,
                                  lift=actor.base + 130, life=5.0, radius=26, damage=skill.damage,
                                  homing=True, vx=actor.facing * 160, vh=vh, burst_scale=1.2))
    elif skill.name == 'skulls' and fired:
        world.shake = max(world.shake, 0.15)
        effects.append(Effect('dark-explosion', actor.x, actor.floor, lift=actor.base + 150, scale=1.1, life=1.4))
        # 어깨 위로 해골 불꽃이 떠올랐다가 본체를 쫓는다. 닿으면 어둠이 터진다.
        angry = enemy.phase >= 3
        for i, vx in enumerate((-90, 90, 0)[:3 if angry else 2]):
            effects.append(Effect('flying-skull', actor.x + vx * 0.4, actor.floor, lift=actor.base + 170 + i * 25,
                                  scale=2.6, hit_up=39, life=6.0, radius=36, damage=skill.damage, homing=True, speed=SKULL_SPEED,
                                  vx=vx, vh=160, burst='dark-explosion', burst_scale=0.6))
    elif skill.name == 'wisps' and active:
        # 도깨비불이 세 높이 중 두 줄로 방을 가로지른다. 0.6초마다 비는 줄이 바뀐다.
        angry = enemy.phase >= 3
        waves = (0.0, 0.6, 1.2) if angry else (0.0, 0.6)
        for wave, at in enumerate(waves):
            if before < skill.telegraph + at <= enemy.skill_time:
                world.shake = max(world.shake, 0.1)
                effects.append(Effect('dark-explosion', actor.x + actor.facing * 70, actor.floor, lift=60, scale=0.7,
                                      life=1.2))
                gap = (enemy.skill_index + wave) % 2   # 바닥 줄이나 가운데 줄을 비운다 (위 줄은 늘 막힌다)
                for row, height in enumerate(WISP_ROWS):
                    if row == gap:
                        continue
                    effects.append(Effect('wisp', actor.x + actor.facing * 70, actor.floor, actor.facing,
                                          scale=2.4, hit_up=29, life=5.0, radius=26, damage=skill.damage, speed=WISP_SPEED,
                                          wave=12, base=height, lift=height, burst='dark-explosion', burst_scale=0.45))
    elif skill.name == 'hands' and fired:
        angry = enemy.phase >= 3
        for delay, offset in ((0.0, 0), (0.35, -170), (0.35, 170))[:3 if angry else 1]:
            effects.append(Effect('grasping-hands', enemy.mark_x + offset, actor.floor, age=-delay, scale=2.2,
                                  life=3.1, hit_at=0.30, hit_for=0.45, radius=105, jumpable=True, damage=skill.damage,
                                  shake=0.3, sound='hands'))
    elif skill.name == 'pillar' and fired:
        # 빛의 기둥: 하늘에 해가 열리고 0.7초 뒤 빛줄기가 표적 자리 문양에 모인다. 모여 있는 동안 문양 위면 맞는다.
        side = 1 if aim.x >= actor.x else -1   # 3단계의 둘째 기둥은 본체 뒤(기사 반대쪽)에 내린다
        for delay, offset in ((0.0, 0), (0.5, side * 170))[:2 if enemy.phase >= 3 else 1]:
            x = max(LEFT + 40, min(RIGHT - 40, aim.x + offset))
            effects.append(Effect('holy-pillar', x, actor.floor, age=-delay, scale=1.8, life=3.5, hit_at=0.7,
                                  hit_for=1.1, radius=46, damage=skill.damage, shake=0.3,
                                  sound='pillar'))
    elif skill.name == 'teleport':
        if before == 0:
            effects.append(Effect('blink-out', actor.x, actor.floor, lift=actor.base + 40, scale=4.0, life=1.6))
        if fired:
            world.shake = max(world.shake, 0.15)
            actor.x = enemy.teleport_to
            actor.facing = 1 if world.player.x >= actor.x else -1
            effects.append(Effect('blink-in', actor.x, actor.floor, lift=actor.base + 40, scale=4.0, life=1.4))
    elif skill.name == 'orb' and fired:
        effects.append(Effect('arcane-orb', actor.x + actor.facing * 40, actor.floor, actor.facing, scale=0.9,
                              speed=250, life=2.6, hit_at=0.0, hit_for=2.6, radius=22, jumpable=True,
                              damage=skill.damage))
    if enemy.skill_time >= skill.telegraph + skill.active + skill.rest:
        enemy.skill, enemy.skill_cooldown = '', COOLDOWN
    return True


def update_gravity(world, horizontal):
    field = world.gravity_field
    if field is None:
        return
    field.age += STEP
    field.escape_immunity = max(0.0, field.escape_immunity - STEP)
    if field.age >= field.warning + field.duration:
        world.gravity_field = None
        return
    player = world.player
    if field.age >= field.warning:
        for echo in world.echo_actors():
            if echo.floor == field.floor and abs(echo.x - field.x) <= 18:
                world.hurt_echo(echo, 3)
    if field.age < field.warning or player.floor != field.floor:
        field.captured = False
        return
    if field.captured:
        player.x = field.x
        player.moving = False
        field.damage_timer -= STEP
        if field.damage_timer <= 0:
            world.hurt(3, '중력 구체에 갇혔습니다! 반대 방향키로 탈출하세요.')
            field.damage_timer = 1.0
        if horizontal == field.escape_direction:
            field.escape_time += STEP
        else:
            field.escape_time = max(0.0, field.escape_time - STEP * 0.5)
        if field.escape_time >= 1.0:
            field.captured = False
            field.escape_immunity = 0.8
            world._move_x(player, field.escape_direction * 45)
        return
    distance = field.x - player.x
    if abs(distance) > field.radius or field.escape_immunity > 0:
        return
    if abs(distance) <= 18:
        field.captured = True
        field.escape_direction = -1 if distance >= 0 else 1
        field.escape_time = 0.0
        field.damage_timer = 0.0
        return
    world._move_x(player, (1 if distance > 0 else -1) * 180 * STEP)


def _fly(world, effect):
    """공중을 나는 이펙트. homing이면 본체 몸 가운데 쪽으로 천천히 방향을 틀고(추적 불빛·해골 불꽃),
    wave면 곧게 날며 위아래로 일렁인다(도깨비불). 몸에 닿으면 터진다 (대시 중엔 뚫고 지나간다)."""
    player = world.player
    dx, dh = player.x - effect.x, player.jump_height + BODY - effect.lift - effect.hit_up
    distance = hypot(dx, dh) or 1.0
    if effect.homing:
        speed = effect.speed or HOMING_SPEED
        turn = min(1.0, HOMING_TURN * STEP)
        effect.vx += (dx / distance * speed - effect.vx) * turn
        effect.vh += (dh / distance * speed - effect.vh) * turn
        effect.x += effect.vx * STEP
        effect.lift += effect.vh * STEP
    else:
        effect.x += effect.facing * effect.speed * STEP
        effect.lift = effect.base + effect.wave * sin(effect.age * 5)
        if not LEFT - 40 <= effect.x <= RIGHT + 40:
            effect.age = effect.life
    if player.floor == effect.floor and distance <= effect.radius + 14:
        if world.hurt(effect.damage, '보스의 마법에 맞았습니다.'):
            world.shake = max(world.shake, 0.2)
            effect.age = effect.life
            world.boss_effects.append(Effect(effect.burst, player.x, player.floor, lift=player.jump_height + 30,
                                             scale=effect.burst_scale, life=1.2))


def update_effects(world):
    """이펙트를 한 스텝 진행하고, 맞는 범위 안의 본체에게 피해를 준다."""
    player = world.player
    for effect in world.boss_effects:
        effect.age += STEP
        if effect.age < 0:
            continue
        if effect.homing or effect.wave:
            _fly(world, effect)
            continue
        effect.x += effect.facing * effect.speed * STEP
        if effect.hit_at is not None and effect.hit_at <= effect.age < effect.hit_at + STEP:
            world.shake = max(world.shake, effect.shake)
            if effect.sound:
                world.sounds.append(effect.sound)
        if (effect.hit_at is None or not effect.damage
                or not effect.hit_at <= effect.age <= effect.hit_at + effect.hit_for):
            continue
        reach = effect.radius + effect.grow * (effect.age - effect.hit_at)
        dodged = effect.jumpable and player.jump_height > 30
        if player.floor == effect.floor and abs(player.x - effect.x) <= reach and not dodged:
            hit = world.hurt(effect.damage, '보스의 스킬에 맞았습니다. 예고를 보고 피하세요.')
            if hit:
                world.shake = max(world.shake, 0.2)
            if hit and effect.sheet == 'dirt-explosion':
                world.confused = CONFUSED_SECONDS   # 떨어진 바위에 머리를 맞아 잠시 기절한다
            elif hit and effect.sheet == 'grasping-hands':
                world.confused = HANDS_STUN          # 그림자 손에 붙잡혀 잠시 움직이지 못한다
        for echo in world.echo_actors():
            if (echo.floor == effect.floor and abs(echo.x - effect.x) <= reach
                    and not (effect.jumpable and echo.jump_height > 30)):
                world.hurt_echo(echo, effect.damage)
    world.boss_effects = [effect for effect in world.boss_effects if effect.age < effect.life]
