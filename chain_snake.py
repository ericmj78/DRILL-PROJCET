"""사슬 뱀 (4스테이지 사슬 뱀의 탑). 길과 몸 위치, 밟을 수 있는 면을 계산한다.

머리는 stages.Snake.path의 꺾인 길을 따라 나아가고, 몸은 머리가 지나간 칸을 그대로 따라온다(뱀 게임처럼).
그래서 몸 칸은 제자리에 있다가 꼬리가 지나가면 사라진다: 한자리에 서 있으면 발밑이 없어지니 머리 쪽으로 걸어야 한다.
길의 높이는 그 층 바닥 기준이고, 가로로 놓인 몸은 윗면이 길 높이다. 세로로 놓인 몸(올라가거나 내려가는 곳)은
맨 윗칸의 위 끝이 밟는 면이라, 머리가 위로 올라가면 그 위에 선 본체도 함께 올라간다.
길이(head)는 길을 따라 잰 머리 앞끝의 거리다. 몸은 head - 칸 수 × CELL부터 head까지 차지한다.
"""
from math import hypot

CELL, THICK = 66, 28     # 몸 한 칸의 길이와 두께 = PixelLab 도트 그림을 1배로 그린 크기 (tools/stage_art/chain_snake.py)
COLUMN_HALF = THICK / 2 + 12  # 세로 몸 위에 설 수 있는 x 범위의 반폭


def corners(snake):
    """꺾이는 점들. 고리(ㅁ자)는 처음 점으로 돌아와 닫힌다."""
    return snake.path + (snake.path[0],) if snake.loop else snake.path


def pieces(snake):
    """곧은 조각들: (시작 거리, 길이, 시작점, 끝점)."""
    out, start = [], 0.0
    points = corners(snake)
    for a, b in zip(points, points[1:]):
        size = hypot(b[0] - a[0], b[1] - a[1])
        out.append((start, size, a, b))
        start += size
    return out


def length(snake) -> float:
    start, size, _, _ = pieces(snake)[-1]
    return start + size


def start_head(snake) -> float:
    """처음 머리 자리: 꼬리가 길의 시작점에 오게 몸 전체가 길 위에 놓인다."""
    return snake.cells * CELL


def point(snake, s):
    """길을 따라 s만큼 간 자리와 나아가는 방향: (x, 높이, dx, dy). 고리는 한 바퀴를 넘으면 되돌아 돌고,
    고리가 아니면 길 앞뒤로 첫·끝 조각 방향 그대로 늘여 잰다 (꼬리 그림이 시작점 뒤로 나올 때)."""
    parts = pieces(snake)
    if snake.loop:
        s %= length(snake)
    for start, size, a, b in parts:
        if s <= start + size or (start, size, a, b) == parts[-1]:
            break
    if s < 0:
        start, size, a, b = parts[0]
    t = (s - start) / size
    dx, dy = (b[0] - a[0]) / size, (b[1] - a[1]) / size
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, dx, dy


def occupied(snake, head):
    """몸이 차지한 길 구간들 [(a, b)]. 고리는 한 바퀴 끝을 넘으면 둘로 나뉘고, 아니면 길 밖은 잘린다."""
    tail = head - snake.cells * CELL
    if not snake.loop:
        a, b = max(0.0, tail), min(length(snake), head)
        return [(a, b)] if a < b else []
    total = length(snake)
    tail %= total
    head = tail + snake.cells * CELL
    return [(tail, head)] if head <= total else [(tail, total), (0.0, head - total)]


def surfaces(snake, head):
    """밟을 수 있는 면: (조각 번호, 왼쪽 x, 오른쪽 x, 높이). 가로 조각은 몸 윗면, 세로 조각은 맨 윗칸의 위 끝."""
    out = []
    for index, (start, size, a, b) in enumerate(pieces(snake)):
        for low, high in occupied(snake, head):
            lo, hi = max(low, start), min(high, start + size)
            if lo >= hi:
                continue
            ends = [(a[0] + (b[0] - a[0]) * (s - start) / size, a[1] + (b[1] - a[1]) * (s - start) / size) for s in (lo, hi)]
            if a[1] == b[1]:   # 가로: 모서리에서 세로 몸과 이어지게 두께 반만큼 늘린다
                left, right = sorted(x for x, _ in ends)
                out.append((index, left - THICK / 2, right + THICK / 2, a[1]))
            else:
                out.append((index, a[0] - COLUMN_HALF, a[0] + COLUMN_HALF, max(y for _, y in ends)))
    return out


def cells(snake, head):
    """그릴 몸 칸의 가운데와 방향: [(x, 높이, dx, dy)]. 머리 쪽부터. 길 밖으로 나간 칸은 뺀다."""
    total = length(snake)
    out = []
    for i in range(snake.cells):
        s = head - (i + 0.5) * CELL
        if snake.loop or 0 <= s <= total:
            out.append(point(snake, s))
    return out
