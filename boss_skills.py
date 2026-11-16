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
    speed: float = 0.0        # 바닥을 따라 나아가는 속도
    life: float = 3.5
    hit_at: float | None = None  # 이 시각부터 hit_for초 동안 radius 안의 본체가 맞는다
    hit_for: float = 0.0
    radius: float = 0.0
    grow: float = 0.0         # 맞는 범위가 초당 넓어지는 속도(충격파)
    jumpable: bool = False    # 점프로 피할 수 있는가
    damage: int = 0


SKILLS = {
    'jailer_boss': (
        Skill('charge', '간수의 돌진! 점프로 뛰어넘으세요.', 0.60, 0.55, 0.60, 140, 560, 11),
        Skill('quake', '간수의 지면 충격파! 내려찍는 순간 점프하세요.', 0.70, 0.45, 0.65, 0, 300, 9),
    ),
    'grand_witch': (
        Skill('blink', '대마녀가 순간이동합니다.', 0.45, 0.10, 0.30, 0, 140),
        Skill('bolts', '대마녀의 낙뢰! 바닥의 문양에서 벗어나세요.', 0.50, 0.90, 0.35, 140, 900, 9),
        Skill('orb', '대마녀의 마력 구체! 점프로 넘으세요.', 0.50, 0.20, 0.45, 150, 900, 8),
    ),
}
CHARGE_SPEED = 520


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
                if skills[index].name != 'blink':  # 순간이동은 순서를 넘기지 않아 원거리 스킬이 번갈아 나온다.
                    enemy.skill_index = index + 1
                actor.facing = 1 if target.x >= actor.x else -1
                world.notify(skills[index].label)
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
                if world.hurt(skill.damage, '간수의 돌진에 맞았습니다.'):
                    effects.append(Effect('crit-hit', player.x, player.floor, actor.facing, scale=0.8))
    elif skill.name == 'quake' and fired:
        effects.append(Effect('ground-slam', actor.x + actor.facing * 40, actor.floor, actor.facing, scale=1.5,
                              hit_at=0.0, hit_for=skill.active, radius=50, grow=300, jumpable=True,
                              damage=skill.damage))
    elif skill.name == 'blink' and fired:
        effects.append(Effect('blink-out', actor.x, actor.floor, actor.facing, scale=1.6))
        side = 1 if RIGHT - aim.x > aim.x - LEFT else -1
        actor.x = min(RIGHT - 60, max(LEFT + 60, aim.x + side * 190))
        actor.facing = -side
        effects.append(Effect('blink-in', actor.x, actor.floor, actor.facing, scale=1.6))
    elif skill.name == 'bolts' and fired:
        for delay, ahead in ((0.0, 0), (0.4, 130)):
            effects.append(Effect('lightning-strike', aim.x + aim.facing * ahead, actor.floor, age=-delay,
                                  hit_at=0.86, hit_for=0.10, radius=34, damage=skill.damage))
    elif skill.name == 'orb' and fired:
        effects.append(Effect('arcane-orb', actor.x + actor.facing * 40, actor.floor, actor.facing, scale=0.9,
                              speed=250, life=2.6, hit_at=0.0, hit_for=2.6, radius=22, jumpable=True,
                              damage=skill.damage))
    if enemy.skill_time >= skill.telegraph + skill.active + skill.rest:
        # 순간이동 뒤에는 벌린 거리에서 곧바로 원거리 스킬을 잇는다.
        enemy.skill, enemy.skill_cooldown = '', 0.4 if skill.name == 'blink' else COOLDOWN
    return True


def update_effects(world):
    """이펙트를 한 스텝 진행하고, 맞는 범위 안의 본체에게 피해를 준다."""
    player = world.player
    for effect in world.boss_effects:
        effect.age += STEP
        if effect.age < 0:
            continue
        effect.x += effect.facing * effect.speed * STEP
        if effect.hit_at is None or not effect.hit_at <= effect.age <= effect.hit_at + effect.hit_for:
            continue
        reach = effect.radius + effect.grow * (effect.age - effect.hit_at)
        dodged = effect.jumpable and player.jump_time > 0
        if player.floor == effect.floor and abs(player.x - effect.x) <= reach and not dodged:
            world.hurt(effect.damage, '보스의 스킬에 맞았습니다. 예고를 보고 피하세요.')
    world.boss_effects = [effect for effect in world.boss_effects if effect.age < effect.life]
