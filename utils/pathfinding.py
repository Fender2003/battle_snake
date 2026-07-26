from __future__ import annotations

from heapq import heappop, heappush
from collections import deque


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def neighbors(pos: tuple[int, int], width: int, height: int) -> list[tuple[int, int]]:
    x, y = pos
    candidates = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return [p for p in candidates if 0 <= p[0] < width and 0 <= p[1] < height]


def bfs_path(
    start: tuple[int, int],
    goals: set[tuple[int, int]],
    width: int,
    height: int,
    blocked: set[tuple[int, int]],
) -> list[tuple[int, int]] | None:
    if start in goals:
        return [start]
    queue = deque([start])
    parent: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    while queue:
        node = queue.popleft()
        for nxt in neighbors(node, width, height):
            if nxt in parent or nxt in blocked:
                continue
            parent[nxt] = node
            if nxt in goals:
                path = [nxt]
                while parent[path[-1]] is not None:
                    path.append(parent[path[-1]])  # type: ignore[arg-type]
                path.reverse()
                return path
            queue.append(nxt)
    return None


def a_star_path(
    start: tuple[int, int],
    goal: tuple[int, int],
    width: int,
    height: int,
    blocked: set[tuple[int, int]],
) -> list[tuple[int, int]] | None:
    open_heap: list[tuple[int, tuple[int, int]]] = [(0, start)]
    g_cost: dict[tuple[int, int], int] = {start: 0}
    parent: dict[tuple[int, int], tuple[int, int] | None] = {start: None}

    while open_heap:
        _, node = heappop(open_heap)
        if node == goal:
            path = [node]
            while parent[path[-1]] is not None:
                path.append(parent[path[-1]])  # type: ignore[arg-type]
            path.reverse()
            return path

        for nxt in neighbors(node, width, height):
            if nxt in blocked:
                continue
            tentative = g_cost[node] + 1
            if tentative < g_cost.get(nxt, 10**9):
                g_cost[nxt] = tentative
                parent[nxt] = node
                priority = tentative + manhattan(nxt, goal)
                heappush(open_heap, (priority, nxt))
    return None
