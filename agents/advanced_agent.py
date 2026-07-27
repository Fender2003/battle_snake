# from __future__ import annotations

# import time
# from itertools import product
# from collections import deque
# from typing import Any, Optional

# from agent import BaseAgent, legal_moves, next_position, parse_point


# class AdvancedAgent(BaseAgent):
#     """
#     Optimized minimax for 11x11, 4 snakes, <500ms.
    
#     Fixes:
#     - H2H checked at every depth (not just distance-1)
#     - Momentum term prevents zigzagging
#     - Fast floodfill with early termination
#     - Smart opponent model (not just greedy space)
#     - Iterative deepening with hard 400ms cutoff
#     """

#     name = "advanced"
#     apiversion = "1"
#     color = "#8b00ff"
#     author = "Skadoosh"

#     TIME_LIMIT = 0.40  # 400ms hard cutoff for 500ms limit

#     # Evaluation weights
#     W_SPACE = 100.0
#     W_OPP_SPACE = -80.0
#     W_H2H_WIN = 600.0
#     W_H2H_LOSE = -1000.0
#     W_MOMENTUM = 15.0  # prevents zigzagging
#     W_HEALTH = 0.5
#     W_LENGTH = 6.0
#     W_FOOD_HUNGRY = 3.0
#     W_FOOD_STARVING = 7.0
#     W_DEAD = -100000.0
#     W_WIN = 100000.0

#     HUNGRY_THRESHOLD = 55
#     STARVING_THRESHOLD = 25

#     def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
#         start = time.time()
#         try:
#             return self._search(game_state, you, start)
#         except Exception:
#             return self._fallback(game_state, you)

#     def _fallback(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
#         try:
#             moves = legal_moves(game_state, you)
#             return moves[0] if moves else "up"
#         except Exception:
#             return "up"

#     def _search(self, game_state: dict[str, Any], you: dict[str, Any],
#                 start: float) -> str:
#         board = game_state["board"]
#         W, H = board["width"], board["height"]
#         foods = [parse_point(f) for f in board.get("food", [])]

#         you_id = you["id"]
#         your_body = [parse_point(p) for p in you["body"]]
#         your_head = your_body[0]
#         your_len = len(your_body)
#         your_hp = int(you.get("health", 100))
#         current_dir = self._get_heading(you)

#         opps: list[dict] = []
#         for s in board.get("snakes", []):
#             if s["id"] == you_id:
#                 continue
#             body = [parse_point(p) for p in s.get("body", [])]
#             if body:
#                 opps.append({
#                     "body": body,
#                     "head": body[0],
#                     "len": len(body),
#                     "hp": int(s.get("health", 100)),
#                 })

#         your_moves = self._safe_moves(your_head, your_body, your_len, opps, W, H)
#         if not your_moves:
#             lm = legal_moves(game_state, you)
#             return lm[0] if lm else "up"
#         if len(your_moves) == 1:
#             return your_moves[0]

#         best_move = your_moves[0]
#         best_score = -1e18

#         # Iterative deepening
#         for depth in (1, 2):
#             if time.time() - start > self.TIME_LIMIT:
#                 break

#             cur_best = your_moves[0]
#             cur_best_score = -1e18

#             for m in your_moves:
#                 if time.time() - start > self.TIME_LIMIT:
#                     break

#                 heads, bodies, lens, hps = self._simulate_all(
#                     your_head, your_body, your_len, your_hp, m, opps, W, H
#                 )
#                 if heads[0] is None:
#                     continue

#                 score = self._min_min(heads, bodies, lens, hps, foods, W, H, 
#                                       depth - 1, start, m, current_dir)
#                 if score > cur_best_score:
#                     cur_best_score = score
#                     cur_best = m

#             best_move = cur_best
#             best_score = cur_best_score

#             if best_score >= self.W_WIN / 2:
#                 break

#         return best_move

#     def _min_min(self, heads, bodies, lens, hps, foods, W, H,
#                  depth: int, start: float, last_move: str, current_dir: Optional[str]) -> float:
#         if time.time() - start > self.TIME_LIMIT or depth <= 0:
#             return self._evaluate(heads, bodies, lens, hps, foods, W, H, last_move, current_dir)

#         opp_move_lists: list[list[str]] = []
#         opp_indices: list[int] = []
#         for i in range(1, len(heads)):
#             if heads[i] is None:
#                 continue
#             others = []
#             for j in range(len(heads)):
#                 if j == i or heads[j] is None:
#                     continue
#                 others.append({
#                     "body": bodies[j],
#                     "head": heads[j],
#                     "len": lens[j],
#                     "hp": hps[j],
#                 })
#             moves = self._safe_moves(heads[i], bodies[i], lens[i], others, W, H)
#             if not moves:
#                 continue
#             opp_move_lists.append(moves)
#             opp_indices.append(i)

#         if not opp_move_lists:
#             return self.W_WIN

