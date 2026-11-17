"""Fixed-size cat sprites, packed into square half-block terminal pixels."""
from __future__ import annotations

from rich.text import Text
from cli.animation.states import MascotState

PIXELS = {
    "N": "#16456B", "B": "#269CFF", "C": "#77DDFF",
    "W": "#E5F9FF", "Y": "#09213B", "M": "#FF9FB8",
    "P": "#FF657A", "*": "#72F5FF",
}
WIDTH = 19
HEIGHT = 22


def _pixel_grid(state: MascotState, frame: int, gaze: int = 0) -> list[list[str]]:
    grid = [["."] * WIDTH for _ in range(HEIGHT)]
    bounce = -1 if state == MascotState.SUCCESS and frame % 6 < 3 else 0

    def dot(x: int, y: int, color: str) -> None:
        y += bounce
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            grid[y][x] = color

    def row(y: int, start: int, end: int, color: str) -> None:
        for x in range(start, end + 1):
            dot(x, y, color)

    # Upright triangular ears, with pink inner ears.
    for y in range(3, 7):
        for x in range(4, 5 + y - 3):
            dot(x, y, "N")
            dot(18 - x, y, "N")
    for x, y in ((4, 4), (4, 5), (5, 5), (14, 4), (14, 5), (13, 5)):
        dot(x, y, "M")
    # Rounded head and tapered seated body.
    for y, start, end in ((6, 4, 14), (7, 3, 15), (8, 3, 15),
                           (9, 3, 15), (10, 3, 15), (11, 4, 14),
                           (12, 5, 13), (13, 6, 12), (14, 6, 12),
                           (15, 5, 13), (16, 5, 13), (17, 5, 13),
                           (18, 5, 13)):
        row(y, start, end, "N")
        row(y, start + 1, end - 1, "B")
    # Forehead stripes, cheek tufts, muzzle and white chest.
    for x in (7, 9, 11):
        dot(x, 6, "C")
    for y in (10, 11):
        row(y, 7, 11, "W")
    for y in range(13, 17):
        row(y, 8, 10, "C")
    for x in (5, 6, 7, 11, 12, 13):
        dot(x, 19, "C")
    # Curled tail swishes independently of the body.
    tip = (0, 0, 1, 1, 0, -1, -1, 0)[frame % 8]
    for x, y in ((14, 18), (15, 18), (16, 17), (17, 16),
                 (17, 15), (17 + tip, 14), (16 + tip, 13)):
        dot(x, y, "C")
    closed = state == MascotState.SLEEPING or (state == MascotState.IDLE and frame % 24 in (20, 21))
    for x in (6, 11):
        if closed:
            row(9, x, x + 1, "Y")
        elif state == MascotState.SUCCESS:
            dot(x, 9, "Y")
            dot(x + 1, 8, "Y")
        else:
            row(8, x, x + 1, "W")
            row(9, x, x + 1, "W")
            shift = (gaze > 0) if state == MascotState.WATCHING else (frame // 5) % 2
            eye_y = 8 if state == MascotState.THINKING else 9
            dot(x + int(shift), eye_y, "P" if state == MascotState.ERROR else "Y")
    dot(9, 10, "M")
    for x in (8, 10):
        dot(x, 11, "N")
    # Whiskers extend beyond the cheeks.
    for x, y in ((1, 9), (2, 10), (1, 11), (17, 9), (16, 10), (17, 11)):
        dot(x, y, "C")
    if state == MascotState.THINKING:
        for i in range(1 + (frame // 2) % 3):
            dot(11 + i * 2, 1, "W")
    elif state == MascotState.LISTENING:
        # Sound waves pulse outside the ears during microphone capture.
        for side in (1, 17):
            for y in range(4 - frame % 3, 6 + frame % 3):
                dot(side, y, "*")
    elif state == MascotState.WATCHING:
        # A tiny typing cursor accompanies the downward, tracking gaze.
        row(21, 4, 14, "N")
        dot(5 + (gaze + 1) * 4, 21, "C")
    elif state == MascotState.EXECUTING:
        dot(6 + frame % 7, 21, "*")
        dot(7 if frame % 2 else 11, 18, "W")
    elif state == MascotState.SUCCESS:
        for x, y in ((1, 3), (17, 2), (2, 15)):
            dot(x, y + frame % 2, "*")
    elif state == MascotState.SLEEPING:
        for x, y in ((15, 1), (16, 1), (16, 2), (15, 3), (16, 3)):
            dot(x, y + (frame // 4) % 2, "C")
    elif state == MascotState.ERROR:
        dot(17, 1, "P")
        dot(17, 2, "P")
        dot(17, 4, "P")
    return grid


def render_sprite(state: MascotState, frame: int, gaze: int = 0) -> Text:
    """Render two vertical pixels per terminal cell, leaving empty pixels transparent."""
    grid = _pixel_grid(state, frame, gaze)
    output = Text()
    for y in range(0, len(grid) - 1, 2):
        for x in range(len(grid[0])):
            upper = PIXELS.get(grid[y][x])
            lower = PIXELS.get(grid[y + 1][x])
            if upper is None and lower is None:
                output.append(" ")
            elif upper is None:
                output.append("▄", style=lower)
            elif lower is None:
                output.append("▀", style=upper)
            elif upper == lower:
                output.append("█", style=upper)
            else:
                output.append("▀", style=f"{upper} on {lower}")
        if y + 2 < len(grid) - 1:
            output.append("\n")
    return output
