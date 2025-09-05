# Space Invader in Python 🎮

Classic arcade-inspired **Space Invader** game built in Python using [pygame](https://www.pygame.org/). Developed as a single-file project for learning and showcasing simple game development.

---

## 🚀 Features

- **Single file implementation**: everything is inside `spaceinvader.py`
- **Player controls** with movement, shooting, and multiple lives
- **Enemy grid** marching down the screen, increasing in speed as they are destroyed
- **Different enemy types**: Common, Tough (2 HP), Shooter (fires back)
- **Boss fly-by** for bonus points
- **Protective shields** that absorb hits and degrade over time
- **Combo score multiplier** for quick consecutive kills
- **Wave progression** with increasing difficulty
- **Particles & screen shake** effects (optional)
- **Procedural sound effects** (toggle in menu)
- **Highscore system** stored in `highscore.json`
- **Debug keys** (God mode, skip wave, etc.)

---

## 🕹 Controls

| Key                  | Action                       |
|----------------------|------------------------------|
| `← / →` or `A / D`   | Move left / right            |
| `Space`              | Shoot                        |
| `P` or `Esc`         | Pause / Resume               |
| `Enter`              | Start game / Confirm actions |
| `Esc (in Menu)`      | Quit game                    |
| `S (in Menu)`        | Toggle sound on/off          |

**Debug keys (for testing):**
- `F1` — print current wave stats
- `F2` — toggle GODMODE (invulnerability)
- `F3` — skip current wave

---

## 📦 Installation

1. Clone the repository:
```bash
git clone https://github.com/L1amDev/Space-Invader.git
cd Space-Invader
````

2. Install dependencies:

```bash
pip install pygame
```

3. Run the game:

```bash
python spaceinvader.py
```

---

## 📊 Highscores

Highscores are automatically saved to `highscore.json` in the repository root.
Top-5 scores are displayed in the main menu.

---

## 🛠 Project Structure

```
Space-Invader/
│
├── spaceinvader.py     # Main game script (single file)
├── highscore.json      # Generated automatically (if not present)
└── LICENSE             # MIT License
```

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
You are free to use, modify, and distribute it as you like.
