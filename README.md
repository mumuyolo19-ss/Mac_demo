# Tetris (tkinter)

A small playable Tetris demo written in Python using `tkinter`.

## Requirements

- Python `3.11+`
- `tkinter` support in your Python installation

## Run

```bash
python3.11 tetris.py
```

If you are not in this directory, run with an absolute path:

```bash
python3.11 /Users/yolosun/repo_code/test/tetris.py
```

## Controls

- Left / Right: move piece
- Up: rotate clockwise
- Z: rotate counter-clockwise
- Down: soft drop
- Space: hard drop
- P: pause / resume
- R: restart
- Esc: quit

## Notes

- The board is 10x20.
- Score increases from line clears and soft drop.
- Game speed increases as level goes up.
