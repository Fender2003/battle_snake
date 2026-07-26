from __future__ import annotations

from collections import deque


def estimate_space(
    start: tuple[int, int],
    width: int,
    height: int,
    blocked: set[tuple[int, int]],
    limit: int | None = None,
) -> int:
    if start in blocked:
        return 0
    queue = deque([start])
    visited = {start}
    count = 0
    while queue:
        node = queue.popleft()
        count += 1
        if limit is not None and count >= limit:
            return count
        x, y = node
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nxt in visited or nxt in blocked:
                continue
            if not (0 <= nxt[0] < width and 0 <= nxt[1] < height):
                continue
            visited.add(nxt)
            queue.append(nxt)
    return count
