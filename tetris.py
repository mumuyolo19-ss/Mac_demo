import random
import tkinter as tk
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


COLS = 10
ROWS = 20
CELL = 30

# Drawing area: board + a top area for HUD.
# Keep HUD a bit taller so text does not overlap on macOS.
HUD_H = 96
BOARD_W = COLS * CELL
SIDE_W = 140
CANVAS_W = BOARD_W + SIDE_W
CANVAS_H = ROWS * CELL + HUD_H


Coord = Tuple[int, int]


def rotate_coords_4x4(coords: List[Coord]) -> List[Coord]:
    """
    Rotate 4x4-grid coordinates clockwise.
    Transform: (x, y) -> (y, 3 - x)
    """
    return [(y, 3 - x) for (x, y) in coords]


def build_rotations(base_coords: List[Coord]) -> List[List[Coord]]:
    rots = [base_coords]
    cur = base_coords
    for _ in range(3):
        cur = rotate_coords_4x4(cur)
        # Keep stable ordering for determinism.
        rots.append(sorted(cur))
    # Normalize initial ordering too.
    rots[0] = sorted(rots[0])
    return rots


# Base coordinates are in a 4x4 grid (0..3 for both x and y).
BASE_SHAPES: Dict[str, List[Coord]] = {
    "I": [(0, 1), (1, 1), (2, 1), (3, 1)],
    "O": [(1, 0), (2, 0), (1, 1), (2, 1)],
    "T": [(1, 0), (0, 1), (1, 1), (2, 1)],
    "S": [(1, 1), (2, 1), (0, 2), (1, 2)],
    "Z": [(0, 1), (1, 1), (1, 2), (2, 2)],
    "J": [(0, 0), (0, 1), (1, 1), (2, 1)],
    "L": [(2, 0), (0, 1), (1, 1), (2, 1)],
}

SHAPES: Dict[str, List[List[Coord]]] = {k: build_rotations(v) for k, v in BASE_SHAPES.items()}

COLORS: Dict[str, str] = {
    "I": "#00C8FF",
    "O": "#FFD400",
    "T": "#B266FF",
    "S": "#2ECC71",
    "Z": "#FF6B6B",
    "J": "#4D7CFE",
    "L": "#FF9F43",
}


PIECE_TYPES = ["I", "O", "T", "S", "Z", "J", "L"]


@dataclass
class ActivePiece:
    kind: str
    rotation: int
    px: int  # x offset of the 4x4 grid on the board
    py: int  # y offset of the 4x4 grid on the board


class TetrisApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Tetris (tkinter)")

        self.canvas = tk.Canvas(root, width=CANVAS_W, height=CANVAS_H, bg="#0b1020", highlightthickness=0)
        self.canvas.pack()

        self.board: List[List[Optional[str]]] = [[None for _ in range(COLS)] for _ in range(ROWS)]

        self.bag: List[str] = []
        self.current: Optional[ActivePiece] = None
        self.next_kind: Optional[str] = None

        self.score = 0
        self.lines = 0
        self.level = 1

        self.paused = False
        self.game_over = False
        self.after_id = None

        self.line_scores = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}

        self._init_pieces()

        self._bind_keys()
        self._draw()
        self._tick()

    def _bind_keys(self) -> None:
        self.root.bind("<Left>", lambda _e: self._on_move(-1))
        self.root.bind("<Right>", lambda _e: self._on_move(1))
        self.root.bind("<Up>", lambda _e: self._on_rotate(1))
        self.root.bind("<z>", lambda _e: self._on_rotate(-1))
        self.root.bind("<Down>", lambda _e: self._on_soft_drop())
        self.root.bind("<space>", lambda _e: self._on_hard_drop())
        self.root.bind("p", lambda _e: self._toggle_pause())
        self.root.bind("P", lambda _e: self._toggle_pause())
        self.root.bind("r", lambda _e: self._restart())
        self.root.bind("R", lambda _e: self._restart())
        self.root.bind("<Escape>", lambda _e: self._quit())

    def _quit(self) -> None:
        self.game_over = True
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
        self.root.destroy()

    def _restart(self) -> None:
        self.board = [[None for _ in range(COLS)] for _ in range(ROWS)]
        self.score = 0
        self.lines = 0
        self.level = 1
        self.paused = False
        self.game_over = False
        self.current = None
        self.next_kind = None
        self._init_pieces()
        self._draw()

    def _toggle_pause(self) -> None:
        if self.game_over:
            return
        self.paused = not self.paused
        self._draw()

    def _refill_bag(self) -> None:
        self.bag = PIECE_TYPES[:]
        random.shuffle(self.bag)

    def _init_pieces(self) -> None:
        self._refill_bag()
        self.current = self._spawn_from_kind(self.bag.pop())
        if not self.bag:
            self._refill_bag()
        self.next_kind = self.bag.pop()

    def _spawn_from_kind(self, kind: str) -> ActivePiece:
        # Place the 4x4 grid roughly centered.
        px = (COLS - 4) // 2
        # Start a bit above the board so rotations can fit.
        py = -2
        return ActivePiece(kind=kind, rotation=0, px=px, py=py)

    def _shape_cells(self, piece: ActivePiece) -> List[Coord]:
        return SHAPES[piece.kind][piece.rotation % 4]

    def _collides(self, piece: ActivePiece) -> bool:
        for (x, y) in self._shape_cells(piece):
            nx = piece.px + x
            ny = piece.py + y
            if nx < 0 or nx >= COLS:
                return True
            if ny >= ROWS:
                return True
            if ny >= 0 and self.board[ny][nx] is not None:
                return True
        return False

    def _lock_piece(self) -> None:
        assert self.current is not None
        kind = self.current.kind
        for (x, y) in self._shape_cells(self.current):
            nx = self.current.px + x
            ny = self.current.py + y
            if ny < 0:
                # Locked while part is above the visible board => game over.
                self.game_over = True
                return
            self.board[ny][nx] = kind

        cleared = self._clear_lines()
        if cleared:
            self.lines += cleared
            self.level = 1 + (self.lines // 10)
            self.score += self.line_scores[cleared] * self.level

        # Spawn next.
        self.current = self._spawn_from_kind(self.next_kind if self.next_kind is not None else random.choice(PIECE_TYPES))
        if not self.bag:
            self._refill_bag()
        self.next_kind = self.bag.pop()

        if self._collides(self.current):
            self.game_over = True

    def _clear_lines(self) -> int:
        cleared = 0
        y = ROWS - 1
        while y >= 0:
            if all(self.board[y][x] is not None for x in range(COLS)):
                del self.board[y]
                self.board.insert(0, [None for _ in range(COLS)])
                cleared += 1
            else:
                y -= 1
        return cleared

    def _tick_ms(self) -> int:
        # Level 1: 800ms. Increase speed gradually.
        ms = 800 - (self.level - 1) * 60
        return max(50, ms)

    def _tick(self) -> None:
        if self.game_over:
            self._draw()
            return

        if not self.paused:
            assert self.current is not None
            moved = ActivePiece(
                kind=self.current.kind,
                rotation=self.current.rotation,
                px=self.current.px,
                py=self.current.py + 1,
            )
            if not self._collides(moved):
                self.current = moved
            else:
                self._lock_piece()

        self._draw()
        self.after_id = self.root.after(self._tick_ms(), self._tick)

    def _try_move(self, dx: int, dy: int) -> bool:
        if self.game_over or self.paused or self.current is None:
            return False
        assert self.current is not None
        candidate = ActivePiece(
            kind=self.current.kind,
            rotation=self.current.rotation,
            px=self.current.px + dx,
            py=self.current.py + dy,
        )
        if not self._collides(candidate):
            self.current = candidate
            return True
        return False

    def _on_move(self, dx: int) -> None:
        self._try_move(dx, 0)
        self._draw()

    def _on_soft_drop(self) -> None:
        if self._try_move(0, 1):
            self.score += 1  # soft drop reward
        self._draw()

    def _on_hard_drop(self) -> None:
        if self.game_over or self.paused or self.current is None:
            return
        assert self.current is not None
        ghost = ActivePiece(
            kind=self.current.kind,
            rotation=self.current.rotation,
            px=self.current.px,
            py=self.current.py,
        )
        while not self._collides(ActivePiece(kind=ghost.kind, rotation=ghost.rotation, px=ghost.px, py=ghost.py + 1)):
            ghost = ActivePiece(kind=ghost.kind, rotation=ghost.rotation, px=ghost.px, py=ghost.py + 1)
        self.current = ghost
        self._lock_piece()
        self._draw()

    def _on_rotate(self, direction: int) -> None:
        if self.game_over or self.paused or self.current is None:
            return
        assert self.current is not None

        new_rotation = (self.current.rotation + direction) % 4
        rotated = ActivePiece(kind=self.current.kind, rotation=new_rotation, px=self.current.px, py=self.current.py)

        if not self._collides(rotated):
            self.current = rotated
            self._draw()
            return

        # Simple wall kicks (try offsets) to reduce rotation frustration.
        kicks = [(0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1), (0, 1)]
        for dx, dy in kicks[1:]:
            candidate = ActivePiece(kind=rotated.kind, rotation=rotated.rotation, px=rotated.px + dx, py=rotated.py + dy)
            if not self._collides(candidate):
                self.current = candidate
                self._draw()
                return

    def _ghost_y(self) -> Optional[int]:
        if self.current is None or self.game_over:
            return None
        ghost = ActivePiece(kind=self.current.kind, rotation=self.current.rotation, px=self.current.px, py=self.current.py)
        while not self._collides(ActivePiece(kind=ghost.kind, rotation=ghost.rotation, px=ghost.px, py=ghost.py + 1)):
            ghost.py += 1
        return ghost.py

    def _draw_block(self, x: int, y: int, color: str, *, ghost: bool = False) -> None:
        # x,y are board coordinates.
        if y < 0:
            return
        px1 = x * CELL
        py1 = y * CELL + HUD_H
        px2 = px1 + CELL
        py2 = py1 + CELL

        if ghost:
            self.canvas.create_rectangle(px1, py1, px2, py2, fill=color, outline=color, stipple="gray50")
        else:
            self.canvas.create_rectangle(px1, py1, px2, py2, fill=color, outline="#111111", width=1)

    def _draw(self) -> None:
        self.canvas.delete("all")

        # HUD background.
        self.canvas.create_rectangle(0, 0, CANVAS_W, HUD_H, fill="#0d1630", outline="")

        # Board background.
        self.canvas.create_rectangle(0, HUD_H, BOARD_W, CANVAS_H, fill="#0b1020", outline="")
        self.canvas.create_rectangle(BOARD_W, HUD_H, CANVAS_W, CANVAS_H, fill="#101735", outline="")

        # Subtle grid lines.
        for x in range(COLS + 1):
            gx = x * CELL
            self.canvas.create_line(gx, HUD_H, gx, CANVAS_H, fill="#111828")
        for y in range(ROWS + 1):
            gy = y * CELL + HUD_H
            self.canvas.create_line(0, gy, BOARD_W, gy, fill="#111828")

        # Locked blocks.
        for y in range(ROWS):
            for x in range(COLS):
                kind = self.board[y][x]
                if kind is not None:
                    self._draw_block(x, y, COLORS[kind])

        # Current piece + ghost.
        if self.current is not None and not self.game_over:
            ghost_y = self._ghost_y()
            if ghost_y is not None:
                ghost_piece = ActivePiece(kind=self.current.kind, rotation=self.current.rotation, px=self.current.px, py=ghost_y)
                for (x, y) in self._shape_cells(ghost_piece):
                    self._draw_block(ghost_piece.px + x, ghost_piece.py + y, COLORS[ghost_piece.kind], ghost=True)

            for (x, y) in self._shape_cells(self.current):
                self._draw_block(self.current.px + x, self.current.py + y, COLORS[self.current.kind])

        # HUD texts in separate rows to avoid overlap.
        self.canvas.create_text(
            10,
            14,
            anchor="nw",
            fill="#e6eefc",
            font=("Courier", 14),
            text=f"Score: {self.score}   Lines: {self.lines}   Level: {self.level}",
        )

        next_txt = self.next_kind if self.next_kind is not None else "-"
        self.canvas.create_text(
            10,
            44,
            anchor="nw",
            fill="#9fb2d9",
            font=("Courier", 13),
            text=f"Next: {next_txt}",
        )

        hint = "Left/Right move   Up rotate   Down soft   Space hard   P pause   R restart"
        self.canvas.create_text(
            10,
            HUD_H - 32,
            anchor="nw",
            fill="#7f95c6",
            font=("Courier", 11),
            text=hint,
            width=CANVAS_W - 20,
        )

        if self.paused and not self.game_over:
            self.canvas.create_text(BOARD_W // 2, HUD_H + (ROWS * CELL) // 2, anchor="center",
                                    fill="#ffffff", font=("Courier", 26), text="PAUSED")
        if self.game_over:
            self.canvas.create_text(BOARD_W // 2, HUD_H + (ROWS * CELL) // 2, anchor="center",
                                    fill="#ffffff", font=("Courier", 26), text="GAME OVER")
            self.canvas.create_text(BOARD_W // 2, HUD_H + (ROWS * CELL) // 2 + 34, anchor="center",
                                    fill="#cfd9ff", font=("Courier", 13), text="Press R to restart")


def main() -> None:
    root = tk.Tk()
    # A fixed window size keeps keyboard controls predictable.
    root.resizable(False, False)
    app = TetrisApp(root)
    app.root.mainloop()


if __name__ == "__main__":
    main()

