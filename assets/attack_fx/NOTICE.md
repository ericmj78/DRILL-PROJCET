# 공격 이펙트 시트 출처

이 폴더의 PNG와 JSON은 [pixelfx](https://github.com/patch-gg/pixelfx) 0.3.1(MIT License, Patch)로 뽑은 스프라이트 시트다. pixelfx의 일부 이펙트는 Hugo Duprez의 Sprite Fusion 오픈소스 VFX(MIT License)를 바탕으로 한다.

다시 뽑거나 다른 이펙트를 추가하려면 pixelfx 저장소에서 아래처럼 실행하고, 나온 PNG와 JSON을 이 폴더에 넣은 뒤 `monster_attack.py`의 `ATTACKS` 표에 시트 이름을 적는다.

```
node tools/render.mjs melee/claw-swipe --sheet --no-actor
```
