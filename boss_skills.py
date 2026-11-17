"""보스 스킬 스크립트.

보스는 기본 공격 외에 아래 SKILLS 표의 스킬을 번갈아 쓴다. 스킬은 예고(telegraph) →
발동(active) → 빈틈(rest) 순서로 진행하고, 빈틈 동안 보스는 가만히 서 있어 반격할 수 있다.
화면 이펙트는 pixelfx 시트(assets/attack_fx)이고 World.boss_effects에 쌓아 두면 view가 그린다.
수치를 바꾸려면 SKILLS 표와 각 스킬의 Effect 값을 고치면 된다.
"""
from dataclasses import dataclass

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
        Skill('bolts', '대마녀의 낙뢰! 바닥의 문양에서 벗어나세요.', 0.50, 0.90, 0.35, 0, 900, 9),
        Skill('orb', '대마녀의 마력 구체! 점프로 넘으세요.', 0.50, 0.20, 0.45, 0, 900, 8),
    ),
    'echo_knight': (
        Skill('charge', '잔향 기사의 돌진! 점프로 피하세요.', 0.60, 0.55, 0.60, 140, 560, 11),
        Skill('orb', '잔향 기사의 마력 구체! 점프로 피하세요.', 0.50, 0.20, 0.45, 0, 900, 8),
        Skill('bolts', '잔향 기사의 낙뢰! 표시된 곳을 피하세요.', 0.50, 0.90, 0.35, 0, 900, 9),
    ),
}
CHARGE_SPEED = 520
CHAIN_REACH = 190  # 쇠사슬이 닿는 앞쪽 거리
CHAIN_CRACK = 0.27 # chain-whip 시트에서 사슬 끝이 터지는 시각
ROCK_FALL = 0.9    # 바위가 떨어지는 데 걸리는 시간


def current(enemy) -> Skill | None:
    return next((skill for skill in SKILLS.get(enemy.spawn.kind, ()) if skill.name == enemy.skill), None)


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


def update(world, enemy) -> bool:
    """보스 한 마리의 스킬을 한 스텝 진행한다. 스킬을 쓰는 중이면 True(기본 행동을 건너뛴다)."""
    skills = SKILLS.get(enemy.spawn.kind)
    if not skills:
        return False
    actor, target = enemy.actor, enemy.target
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
            if skills[index].near <= distance <= skills[index].far:
                enemy.skill, enemy.skill_time = skills[index].name, 0.0
                enemy.skill_index = index + 1
                actor.facing = 1 if target.x >= actor.x else -1
                world.notify(skills[index].label)
                if skills[index].name == 'gravity':
                    x = max(LEFT + 100, min(RIGHT - 100, target.x + actor.facing * 90))
                    world.gravity_field = GravityField(x, actor.floor)
                return True
        return False

    before = enemy.skill_time
    enemy.skill_time += STEP
    fired = before < skill.telegraph <= enemy.skill_time
    active = skill.telegraph <= enemy.skill_time < skill.telegraph + skill.active
    aim = target if target is not None else world.player
    effects = world.boss_effects
    if skill.name == 'charge':
        if fired:
            effects.append(Effect('heavy-landing', actor.x, actor.floor, actor.facing))
        if active:
            world._move_x(actor, actor.facing * CHARGE_SPEED * STEP)
            player = world.player
            if player.floor == actor.floor and player.jump_time == 0 and abs(player.x - actor.x) < 36:
                message = '잔향 기사의 돌진에 맞았습니다.' if enemy.spawn.kind == 'echo_knight' else '간수의 돌진에 맞았습니다.'
                if world.hurt(skill.damage, message):
                    effects.append(Effect('crit-hit', player.x, player.floor, actor.facing, scale=0.8))
            for echo in world.echo_actors():
                if echo.floor == actor.floor and echo.jump_time == 0 and abs(echo.x - actor.x) < 36:
                    world.hurt_echo(echo, skill.damage)
    elif skill.name == 'chain' and fired:
        player = world.player
        world.shake = max(world.shake, 0.15)
        if player.floor == actor.floor and 0 < (player.x - actor.x) * actor.facing < CHAIN_REACH:
            world.hurt(skill.damage, '간수의 쇠사슬에 맞았습니다.')
        for echo in world.echo_actors():
            if echo.floor == actor.floor and 0 < (echo.x - actor.x) * actor.facing < CHAIN_REACH:
                world.hurt_echo(echo, skill.damage)
    elif skill.name == 'rockfall' and fired:
        # 바위 세 개가 표적 자리와 양옆에 차례로 떨어진다. 닿는 순간 터지고 화면이 흔들린다.
        for delay, offset in ((0.0, 0), (0.3, 130), (0.6, -130)):
            x = min(RIGHT - 30, max(LEFT + 30, aim.x + offset))
            effects.append(Effect('rock', x, actor.floor, age=-delay, scale=3.0, life=ROCK_FALL, drop=560))
            effects.append(Effect('dirt-explosion', x, actor.floor, age=-delay - ROCK_FALL, scale=0.7,
                                  hit_at=0.0, hit_for=0.10, radius=38, damage=skill.damage, shake=0.35))
    elif skill.name == 'bolts' and fired:
        for delay, ahead in ((0.0, 0), (0.4, 130)):
            effects.append(Effect('lightning-strike', aim.x + aim.facing * ahead, actor.floor, age=-delay,
                                  hit_at=0.86, hit_for=0.10, radius=34, damage=skill.damage))
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


def update_effects(world):
    """이펙트를 한 스텝 진행하고, 맞는 범위 안의 본체에게 피해를 준다."""
    player = world.player
    for effect in world.boss_effects:
        effect.age += STEP
        if effect.age < 0:
            continue
        effect.x += effect.facing * effect.speed * STEP
        if effect.shake and effect.hit_at is not None and effect.hit_at <= effect.age < effect.hit_at + STEP:
            world.shake = max(world.shake, effect.shake)
        if effect.hit_at is None or not effect.hit_at <= effect.age <= effect.hit_at + effect.hit_for:
            continue
        reach = effect.radius + effect.grow * (effect.age - effect.hit_at)
        dodged = effect.jumpable and player.jump_time > 0
        if player.floor == effect.floor and abs(player.x - effect.x) <= reach and not dodged:
            world.hurt(effect.damage, '보스의 스킬에 맞았습니다. 예고를 보고 피하세요.')
        for echo in world.echo_actors():
            if (echo.floor == effect.floor and abs(echo.x - effect.x) <= reach
                    and not (effect.jumpable and echo.jump_time > 0)):
                world.hurt_echo(echo, effect.damage)
    world.boss_effects = [effect for effect in world.boss_effects if effect.age < effect.life]
