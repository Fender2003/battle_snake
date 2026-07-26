from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


def replay_game(history: list[Any], pause_seconds: float = 0.2) -> None:
    fig, ax = plt.subplots(figsize=(7, 7))
    for snapshot in history:
        ax.clear()
        width = snapshot.width
        height = snapshot.height
        ax.set_xlim(0, width)
        ax.set_ylim(0, height)
        ax.set_xticks(range(width + 1))
        ax.set_yticks(range(height + 1))
        ax.grid(True, linewidth=0.5)
        ax.set_aspect("equal")
        ax.set_title(f"Turn {snapshot.turn}")

        for food in snapshot.food:
            ax.add_patch(Rectangle((food["x"], food["y"]), 1, 1, color="red", alpha=0.8))

        for i, snake in enumerate(snapshot.snakes):
            color = f"C{i % 10}"
            for idx, point in enumerate(snake["body"]):
                shade = 0.95 if idx == 0 else 0.7
                ax.add_patch(
                    Rectangle(
                        (point["x"], point["y"]),
                        1,
                        1,
                        color=color,
                        alpha=shade,
                    )
                )
                if idx == 0:
                    ax.text(
                        point["x"] + 0.05,
                        point["y"] + 0.7,
                        snake["name"],
                        fontsize=7,
                        color="black",
                    )

        plt.pause(pause_seconds)
    plt.show()