#         min_score = 1e18
#         for combo in product(*opp_move_lists):
#             new_heads, new_bodies, new_lens, new_hps = self._simulate_opps(
#                 heads, bodies, lens, hps, opp_indices, combo, W, H
#             )
#             score = self._max_you(new_heads, new_bodies, new_lens, new_hps,
#                                   foods, W, H, depth - 1, start, last_move, current_dir)
#             if score < min_score:
#                 min_score = score
#                 if min_score <= self.W_DEAD:
#                     break

#         return min_score

#     def _max_you(self, heads, bodies, lens, hps, foods, W, H,
#                  depth: int, start: float, last_move: str, current_dir: Optional[str]) -> float:
#         if time.time() - start > self.TIME_LIMIT or depth <= 0:
#             return self._evaluate(heads, bodies, lens, hps, foods, W, H, last_move, current_dir)

#         if heads[0] is None:
#             return self.W_DEAD

#         opps = []
#         for i in range(1, len(heads)):
#             if heads[i] is None:
#                 continue
#             opps.append({
#                 "body": bodies[i],
#                 "head": heads[i],
#                 "len": lens[i],
#                 "hp": hps[i],
#             })

#         moves = self._safe_moves(heads[0], bodies[0], lens[0], opps, W, H)
#         if not moves:
#             return self.W_DEAD

#         max_score = -1e18
#         for m in moves:
#             new_heads, new_bodies, new_lens, new_hps = self._simulate_all(
#                 heads[0], bodies[0], lens[0], hps[0], m, opps, W, H
#             )
#             score = self._min_min(new_heads, new_bodies, new_lens, new_hps,
#                                   foods, W, H, depth - 1, start, m, current_dir)
#             if score > max_score:
#                 max_score = score

#         return max_score

#     def _safe_moves(self, head, body, my_len, opps, W, H) -> list[str]:
#         """Legal moves with full H2H filtering."""
#         blocked: set[tuple[int, int]] = set()

#         for opp in opps:
#             b = opp["body"]
#             if len(b) > 1:
#                 blocked.update(b[:-1])
#             else:
#                 blocked.update(b)

#         if len(body) > 1:
#             blocked.update(body[:-1])
#         else:
#             blocked.update(body)

#         out: list[str] = []
#         for m in ("up", "down", "left", "right"):
#             nx, ny = next_position(head, m)
#             if not (0 <= nx < W and 0 <= ny < H):
#                 continue
#             p = (nx, ny)
#             if p in blocked:
#                 continue

#             # H2H: if opponent is adjacent and I'm <= their length, I die
#             dead = False
#             for opp in opps:
#                 oh = opp["head"]
#                 if abs(oh[0] - p[0]) + abs(oh[1] - p[1]) == 1:
#                     if my_len <= opp["len"]:
#                         dead = True
#                         break
#             if dead:
#                 continue

#             out.append(m)
#         return out

#     def _simulate_all(self, your_head, your_body, your_len, your_hp,
#                       your_move, opps, W, H):
#         """Simulate full turn with smart opponent model."""
#         your_new_head = next_position(your_head, your_move)

#         opp_new_heads = []
#         for opp in opps:
#             others = [{"body": your_body, "head": your_head, "len": your_len, "hp": your_hp}]
#             for other_opp in opps:
#                 if other_opp is not opp:
#                     others.append(other_opp)
            
#             opp_moves = self._safe_moves(opp["head"], opp["body"], opp["len"], others, W, H)
#             if not opp_moves:
#                 opp_new_heads.append(None)
#                 continue
            
#             # Smart opponent: avoid you if you're longer, chase food if hungry
#             best_m = self._pick_opp_move(opp, opp_moves, your_head, your_len, W, H)
#             opp_new_heads.append(next_position(opp["head"], best_m))

#         proposed = [your_new_head] + opp_new_heads
#         all_bodies = [your_body] + [o["body"] for o in opps]
#         all_lens = [your_len] + [o["len"] for o in opps]
#         all_hps = [your_hp] + [o["hp"] for o in opps]

#         alive = [True] * len(proposed)

#         for i, nh in enumerate(proposed):
#             if nh is None:
#                 alive[i] = False
#                 continue
#             if not (0 <= nh[0] < W and 0 <= nh[1] < H):
#                 alive[i] = False
#                 continue
#             for j, b in enumerate(all_bodies):
#                 if j == i:
#                     check_body = b[:-1] if len(b) > 1 else b
#                 else:
#                     check_body = b
#                 if nh in check_body:
#                     alive[i] = False
#                     break

#         for i in range(len(proposed)):
#             if not alive[i] or proposed[i] is None:
#                 continue
#             for j in range(i + 1, len(proposed)):
#                 if not alive[j] or proposed[j] is None:
#                     continue
#                 if proposed[i] == proposed[j]:
#                     if all_lens[i] > all_lens[j]:
#                         alive[j] = False
#                     elif all_lens[j] > all_lens[i]:
#                         alive[i] = False
#                     else:
#                         alive[i] = False
#                         alive[j] = False

#         heads: list[Optional[tuple[int, int]]] = [None] * len(proposed)
#         bodies: list[list] = [[] for _ in range(len(proposed))]
#         lens = [0] * len(proposed)
#         hps = [0] * len(proposed)

