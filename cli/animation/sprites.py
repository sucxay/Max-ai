"""Procedural, true-color pixel frames (no external image assets)."""

from __future__ import annotations

from rich.text import Text

from cli.animation.states import MascotState

PIXELS: dict[str, str] = {
    "N": "#07152E",  # deep outline
    "B": "#167DFF",  # electric blue
    "C": "#39E7FF",  # cyan light
    "F": "#07152E",  # face glass
    "W": "#DDFBFF",  # eye whites
    "Y": "#55F2FF",  # pupils
    "P": "#FF657A",  # error accents
    "*": "#72F5FF",  # particles
}

WIDTH = 19
BODY = (
    "." * 7 + "N" * 5 + "." * 7,
    "." * 5 + "NN" + "B" * 5 + "NN" + "." * 5,
    "." * 4 + "N" + "B" * 9 + "N" + "." * 4,
    "." * 3 + "N" + "B" * 11 + "N" + "." * 3,
    "." * 2 + "N" + "B" * 13 + "N" + "." * 2,
    "." + "N" + "B" * 15 + "N" + ".",
    "N" + "B" * 17 + "N",
    "N" + "B" * 2 + "C" * 13 + "B" * 2 + "N",
    "N" + "B" * 2 + "C" * 2 + "F" * 9 + "C" * 2 + "B" * 2 + "N",
    "N" + "B" * 2 + "C" * 2 + "F" * 9 + "C" * 2 + "B" * 2 + "N",
    "N" + "B" * 2 + "C" * 2 + "F" * 9 + "C" * 2 + "B" * 2 + "N",
    "N" + "B" * 2 + "C" * 2 + "F" * 9 + "C" * 2 + "B" * 2 + "N",
    "N" + "B" * 2 + "C" * 2 + "F" * 3 + "C" * 3 + "F" * 3 + "C" * 2 + "B" * 2 + "N",
    ".N" + "B" * 15 + "N.",
    "..N" + "B" * 13 + "N..",
    ".....N" + "BB" + "NNN" + "BB" + "N.....",
    "....NN" + "BB" + "..." + "BB" + "NN....",
    "....NN" + "BB" + "..." + "BB" + "NN....",
    ".....NNN" + "..." + "NNN.....",
)


def _pixel_grid(state: MascotState, frame: int) -> list[list[str]]:
    # A fixed even-height canvas keeps every animation frame aligned.
    grid = [["." for _ in range(WIDTH)] for _ in range(len(BODY) + 3)]
    float_y = (0, 0, -1, -1, 0, 1, 1, 0)[frame % 8]
    if state == MascotState.SUCCESS:
        float_y = (-1, 0, -1, 1)[frame % 4]
    elif state == MascotState.SLEEPING:
        float_y = (0, 0, 0, 1)[frame % 4]
    top = 2 + float_y
    left = 0

    for y, row in enumerate(BODY):
        if len(row) != WIDTH:
            raise ValueError(f"Sprite row {y} must be exactly {WIDTH} pixels wide")
        for x, pixel in enumerate(row):
            if pixel != ".":
                grid[top + y][left + x] = pixel

    face_y = top + 9
    eye_offsets = (6, 11)
    if state == MascotState.ERROR:
        for eye_x in eye_offsets:
            if frame % 4 in (0, 2):
                for dx, dy in (
                    ((0, 0), (1, 1))
                    if eye_x == eye_offsets[0]
                    else ((1, 0), (0, 1))
                ):
                    grid[face_y + dy][left + eye_x + dx] = "P"
            else:
                grid[face_y][left + eye_x] = "P"
                grid[face_y][left + eye_x + 1] = "P"
    elif state == MascotState.SUCCESS:
        for eye_x in eye_offsets:
            for dx, dy in (
                ((0, 0), (1, 1))
                if eye_x == eye_offsets[0]
                else ((1, 0), (0, 1))
            ):
                grid[face_y + dy][left + eye_x + dx] = "C"
    elif state == MascotState.SLEEPING or (
        state == MascotState.IDLE and frame % 19 in (14, 15)
    ):
        for eye_x in eye_offsets:
            for dx in range(3):
                grid[face_y + 1][left + eye_x + dx] = "C"
    else:
        pupil_shift = 0
        if state == MascotState.IDLE:
            pupil_shift = (-1, 0, 0, 1, 0, 0)[(frame // 3) % 6]
        elif state == MascotState.THINKING:
            pupil_shift = -1 if frame % 8 < 4 else 1
        elif state == MascotState.LISTENING:
            pupil_shift = 0
        elif state == MascotState.EXECUTING:
            pupil_shift = -1 if frame % 2 else 1
        for eye_x in eye_offsets:
            grid[face_y][left + eye_x + pupil_shift] = "W"
            grid[face_y][left + eye_x + 1 + pupil_shift] = "W"
            grid[face_y + 1][left + eye_x + pupil_shift] = "Y"
            grid[face_y + 1][left + eye_x + 1 + pupil_shift] = "Y"
            if state == MascotState.LISTENING:
                grid[face_y + 2][left + eye_x] = "C"
                grid[face_y + 2][left + eye_x + 1] = "C"

    # A tiny centered mouth gives the face a stable, readable expression.
    if state not in (MascotState.SLEEPING, MascotState.ERROR, MascotState.SUCCESS):
        grid[face_y + 3][left + 8] = "C"
        grid[face_y + 3][left + 9] = "C"

    # State-specific pixels make actions visually distinct at a glance.
    if state == MascotState.EXECUTING and frame % 2:
        grid[top + 1][0] = "C"
        grid[top + 1][WIDTH - 1] = "C"
    if state == MascotState.SUCCESS:
        for x, y in (
            (2, top - 1),
            (WIDTH - 3, top - 1),
            (0, top + 2),
            (WIDTH - 1, top + 2),
        ):
            grid[y][x] = "*"
    elif state in (MascotState.THINKING, MascotState.LISTENING):
        if frame % 3 != 2:
            grid[top + 1][WIDTH - 1] = "*"
        if frame % 3 == 1:
            grid[top + 3][0] = "*"
    elif state == MascotState.IDLE and frame % 4 == 0:
        grid[top + 1][0] = "*"
        grid[top + 2][WIDTH - 1] = "*"
    elif state == MascotState.SLEEPING and frame % 4 == 0:
        grid[top + 1][WIDTH - 1] = "*"

    return grid


def render_sprite(state: MascotState, frame: int) -> Text:
    """Render two vertical pixels per terminal cell, leaving empty pixels transparent."""
    grid = _pixel_grid(state, frame)
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
