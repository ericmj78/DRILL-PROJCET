"""효과음과 배경음악. 소리 파일은 assets/sound (모두 CC0, 출처는 assets/sound/NOTICE.md).

World와 boss_skills가 world.sounds에 소리 이름을 쌓으면 main이 매 프레임 Audio.update로 재생하고 비운다.
배경음악은 보스가 살아 있는 동안 Basilisk Boss Battle Loop, 보스가 없는 스테이지에서는 Dungeon Ambience를 튼다.
스테이지 시작·구역 클리어·패배 같은 짧은 음악은 Audio가 화면이 바뀌는 순간을 보고 직접 튼다.
"""
import random

from pico2d import load_music, load_wav
from pico2d import pico2d as canvas

from asset_paths import ASSET_ROOT
from stages import BOSS_KINDS, STAGE_GROUPS

SOUNDS = {   # 이름: (파일 또는 파일 여러 개, 크기 0~128). 여러 개면 낼 때마다 하나를 골라 같은 소리만 반복되지 않게 한다.
    # 크기는 전체 볼륨 설정(메뉴)에 한 번 더 곱해진다.
    'jump': ('jump.wav', 70), 'double_jump': ('double_jump.wav', 80), 'dash': ('dash_whoosh.ogg', 110),
    'slash': (('slash_1.ogg', 'slash_2.ogg', 'slash_3.ogg', 'slash_4.ogg', 'slash_5.ogg'), 90),
    'thrust': ('thrust_swoosh.ogg', 100), 'hit': ('hit_kick.ogg', 110), 'land': (('land_1.ogg', 'land_2.ogg'), 60),
    'hurt': ('hurt.wav', 90), 'level_up': ('level_up_orchestral.ogg', 100),
    # 몬스터: 공격하려고 움츠릴 때 으르렁, 쓰러질 때 울리는 비명
    'enemy_attack': (('monster_1.ogg', 'monster_2.ogg', 'monster_3.ogg'), 70),
    'monster_die': (('monster_die_1.ogg', 'monster_die_2.ogg'), 80),
    # 보스: 처음 마주칠 때 등장 음악, 쓰러뜨리면 승리 음악
    'boss_appears': ('boss_appears.ogg', 110), 'final_boss': ('final_boss_organ.ogg', 110),
    'boss_defeat': ('victory.ogg', 120), 'trap': ('trap_scary.ogg', 90),
    # 보스 스킬 (boss_skills.SKILL_SOUNDS, Effect.sound)
    'chain': ('chain.ogg', 120), 'rockfall': ('rockfall.ogg', 100), 'rock': ('rock.wav', 90),
    'charge': ('charge.ogg', 120), 'gravity': ('gravity.ogg', 110), 'laser': ('laser.ogg', 100),
    'homing': ('magic_1.ogg', 90), 'teleport': ('magic_2.ogg', 90), 'broom': ('broom.wav', 90),
    'skulls': (('skull_crack_1.ogg', 'skull_crack_2.ogg'), 90), 'wisps': ('wisps.ogg', 80),
    'hands': (('creepy_impact_1.ogg', 'creepy_impact_2.ogg', 'creepy_impact_3.ogg'), 110),
    'pillar': ('pillar.wav', 90), 'phase_start': ('boss_roar.ogg', 120), 'phase': ('phase.wav', 110),
}
JINGLES = {   # Audio가 직접 트는 짧은 음악
    'stage_start': ('stage_start.ogg', 90), 'stage_clear': ('stage_clear_echoes.ogg', 90),
    'game_over': ('game_over.ogg', 110),
}
BOSS_MUSIC = 'boss_basilisk.ogg'
STAGE_MUSIC = 'stage_dungeon.ogg'   # Dungeon Ambience (yd)
MUSIC_SHARE = 0.6   # 배경음악은 효과음보다 작게: 메뉴 볼륨의 60%


def files(entry) -> tuple:
    return entry if isinstance(entry, tuple) else (entry,)


class Audio:
    def __init__(self):
        self.wavs, self.music, self.playing = {}, {}, None
        self.world, self.result = None, None
        try:
            canvas.Mix_AllocateChannels(24)   # 보스 스킬과 타격음이 겹쳐도 끊기지 않게 (기본 8)
            for name, (entry, volume) in {**SOUNDS, **JINGLES}.items():
                self.wavs[name] = [load_wav(str(ASSET_ROOT / 'sound' / file)) for file in files(entry)]
                for wav in self.wavs[name]:
                    wav.set_volume(volume)
            self.music = {name: load_music(str(ASSET_ROOT / 'sound' / file))
                          for name, file in (('boss', BOSS_MUSIC), ('stage', STAGE_MUSIC))}
            canvas.Mix_VolumeMusic(round(128 * MUSIC_SHARE))
        except IOError:   # 스피커가 없거나 소리 장치를 못 열면 소리 없이 한다
            self.wavs, self.music = {}, {}

    def _play(self, name):
        if name in self.wavs:
            random.choice(self.wavs[name]).play()

    def update(self, world, screen):
        """쌓인 효과음과 짧은 음악을 틀고, 상황에 맞는 배경음악으로 바꾼다."""
        for name in dict.fromkeys(world.sounds):   # 한 프레임에 같은 소리가 여러 번 쌓이면 한 번만
            self._play(name)
        world.sounds.clear()
        boss_stage = any(spawn.kind in BOSS_KINDS for spawn in world.stage.enemies)
        if screen == 'play' and world is not self.world:   # 새 구역: 스테이지의 첫 구역이면 시작 음악
            self.world, self.result = world, world.result
            if any(group[0] == world.index for group in STAGE_GROUPS):
                self._play('stage_start')
        if screen == 'play' and world.result != self.result:
            self.result = world.result
            if world.result == 'defeated':
                self._play('game_over')
            elif world.result == 'cleared' and not boss_stage:   # 보스방은 보스를 쓰러뜨릴 때 승리 음악이 나온다
                self._play('stage_clear')
        boss_alive = any(enemy.spawn.kind in BOSS_KINDS for enemy in world.enemies)
        wanted = None
        if screen == 'play' and world.result == 'playing':
            wanted = 'boss' if boss_alive else None if boss_stage else 'stage'
        if self.music and wanted != self.playing:
            self.playing = wanted
            if wanted is None:
                canvas.Mix_HaltMusic()
            else:
                self.music[wanted].repeat_play()