#         for i in range(len(proposed)):
#             if alive[i]:
#                 heads[i] = proposed[i]
#                 bodies[i] = [proposed[i]] + all_bodies[i][:-1]
#                 lens[i] = all_lens[i]
#                 hps[i] = max(0, all_hps[i] - 1)
#             else:
#                 heads[i] = None
#                 bodies[i] = []
#                 lens[i] = 0
#                 hps[i] = 0

#         return heads, bodies, lens, hps

#     def _pick_opp_move(self, opp, opp_moves, your_head, your_len, W, H):
#         """Smart opponent model: flee if you're longer, else maximize space."""
#         opp_head = opp["head"]
#         opp_len = opp["len"]
        
#         # If you're longer, opponent should flee
#         if your_len > opp_len:
#             best_m = opp_moves[0]
#             best_dist = -1
#             for om in opp_moves:
#                 nh = next_position(opp_head, om)
#                 dist = abs(nh[0] - your_head[0]) + abs(nh[1] - your_head[1])
#                 if dist > best_dist:
#                     best_dist = dist
#                     best_m = om
#             return best_m
        
#         # Otherwise maximize space
#         best_m = opp_moves[0]
#         best_space = -1
#         for om in opp_moves:
#             nh = next_position(opp_head, om)
#             sp = self._quick_space(nh, opp["body"], W, H)
#             if sp > best_space:
#                 best_space = sp
#                 best_m = om
#         return best_m

#     def _simulate_opps(self, heads, bodies, lens, hps, opp_indices, opp_moves,
#                        W, H):
#         """Apply opponent moves."""
#         new_heads = list(heads)
#         new_bodies = [list(b) for b in bodies]
#         new_lens = list(lens)
#         new_hps = list(hps)

#         proposed = {idx: next_position(heads[idx], m)
#                     for idx, m in zip(opp_indices, opp_moves)}

#         alive = {idx: True for idx in opp_indices}

#         for idx, nh in proposed.items():
#             if not (0 <= nh[0] < W and 0 <= nh[1] < H):
#                 alive[idx] = False
#                 continue
            
#             if heads[0] is not None:
#                 your_body_check = bodies[0][:-1] if len(bodies[0]) > 1 else bodies[0]
#                 if nh in your_body_check:
#                     alive[idx] = False
#                     continue
            
#             for j in opp_indices:
#                 if j == idx or not alive.get(j, False):
#                     continue
#                 opp_body = bodies[j]
#                 if nh in opp_body:
#                     alive[idx] = False
#                     break

#         if heads[0] is not None:
#             for idx in opp_indices:
#                 if not alive[idx]:
#                     continue
#                 if proposed[idx] == heads[0]:
#                     if lens[0] > lens[idx]:
#                         alive[idx] = False
#                     elif lens[idx] > lens[0]:
#                         new_heads[0] = None
#                         new_bodies[0] = []
#                         new_lens[0] = 0
#                         new_hps[0] = 0
#                     else:
#                         alive[idx] = False
#                         new_heads[0] = None
#                         new_bodies[0] = []
#                         new_lens[0] = 0
#                         new_hps[0] = 0

#         for i_idx in opp_indices:
#             if not alive[i_idx]:
#                 continue
#             for j_idx in opp_indices:
#                 if i_idx >= j_idx or not alive[j_idx]:
#                     continue
#                 if proposed[i_idx] == proposed[j_idx]:
#                     if lens[i_idx] > lens[j_idx]:
#                         alive[j_idx] = False
#                     elif lens[j_idx] > lens[i_idx]:
#                         alive[i_idx] = False
#                     else:
#                         alive[i_idx] = False
#                         alive[j_idx] = False

#         for idx in opp_indices:
#             if alive[idx]:
#                 new_heads[idx] = proposed[idx]
#                 new_bodies[idx] = [proposed[idx]] + bodies[idx][:-1]
#                 new_hps[idx] = max(0, hps[idx] - 1)
#             else:
#                 new_heads[idx] = None
#                 new_bodies[idx] = []
#                 new_lens[idx] = 0
#                 new_hps[idx] = 0

#         return new_heads, new_bodies, new_lens, new_hps

#     def _evaluate(self, heads, bodies, lens, hps, foods, W, H, 
#                   last_move: str, current_dir: Optional[str]) -> float:
#         """Evaluation with momentum to prevent zigzagging."""
#         if heads[0] is None:
#             return self.W_DEAD

#         all_dead = all(heads[i] is None for i in range(1, len(heads)))
#         if all_dead:
#             return self.W_WIN

#         score = 0.0
#         total_cells = W * H

#         your_space = self._floodfill(heads[0], bodies, W, H)
#         score += self.W_SPACE * (your_space / total_cells)

#         your_len = lens[0]
#         your_hp = hps[0]

#         opp_len_sum = 0
#         opp_count = 0
#         for i in range(1, len(heads)):
#             if heads[i] is None:
#                 continue
#             opp_count += 1
#             opp_len_sum += lens[i]

