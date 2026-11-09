# Echo Escape

[PRD](PRD.md)와 [사전 기획서](PRE_PRD.md)를 바탕으로 개발하는 분신 퍼즐 게임이다. Python 3.13과 pico2d 1.5.1 환경에서 실행한다.

```powershell
python -m pip install -r requirements.txt
python main.py
```

`Enter`로 시작한다. `←`/`→`로 움직이고 `A` 또는 `S`로 기본 공격을 한다. `C`로 분신을 직접 조작해 이동과 대기를 녹화하고, 다시 `C`를 누르면 본체 조작과 분신 재현이 시작된다. `Backspace`로 녹화를 취소하고 `R`로 맵을 초기화한다. `Esc`로 종료한다.

## 1주차 · 기본 조작과 분신 재현

- 방향키 이동, 벽 충돌, 기본 공격 입력과 애니메이션
- 녹화 중 본체와 세계 시간 정지
- 녹화 시작점에서 분신이 이동과 대기를 한 번 재현