#             opp_space = self._floodfill(heads[i], bodies, W, H)
#             score += self.W_OPP_SPACE * (opp_space / total_cells)

#             dist = abs(heads[0][0] - heads[i][0]) + abs(heads[0][1] - heads[i][1])
#             if dist == 1:
#                 if your_len > lens[i]:
#                     score += self.W_H2H_WIN
#                 else:
#                     score += self.W_H2H_LOSE
#             elif dist == 2 and lens[i] >= your_len:
#                 score -= 40.0

#         if opp_count > 0:
#             avg_opp_len = opp_len_sum / opp_count
#             score += self.W_LENGTH * (your_len - avg_opp_len)

#         score += self.W_HEALTH * (your_hp - 50)

#         if foods:
#             if your_hp <= self.STARVING_THRESHOLD:
#                 w = self.W_FOOD_STARVING
#             elif your_hp <= self.HUNGRY_THRESHOLD:
#                 w = self.W_FOOD_HUNGRY
#             else:
#                 w = 0.0
#             if w > 0:
#                 nearest = min(abs(heads[0][0] - f[0]) + abs(heads[0][1] - f[1])
#                               for f in foods)
#                 score -= w * nearest

#         # Momentum: bonus for continuing in same direction
#         if current_dir and last_move == current_dir:
#             score += self.W_MOMENTUM

#         return score

#     def _floodfill(self, start, bodies, W, H) -> int:
#         """Fast floodfill with early termination."""
#         if start is None:
#             return 0
#         blocked: set[tuple[int, int]] = set()
#         for b in bodies:
#             if b:
#                 if len(b) > 1:
#                     blocked.update(b[:-1])
#                 else:
#                     blocked.update(b)

#         if start in blocked:
#             return 0

#         visited = {start}
#         q = deque([start])
#         count = 0
#         limit = 60  # 50% of 11x11 = 60, no need to count more

#         while q and count < limit:
#             x, y = q.popleft()
#             count += 1
#             for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
#                 nx, ny = x + dx, y + dy
#                 if 0 <= nx < W and 0 <= ny < H:
#                     n = (nx, ny)
#                     if n not in visited and n not in blocked:
#                         visited.add(n)
#                         q.append(n)
#         return count

#     def _quick_space(self, head, body, W, H) -> int:
#         """Very fast approximate space for opponent decisions."""
#         blocked: set[tuple[int, int]] = set()
#         if len(body) > 1:
#             blocked.update(body[:-1])
#         else:
#             blocked.update(body)
#         if head in blocked:
#             return 0
#         visited = {head}
#         q = deque([head])
#         count = 0
#         limit = 15
#         while q and count < limit:
#             x, y = q.popleft()
#             count += 1
#             for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
#                 nx, ny = x + dx, y + dy
#                 if 0 <= nx < W and 0 <= ny < H:
#                     n = (nx, ny)
#                     if n not in visited and n not in blocked:
#                         visited.add(n)
#                         q.append(n)
#         return count

#     def _get_heading(self, you: dict[str, Any]) -> Optional[str]:
#         body = you.get("body", [])
#         if len(body) < 2:
#             return None
#         head = parse_point(body[0])
#         neck = parse_point(body[1])
#         dx, dy = head[0] - neck[0], head[1] - neck[1]
#         if dx == 0 and dy == 1: return "up"
#         if dx == 0 and dy == -1: return "down"
#         if dx == 1 and dy == 0: return "right"
#         if dx == -1 and dy == 0: return "left"
#         return None

from __future__ import annotations

import time
from itertools import product
from collections import deque
from typing import Any, Optional

from agent import BaseAgent, legal_moves, next_position, parse_point


class AdvancedAgent(BaseAgent):
    """
    Alpha-beta minimax with transposition tables.
    Optimized for 11x11, 4 snakes, <500ms.
    
    Features:
    - Alpha-beta pruning (10-100x faster than plain minimax)
    - Transposition tables (reuse evaluated positions)
    - Move ordering (try best moves first for better pruning)
    - Iterative deepening (depth 1-4 with 400ms cutoff)
    - Full H2H handling at every depth
    - Momentum to prevent zigzagging
    - Center preference to avoid wall-fleeing bias
    """

    name = "advanced"
    apiversion = "1"
    color = "#8b00ff"
    author = "Skadoosh"

    TIME_LIMIT = 0.40

    # Evaluation weights
    W_SPACE = 100.0
    W_OPP_SPACE = -80.0
    W_H2H_WIN = 600.0
    W_H2H_LOSE = -1000.0
    W_MOMENTUM = 15.0
    W_CENTER = 3.0
    W_HEALTH = 0.5
    W_LENGTH = 6.0
    W_FOOD_HUNGRY = 3.0
    W_FOOD_STARVING = 7.0
    W_DEAD = -100000.0
    W_WIN = 100000.0

    HUNGRY_THRESHOLD = 55
    STARVING_THRESHOLD = 25

    # Transposition table flags
    TT_EXACT = 0
    TT_LOWER = 1
    TT_UPPER = 2

    def move(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        start = time.time()
        try:
            return self._search(game_state, you, start)
        except Exception:
            return self._fallback(game_state, you)

    def _fallback(self, game_state: dict[str, Any], you: dict[str, Any]) -> str:
        try:
            moves = legal_moves(game_state, you)
            return moves[0] if moves else "up"
        except Exception:
            return "up"

    def _search(self, game_state: dict[str, Any], you: dict[str, Any],
                start: float) -> str:
        board = game_state["board"]
        W, H = board["width"], board["height"]
        foods = tuple(sorted(parse_point(f) for f in board.get("food", [])))

        you_id = you["id"]
        your_body = [parse_point(p) for p in you["body"]]
        your_head = your_body[0]
        your_len = len(your_body)
        your_hp = int(you.get("health", 100))
        current_dir = self._get_heading(you)

        opps: list[dict] = []
        for s in board.get("snakes", []):
            if s["id"] == you_id:
                continue
            body = [parse_point(p) for p in s.get("body", [])]
            if body:
                opps.append({
                    "body": body,
                    "head": body[0],
                    "len": len(body),
                    "hp": int(s.get("health", 100)),
                })

        your_moves = self._safe_moves(your_head, your_body, your_len, opps, W, H)
        if not your_moves:
            lm = legal_moves(game_state, you)
            return lm[0] if lm else "up"
        if len(your_moves) == 1:
            return your_moves[0]

        # Order moves for better alpha-beta pruning
        your_moves = self._order_my_moves(your_moves, your_head, your_len, opps, W, H, current_dir)

        # Initialize transposition table
        self.tt = {}

        best_move = your_moves[0]
        best_score = -1e18

        # Iterative deepening with alpha-beta
        for depth in (1, 2, 3, 4):
            if time.time() - start > self.TIME_LIMIT:
                break

            alpha = -1e18
            beta = 1e18
            cur_best = your_moves[0]
            cur_best_score = -1e18

            for m in your_moves:
                if time.time() - start > self.TIME_LIMIT:
                    break

                heads, bodies, lens, hps = self._simulate_all(
                    your_head, your_body, your_len, your_hp, m, opps, W, H
                )
                if heads[0] is None:
                    continue

                score = self._min_min(heads, bodies, lens, hps, foods, W, H,
                                      depth - 1, start, alpha, beta, m, current_dir)
                
                if score > cur_best_score:
                    cur_best_score = score
                    cur_best = m
                
                alpha = max(alpha, cur_best_score)

            best_move = cur_best
            best_score = cur_best_score

            if best_score >= self.W_WIN / 2:
                break

        return best_move

    def _min_min(self, heads, bodies, lens, hps, foods, W, H,
                 depth: int, start: float, alpha: float, beta: float,
                 last_move: str, current_dir: Optional[str]) -> float:
        if time.time() - start > self.TIME_LIMIT or depth <= 0:
            return self._evaluate(heads, bodies, lens, hps, foods, W, H, last_move, current_dir)

        # Check transposition table
        tt_key = self._hash_state(heads, bodies, lens, hps, foods, depth, "MIN")
        if tt_key in self.tt:
            entry = self.tt[tt_key]
            if entry['depth'] >= depth:
                if entry['flag'] == self.TT_EXACT:
                    return entry['score']
                elif entry['flag'] == self.TT_LOWER:
                    alpha = max(alpha, entry['score'])
                elif entry['flag'] == self.TT_UPPER:
                    beta = min(beta, entry['score'])
                if alpha >= beta:
                    return entry['score']

        opp_move_lists: list[list[str]] = []
        opp_indices: list[int] = []
        for i in range(1, len(heads)):
            if heads[i] is None:
                continue
            others = []
            for j in range(len(heads)):
                if j == i or heads[j] is None:
                    continue
                others.append({
                    "body": bodies[j],
                    "head": heads[j],
                    "len": lens[j],
                    "hp": hps[j],
                })
            moves = self._safe_moves(heads[i], bodies[i], lens[i], others, W, H)
            if not moves:
                continue
            # Order opponent moves (try worst-for-us first)
            moves = self._order_opp_moves(moves, heads[i], lens[i], heads[0], lens[0], W, H)
            opp_move_lists.append(moves)
            opp_indices.append(i)

        if not opp_move_lists:
            return self.W_WIN

        orig_alpha = alpha
        min_score = 1e18
        
        for combo in product(*opp_move_lists):
            new_heads, new_bodies, new_lens, new_hps = self._simulate_opps(
                heads, bodies, lens, hps, opp_indices, combo, W, H
            )
            score = self._max_you(new_heads, new_bodies, new_lens, new_hps,
                                  foods, W, H, depth - 1, start, alpha, beta,
                                  last_move, current_dir)
            if score < min_score:
                min_score = score
            beta = min(beta, min_score)
            if alpha >= beta:
                break

        # Store in TT
        flag = self.TT_EXACT
        if min_score <= orig_alpha:
            flag = self.TT_UPPER
        elif min_score >= beta:
            flag = self.TT_LOWER
        
        self.tt[tt_key] = {
            'depth': depth,
            'score': min_score,
            'flag': flag
        }

        return min_score

    def _max_you(self, heads, bodies, lens, hps, foods, W, H,
                 depth: int, start: float, alpha: float, beta: float,
                 last_move: str, current_dir: Optional[str]) -> float:
        if time.time() - start > self.TIME_LIMIT or depth <= 0:
            return self._evaluate(heads, bodies, lens, hps, foods, W, H, last_move, current_dir)

        if heads[0] is None:
            return self.W_DEAD

        # Check TT
        tt_key = self._hash_state(heads, bodies, lens, hps, foods, depth, "MAX")
        if tt_key in self.tt:
            entry = self.tt[tt_key]
            if entry['depth'] >= depth:
                if entry['flag'] == self.TT_EXACT:
                    return entry['score']
                elif entry['flag'] == self.TT_LOWER:
                    alpha = max(alpha, entry['score'])
                elif entry['flag'] == self.TT_UPPER:
                    beta = min(beta, entry['score'])
                if alpha >= beta:
                    return entry['score']

        opps = []
        for i in range(1, len(heads)):
            if heads[i] is None:
                continue
            opps.append({
                "body": bodies[i],
                "head": heads[i],
                "len": lens[i],
                "hp": hps[i],
            })

        moves = self._safe_moves(heads[0], bodies[0], lens[0], opps, W, H)
        if not moves:
            return self.W_DEAD

        # Order moves
        moves = self._order_my_moves(moves, heads[0], lens[0], opps, W, H, current_dir)

        orig_alpha = alpha
        max_score = -1e18
        
        for m in moves:
            new_heads, new_bodies, new_lens, new_hps = self._simulate_all(
                heads[0], bodies[0], lens[0], hps[0], m, opps, W, H
            )
            score = self._min_min(new_heads, new_bodies, new_lens, new_hps,
                                  foods, W, H, depth - 1, start, alpha, beta,
                                  m, current_dir)
            if score > max_score:
                max_score = score
            alpha = max(alpha, max_score)
            if alpha >= beta:
                break

        # Store in TT
        flag = self.TT_EXACT
        if max_score <= orig_alpha:
            flag = self.TT_UPPER
        elif max_score >= beta:
            flag = self.TT_LOWER
        
        self.tt[tt_key] = {
            'depth': depth,
            'score': max_score,
            'flag': flag
        }

        return max_score

    def _order_my_moves(self, moves, head, my_len, opps, W, H, current_dir):
        """Order my moves: H2H kills first, then space, then momentum."""
        scored = []
        for m in moves:
            nh = next_position(head, m)
            score = 0.0
            
            # H2H kill opportunity
            for opp in opps:
                if abs(opp["head"][0] - nh[0]) + abs(opp["head"][1] - nh[1]) == 1:
                    if my_len > opp["len"]:
                        score += 100.0
            
            # Space
            sp = self._quick_space(nh, [], W, H)
            score += sp * 0.5
            
            # Momentum
            if current_dir and m == current_dir:
                score += 10.0
            
            # Center preference
            center_x, center_y = (W - 1) / 2.0, (H - 1) / 2.0
            dist = abs(nh[0] - center_x) + abs(nh[1] - center_y)
            score -= dist * 0.5
            
            scored.append((score, m))
        
        scored.sort(reverse=True)
        return [m for _, m in scored]

    def _order_opp_moves(self, moves, opp_head, opp_len, my_head, my_len, W, H):
        """Order opponent moves: threats to us first."""
        scored = []
        for m in moves:
            nh = next_position(opp_head, m)
            score = 0.0
            
            # H2H threat to us
            if abs(my_head[0] - nh[0]) + abs(my_head[1] - nh[1]) == 1:
                if opp_len >= my_len:
                    score += 100.0
            
            # Reduces our space (simplified: closer to us = worse)
            dist = abs(nh[0] - my_head[0]) + abs(nh[1] - my_head[1])
            score -= dist
            
            scored.append((score, m))
        
        scored.sort(reverse=True)
        return [m for _, m in scored]

    def _hash_state(self, heads, bodies, lens, hps, foods, depth, turn):
        """Create hashable state for transposition table."""
        h = tuple(heads)
        l = tuple(lens)
        f = foods
        return (h, l, f, depth, turn)

    def _safe_moves(self, head, body, my_len, opps, W, H) -> list[str]:
        """Legal moves with full H2H filtering."""
        blocked: set[tuple[int, int]] = set()

        for opp in opps:
            b = opp["body"]
            if len(b) > 1:
                blocked.update(b[:-1])
            else:
                blocked.update(b)

        if len(body) > 1:
            blocked.update(body[:-1])
        else:
            blocked.update(body)

        out: list[str] = []
        for m in ("up", "down", "left", "right"):
            nx, ny = next_position(head, m)
            if not (0 <= nx < W and 0 <= ny < H):
                continue
            p = (nx, ny)
            if p in blocked:
                continue

            dead = False
            for opp in opps:
                oh = opp["head"]
                if abs(oh[0] - p[0]) + abs(oh[1] - p[1]) == 1:
                    if my_len <= opp["len"]:
                        dead = True
                        break
            if dead:
                continue

            out.append(m)
        return out

    def _simulate_all(self, your_head, your_body, your_len, your_hp,
                      your_move, opps, W, H):
        """Simulate full turn."""
        your_new_head = next_position(your_head, your_move)

        opp_new_heads = []
        for opp in opps:
            others = [{"body": your_body, "head": your_head, "len": your_len, "hp": your_hp}]
            for other_opp in opps:
                if other_opp is not opp:
                    others.append(other_opp)
            
            opp_moves = self._safe_moves(opp["head"], opp["body"], opp["len"], others, W, H)
            if not opp_moves:
                opp_new_heads.append(None)
                continue
            
            best_m = self._pick_opp_move(opp, opp_moves, your_head, your_len, W, H)
            opp_new_heads.append(next_position(opp["head"], best_m))

        proposed = [your_new_head] + opp_new_heads
        all_bodies = [your_body] + [o["body"] for o in opps]
        all_lens = [your_len] + [o["len"] for o in opps]
        all_hps = [your_hp] + [o["hp"] for o in opps]

        alive = [True] * len(proposed)

        for i, nh in enumerate(proposed):
            if nh is None:
                alive[i] = False
                continue
            if not (0 <= nh[0] < W and 0 <= nh[1] < H):
                alive[i] = False
                continue
            for j, b in enumerate(all_bodies):
                if j == i:
                    check_body = b[:-1] if len(b) > 1 else b
                else:
                    check_body = b
                if nh in check_body:
                    alive[i] = False
                    break

        for i in range(len(proposed)):
            if not alive[i] or proposed[i] is None:
                continue
            for j in range(i + 1, len(proposed)):
                if not alive[j] or proposed[j] is None:
                    continue
                if proposed[i] == proposed[j]:
                    if all_lens[i] > all_lens[j]:
                        alive[j] = False
                    elif all_lens[j] > all_lens[i]:
                        alive[i] = False
                    else:
                        alive[i] = False
                        alive[j] = False

        heads: list[Optional[tuple[int, int]]] = [None] * len(proposed)
        bodies: list[list] = [[] for _ in range(len(proposed))]
        lens = [0] * len(proposed)
        hps = [0] * len(proposed)

        for i in range(len(proposed)):
            if alive[i]:
                heads[i] = proposed[i]
                bodies[i] = [proposed[i]] + all_bodies[i][:-1]
                lens[i] = all_lens[i]
                hps[i] = max(0, all_hps[i] - 1)
            else:
                heads[i] = None
                bodies[i] = []
                lens[i] = 0
                hps[i] = 0

        return heads, bodies, lens, hps

    def _pick_opp_move(self, opp, opp_moves, your_head, your_len, W, H):
        """Smart opponent model."""
        opp_head = opp["head"]
        opp_len = opp["len"]
        
        if your_len > opp_len:
            best_m = opp_moves[0]
            best_dist = -1
            for om in opp_moves:
                nh = next_position(opp_head, om)
                dist = abs(nh[0] - your_head[0]) + abs(nh[1] - your_head[1])
                if dist > best_dist:
                    best_dist = dist
                    best_m = om
            return best_m
        
        best_m = opp_moves[0]
        best_space = -1
        for om in opp_moves:
            nh = next_position(opp_head, om)
            sp = self._quick_space(nh, opp["body"], W, H)
            if sp > best_space:
                best_space = sp
                best_m = om
        return best_m

    def _simulate_opps(self, heads, bodies, lens, hps, opp_indices, opp_moves,
                       W, H):
        """Apply opponent moves."""
        new_heads = list(heads)
        new_bodies = [list(b) for b in bodies]
        new_lens = list(lens)
        new_hps = list(hps)

        proposed = {idx: next_position(heads[idx], m)
                    for idx, m in zip(opp_indices, opp_moves)}

        alive = {idx: True for idx in opp_indices}

        for idx, nh in proposed.items():
            if not (0 <= nh[0] < W and 0 <= nh[1] < H):
                alive[idx] = False
                continue
            
            if heads[0] is not None:
                your_body_check = bodies[0][:-1] if len(bodies[0]) > 1 else bodies[0]
                if nh in your_body_check:
                    alive[idx] = False
                    continue
            
            for j in opp_indices:
                if j == idx or not alive.get(j, False):
                    continue
                opp_body = bodies[j]
                if nh in opp_body:
                    alive[idx] = False
                    break

        if heads[0] is not None:
            for idx in opp_indices:
                if not alive[idx]:
                    continue
                if proposed[idx] == heads[0]:
                    if lens[0] > lens[idx]:
                        alive[idx] = False
                    elif lens[idx] > lens[0]:
                        new_heads[0] = None
                        new_bodies[0] = []
                        new_lens[0] = 0
                        new_hps[0] = 0
                    else:
                        alive[idx] = False
                        new_heads[0] = None
                        new_bodies[0] = []
                        new_lens[0] = 0
                        new_hps[0] = 0

        for i_idx in opp_indices:
            if not alive[i_idx]:
                continue
            for j_idx in opp_indices:
                if i_idx >= j_idx or not alive[j_idx]:
                    continue
                if proposed[i_idx] == proposed[j_idx]:
                    if lens[i_idx] > lens[j_idx]:
                        alive[j_idx] = False
                    elif lens[j_idx] > lens[i_idx]:
                        alive[i_idx] = False
                    else:
                        alive[i_idx] = False
                        alive[j_idx] = False

        for idx in opp_indices:
            if alive[idx]:
                new_heads[idx] = proposed[idx]
                new_bodies[idx] = [proposed[idx]] + bodies[idx][:-1]
                new_hps[idx] = max(0, hps[idx] - 1)
            else:
                new_heads[idx] = None
                new_bodies[idx] = []
                new_lens[idx] = 0
                new_hps[idx] = 0

        return new_heads, new_bodies, new_lens, new_hps

    def _evaluate(self, heads, bodies, lens, hps, foods, W, H,
                  last_move: str, current_dir: Optional[str]) -> float:
        """Evaluation with momentum and center preference."""
        if heads[0] is None:
            return self.W_DEAD

        all_dead = all(heads[i] is None for i in range(1, len(heads)))
        if all_dead:
            return self.W_WIN

        score = 0.0
        total_cells = W * H

        your_space = self._floodfill(heads[0], bodies, W, H)
        score += self.W_SPACE * (your_space / total_cells)

        your_len = lens[0]
        your_hp = hps[0]

        opp_len_sum = 0
        opp_count = 0
        for i in range(1, len(heads)):
            if heads[i] is None:
                continue
            opp_count += 1
            opp_len_sum += lens[i]

            opp_space = self._floodfill(heads[i], bodies, W, H)
            score += self.W_OPP_SPACE * (opp_space / total_cells)

            dist = abs(heads[0][0] - heads[i][0]) + abs(heads[0][1] - heads[i][1])
            if dist == 1:
                if your_len > lens[i]:
                    score += self.W_H2H_WIN
                else:
                    score += self.W_H2H_LOSE
            elif dist == 2 and lens[i] >= your_len:
                score -= 40.0

        if opp_count > 0:
            avg_opp_len = opp_len_sum / opp_count
            score += self.W_LENGTH * (your_len - avg_opp_len)

        score += self.W_HEALTH * (your_hp - 50)

        if foods:
            if your_hp <= self.STARVING_THRESHOLD:
                w = self.W_FOOD_STARVING
            elif your_hp <= self.HUNGRY_THRESHOLD:
                w = self.W_FOOD_HUNGRY
            else:
                w = 0.0
            if w > 0:
                nearest = min(abs(heads[0][0] - f[0]) + abs(heads[0][1] - f[1])
                              for f in foods)
                score -= w * nearest

        if current_dir and last_move == current_dir:
            score += self.W_MOMENTUM

        center_x, center_y = (W - 1) / 2.0, (H - 1) / 2.0
        dist_to_center = abs(heads[0][0] - center_x) + abs(heads[0][1] - center_y)
        max_dist = (W - 1) + (H - 1)
        center_bonus = (max_dist - dist_to_center) / max_dist
        score += self.W_CENTER * center_bonus

        return score

    def _floodfill(self, start, bodies, W, H) -> int:
        """Fast floodfill with early termination."""
        if start is None:
            return 0
        blocked: set[tuple[int, int]] = set()
        for b in bodies:
            if b:
                if len(b) > 1:
                    blocked.update(b[:-1])
                else:
                    blocked.update(b)

        if start in blocked:
            return 0

        visited = {start}
        q = deque([start])
        count = 0
        limit = 60

        while q and count < limit:
            x, y = q.popleft()
            count += 1
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H:
                    n = (nx, ny)
                    if n not in visited and n not in blocked:
                        visited.add(n)
                        q.append(n)
        return count

    def _quick_space(self, head, body, W, H) -> int:
        """Very fast approximate space."""
        blocked: set[tuple[int, int]] = set()
        if len(body) > 1:
            blocked.update(body[:-1])
        else:
            blocked.update(body)
        if head in blocked:
            return 0
        visited = {head}
        q = deque([head])
        count = 0
        limit = 15
        while q and count < limit:
            x, y = q.popleft()
            count += 1
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H:
                    n = (nx, ny)
                    if n not in visited and n not in blocked:
                        visited.add(n)
                        q.append(n)
        return count

    def _get_heading(self, you: dict[str, Any]) -> Optional[str]:
        body = you.get("body", [])
        if len(body) < 2:
            return None
        head = parse_point(body[0])
        neck = parse_point(body[1])
        dx, dy = head[0] - neck[0], head[1] - neck[1]
        if dx == 0 and dy == 1: return "up"
        if dx == 0 and dy == -1: return "down"
        if dx == 1 and dy == 0: return "right"
        if dx == -1 and dy == 0: return "left"
        return None