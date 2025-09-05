"""
Space Invader — single-file pygame game.
File: spaceinvader.py

How to run:
  pip install pygame
  python spaceinvader.py

This game follows the previously defined spec: menu, waves of enemies, shields,
player/enemy bullets, boss fly-by, score with combo, highscores, pause, debug keys.
All assets are generated at runtime; no external images or sounds are required.
"""
from __future__ import annotations
import os
import sys
import json
import math
import random
import time
import struct
from dataclasses import dataclass
from typing import List, Tuple, Optional

import pygame

# ============================
# SETTINGS & CONSTANTS
# ============================
WIDTH, HEIGHT = 800, 600
FPS = 60
TITLE = "Space Invader"
HIGHSCORE_PATH = os.path.join(os.path.dirname(__file__), "highscore.json")

# Feature flags
ENABLE_SOUND = True
ENABLE_PARTICLES = True
HARD_MODE = False

# Colors
COLOR_BG = (13, 16, 33)          # #0d1021
COLOR_UI = (230, 235, 255)
COLOR_PLAYER = (240, 240, 255)
COLOR_ENEMY_COMMON = (120, 200, 255)
COLOR_ENEMY_TOUGH = (255, 160, 120)
COLOR_ENEMY_SHOOTER = (180, 255, 160)
COLOR_BOSS = (255, 80, 140)
COLOR_BULLET_PLAYER = (255, 255, 180)
COLOR_BULLET_ENEMY = (255, 120, 120)
COLOR_SHIELD = (90, 200, 160)
COLOR_SHIELD_DMG = (180, 110, 110)
COLOR_DIM = (80, 90, 120)
COLOR_HIGHLIGHT = (160, 200, 255)

# Gameplay constants
PLAYER_SPEED = 300.0 * (1.2 if HARD_MODE else 1.0)
PLAYER_SIZE = (50, 30)
PLAYER_CD_MS = int(250 * (0.8 if HARD_MODE else 1.0))
PLAYER_MAX_BULLETS = 3 + (1 if HARD_MODE else 0)
PLAYER_LIVES = 3

ENEMY_ROWS = 6
ENEMY_COLS = 8
ENEMY_START_SPEED = 72.0 * (1.2 if HARD_MODE else 1.0)  # px/sec
ENEMY_STEP_DOWN = 20
ENEMY_FIRE_RATE = 0.28 * (1.2 if HARD_MODE else 1.0)    # shots/sec baseline
ENEMY_MAX_BULLETS = 7 if HARD_MODE else 6

BOSS_CD_MIN, BOSS_CD_MAX = 20.0, 30.0
BOSS_SPEED = 200.0

PLAYER_BULLET_SPEED = -500.0
ENEMY_BULLET_SPEED = 300.0

SHIELD_COUNT = 4
SHIELD_SEG_ROWS = 3
SHIELD_SEG_COLS = 6
SHIELD_SEG_SIZE = 12
SHIELD_SEG_HP = 3

WAVE_SPEED_MULT = 1.10
WAVE_FIRE_MULT = 1.05

COMBO_WINDOW = 1.0  # seconds
COMBO_STEP = 0.1

# Scenes
SCENE_MENU = "MENU"
SCENE_PLAYING = "PLAYING"
SCENE_PAUSED = "PAUSED"
SCENE_GAME_OVER = "GAME_OVER"

# Debug keys states
GODMODE = False


# ============================
# UTILS
# ============================
def clamp(x: float, lo: float, hi: float) -> float:\n    return lo if x < lo else hi if x > hi else x


def load_highscores() -> dict:
    # Structure: {"top": [ints], "last_updated": iso}
    if not os.path.exists(HIGHSCORE_PATH):
        return {"top": [], "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        with open(HIGHSCORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data.get("top", []), list):
                raise ValueError("invalid structure")
            return data
    except Exception:
        return {"top": [], "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def save_highscores(top: List[int]):
    data = {
        "top": list(sorted(top, reverse=True))[:5],
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        with open(HIGHSCORE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        # Fail silently; game should not crash if disk is read-only
        pass


# ============================
# SOUND
# ============================
class SoundManager:
    """Generate and play very small procedural sounds. No external files required."""
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.sounds = {}
        self._init_mixer()
        if self.enabled:
            # Pre-generate small tones
            self.sounds["shoot"] = self._make_tone(880, 60, 0.25)
            self.sounds["enemy_shoot"] = self._make_tone(440, 80, 0.18)
            self.sounds["explosion"] = self._make_noise_pop(160, 0.3)
            self.sounds["highscore"] = self._make_tone(1320, 220, 0.3)

    def _init_mixer(self):
        if not self.enabled:
            return
        try:
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=1, buffer=512)
            pygame.mixer.init()
        except Exception:
            self.enabled = False

    def _make_tone(self, freq: int, ms: int, volume: float):
        if not self.enabled:
            return None
        sr = 22050
        n = max(1, int(sr * (ms / 1000.0)))
        amp = int(32767 * volume)
        buf = bytearray()
        for i in range(n):
            t = i / sr
            s = int(amp * math.sin(2 * math.pi * freq * t))
            buf += struct.pack('<h', s)
        try:
            return pygame.mixer.Sound(buffer=bytes(buf))
        except Exception:
            return None

    def _make_noise_pop(self, ms: int, volume: float):
        if not self.enabled:
            return None
        sr = 22050
        n = max(1, int(sr * (ms / 1000.0)))
        buf = bytearray()
        for i in range(n):
            decay = 1.0 - (i / n)
            s = int(32767 * volume * decay * (random.random() * 2 - 1))
            buf += struct.pack('<h', s)
        try:
            return pygame.mixer.Sound(buffer=bytes(buf))
        except Exception:
            return None

    def play(self, name: str):
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd is not None:
            try:
                snd.play()
            except Exception:
                pass


# ============================
# ENTITIES
# ============================
class Bullet:
    def __init__(self, x: float, y: float, vy: float, damage: int, is_player: bool):
        self.rect = pygame.Rect(int(x) - 2, int(y) - 8, 4, 12)
        self.vy = vy
        self.damage = damage
        self.is_player = is_player
        self.alive = True

    def update(self, dt: float):
        self.rect.y += int(self.vy * dt)
        if self.rect.bottom < 0 or self.rect.top > HEIGHT:
            self.alive = False

    def draw(self, surf: pygame.Surface, ox: int = 0, oy: int = 0):
        color = COLOR_BULLET_PLAYER if self.is_player else COLOR_BULLET_ENEMY
        pygame.draw.rect(surf, color, self.rect.move(ox, oy))


class Particle:
    def __init__(self, x: float, y: float):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(80, 220)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.x = x
        self.y = y
        self.life = random.uniform(0.08, 0.22)
        self.max_life = self.life
        self.size = random.randint(1, 3)

    def update(self, dt: float):
        self.life -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 180 * dt  # small gravity

    def draw(self, surf: pygame.Surface, color: Tuple[int, int, int], ox: int = 0, oy: int = 0):
        if self.life <= 0:
            return
        alpha = clamp(self.life / self.max_life, 0.0, 1.0)
        s = max(1, int(self.size * alpha * 2))
        rect = pygame.Rect(int(self.x) - s // 2, int(self.y) - s // 2, s, s)
        pygame.draw.rect(surf, color, rect.move(ox, oy))


class Player:
    def __init__(self, x: int, y: int):
        self.rect = pygame.Rect(0, 0, *PLAYER_SIZE)
        self.rect.centerx = x
        self.rect.bottom = y
        self.speed = PLAYER_SPEED
        self.shoot_cd = PLAYER_CD_MS / 1000.0
        self._shoot_timer = 0.0
        self.lives = PLAYER_LIVES
        self.invuln_timer = 0.0

    def reset_position(self):
        self.rect.centerx = WIDTH // 2
        self.rect.bottom = HEIGHT - 30

    def update(self, dt: float, keys: pygame.key.ScancodeWrapper):
        # Movement
        move = 0.0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move -= 1.0
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move += 1.0
        self.rect.x += int(move * self.speed * dt)
        self.rect.left = max(10, self.rect.left)
        self.rect.right = min(WIDTH - 10, self.rect.right)
        # Timers
        if self._shoot_timer > 0:
            self._shoot_timer -= dt
        if self.invuln_timer > 0:
            self.invuln_timer -= dt

    def can_shoot(self, current_player_bullets: int) -> bool:
        return self._shoot_timer <= 0 and current_player_bullets < PLAYER_MAX_BULLETS

    def shoot(self) -> Bullet:
        self._shoot_timer = self.shoot_cd
        bx = self.rect.centerx
        by = self.rect.top - 6
        return Bullet(bx, by, PLAYER_BULLET_SPEED, 1, True)

    def hit(self):
        if self.invuln_timer > 0 or GODMODE:
            return False
        self.lives -= 1
        self.invuln_timer = 1.5
        return True

    def draw(self, surf: pygame.Surface, ox: int = 0, oy: int = 0):
        # Simple triangular ship on a rectangle body
        body = self.rect.inflate(-10, -8)
        pygame.draw.rect(surf, COLOR_PLAYER, body.move(ox, oy))
        tri = [
            (self.rect.centerx + ox, self.rect.top - 8 + oy),
            (self.rect.left + 8 + ox, self.rect.top + 8 + oy),
            (self.rect.right - 8 + ox, self.rect.top + 8 + oy),
        ]
        pygame.draw.polygon(surf, COLOR_PLAYER, tri)
        # Blink when invulnerable
        if self.invuln_timer > 0:
            if int(self.invuln_timer * 10) % 2 == 0:
                overlay = self.rect.inflate(4, 4).move(ox, oy)
                pygame.draw.rect(surf, (255, 255, 255), overlay, 2)


class Enemy:
    def __init__(self, x: int, y: int, etype: str, row_idx: int):
        self.rect = pygame.Rect(x, y, 44, 28)
        self.type = etype  # 'common', 'tough', 'shooter'
        self.row_idx = row_idx
        if etype == 'common':
            self.hp = 1
            self.points = 10
            self.color = COLOR_ENEMY_COMMON
        elif etype == 'tough':
            self.hp = 2
            self.points = 20
            self.color = COLOR_ENEMY_TOUGH
        else:
            self.hp = 1
            self.points = 30
            self.color = COLOR_ENEMY_SHOOTER
        self.hit_flash = 0.0

    def take_damage(self, dmg: int):
        self.hp -= dmg
        self.hit_flash = 0.1
        return self.hp <= 0

    def draw(self, surf: pygame.Surface, ox: int = 0, oy: int = 0):
        r = self.rect.move(ox, oy)
        color = (255, 255, 255) if self.hit_flash > 0 else self.color
        pygame.draw.rect(surf, color, r)
        eye_y = r.centery - 4
        pygame.draw.rect(surf, COLOR_BG, (r.left + 8, eye_y, 6, 6))
        pygame.draw.rect(surf, COLOR_BG, (r.right - 14, eye_y, 6, 6))


class EnemyGrid:
    def __init__(self, wave: int):
        # Build a grid of enemies with types based on probabilities
        pad_x, pad_y = 60, 60
        start_x = 60
        start_y = 70
        spacing_x = 70
        spacing_y = 50
        self.enemies: List[Enemy] = []
        for row in range(ENEMY_ROWS):
            for col in range(ENEMY_COLS):
                p = random.random()
                if p < 0.05:
                    et = 'shooter'
                elif p < 0.30:
                    et = 'tough'
                else:
                    et = 'common'
                x = start_x + col * spacing_x
                y = start_y + row * spacing_y
                self.enemies.append(Enemy(x, y, et, row))
        # Movement
        self.dir = 1
        self.speed = ENEMY_START_SPEED * (WAVE_SPEED_MULT ** (wave - 1))
        self.descend_pending = 0
        self.time_since_shot = 0.0
        self.fire_rate = ENEMY_FIRE_RATE * (WAVE_FIRE_MULT ** (wave - 1))

    def alive(self) -> int:
        return sum(1 for e in self.enemies if e is not None)

    def bounds(self) -> pygame.Rect:
        rects = [e.rect for e in self.enemies if e is not None]
        if not rects:
            return pygame.Rect(0, 0, 0, 0)
        left = min(r.left for r in rects)
        right = max(r.right for r in rects)
        top = min(r.top for r in rects)
        bottom = max(r.bottom for r in rects)
        return pygame.Rect(left, top, right - left, bottom - top)

    def update(self, dt: float):
        # Horizontal march
        accel = (1.0 + 0.6 * (1.0 - self.alive() / (ENEMY_ROWS * ENEMY_COLS)))
        dx = int(self.dir * self.speed * accel * dt)
        for e in self.enemies:
            if e is not None:
                e.rect.x += dx
                if e.hit_flash > 0:
                    e.hit_flash -= dt
        # Edge detection -> descend and reverse
        b = self.bounds()
        hit_edge = (b.left <= 20 and self.dir < 0) or (b.right >= WIDTH - 20 and self.dir > 0)
        if hit_edge:
            self.dir *= -1
            for e in self.enemies:
                if e is not None:
                    e.rect.y += ENEMY_STEP_DOWN

    def try_enemy_shot(self, bullets: List[Bullet], max_enemy_bullets: int, sound: SoundManager):
        # Limit number of enemy bullets
        active_enemy_bullets = sum(1 for b in bullets if not b.is_player)
        if active_enemy_bullets >= max_enemy_bullets or self.alive() == 0:
            return
        # Shooting probability per second -> scale with dt by caller controlling cadence
        # Choose a random column, then the bottom-most enemy in that column
        cols = {}
        for e in self.enemies:
            if e is None:
                continue
            col = (e.rect.centerx // 70)  # rough columns by spacing
            if col not in cols or e.rect.bottom > cols[col].rect.bottom:
                cols[col] = e
        if not cols:
            return
        if random.random() < self.fire_rate / FPS:
            shooter = random.choice(list(cols.values()))
            bx = shooter.rect.centerx
            by = shooter.rect.bottom + 6
            bullet = Bullet(bx, by, ENEMY_BULLET_SPEED, 1, False)
            bullets.append(bullet)
            sound.play("enemy_shoot")

    def draw(self, surf: pygame.Surface, ox: int = 0, oy: int = 0):
        for e in self.enemies:
            if e is not None:
                e.draw(surf, ox, oy)


class Boss:
    def __init__(self, y: int):
        self.rect = pygame.Rect(-80, y, 60, 24)
        self.speed = BOSS_SPEED
        self.alive = True

    def update(self, dt: float):
        self.rect.x += int(self.speed * dt)
        if self.rect.left > WIDTH + 40:
            self.alive = False

    def draw(self, surf: pygame.Surface, ox: int = 0, oy: int = 0):
        r = self.rect.move(ox, oy)
        pygame.draw.rect(surf, COLOR_BOSS, r, border_radius=6)
        pygame.draw.rect(surf, COLOR_BG, r.inflate(-30, -12))


class ShieldPiece:
    def __init__(self, x: int, y: int):
        self.rect = pygame.Rect(x, y, SHIELD_SEG_SIZE, SHIELD_SEG_SIZE)
        self.hp = SHIELD_SEG_HP

    def hit(self):
        self.hp -= 1
        return self.hp <= 0

    def draw(self, surf: pygame.Surface, ox: int = 0, oy: int = 0):
        color = COLOR_SHIELD if self.hp >= 2 else COLOR_SHIELD_DMG
        pygame.draw.rect(surf, color, self.rect.move(ox, oy))


class Shields:
    def __init__(self):
        self.pieces: List[ShieldPiece] = []
        margin_x = 80
        spacing = (WIDTH - 2 * margin_x) // (SHIELD_COUNT - 1)
        base_y = HEIGHT - 180
        for i in range(SHIELD_COUNT):
            left = margin_x + i * spacing - (SHIELD_SEG_COLS * SHIELD_SEG_SIZE) // 2
            top = base_y
            for r in range(SHIELD_SEG_ROWS):
                for c in range(SHIELD_SEG_COLS):
                    # Carve a small arch by skipping corners in the bottom row
                    if r == SHIELD_SEG_ROWS - 1 and (c == 0 or c == SHIELD_SEG_COLS - 1):
                        continue
                    x = left + c * SHIELD_SEG_SIZE
                    y = top + r * SHIELD_SEG_SIZE
                    self.pieces.append(ShieldPiece(x, y))

    def collide_bullet(self, b: Bullet) -> bool:
        for p in list(self.pieces):
            if p.rect.colliderect(b.rect):
                if p.hit():
                    self.pieces.remove(p)
                return True
        return False

    def draw(self, surf: pygame.Surface, ox: int = 0, oy: int = 0):
        for p in self.pieces:
            p.draw(surf, ox, oy)


# ============================
# GAME
# ============================
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 26)
        self.bigfont = pygame.font.SysFont(None, 48)
        self.sound = SoundManager(ENABLE_SOUND)

        # State
        self.scene = SCENE_MENU
        self.player = Player(WIDTH // 2, HEIGHT - 30)
        self.bullets: List[Bullet] = []
        self.particles: List[Particle] = []
        self.grid: Optional[EnemyGrid] = None
        self.enemy_bullets: List[Bullet] = []  # same list as bullets but kept for clarity
        self.shields: Shields = Shields()
        self.wave = 1
        self.score = 0
        self.combo_mult = 0.0
        self.last_kill_time = -999.0
        self.shake_timer = 0.0
        self.shake_mag = 0.0
        self.boss: Optional[Boss] = None
        self.next_boss_time = self._rand_boss_timer()
        self.highscores = load_highscores()
        self.just_made_highscore = False
        self.debug_god = False

        self._start_new_game(reset_scores=False)

    def _rand_boss_timer(self) -> float:
        return random.uniform(BOSS_CD_MIN, BOSS_CD_MAX)

    def _start_new_game(self, reset_scores: bool = True):
        self.player = Player(WIDTH // 2, HEIGHT - 30)
        self.bullets = []
        self.enemy_bullets = []
        self.particles = []
        self.shields = Shields()
        self.wave = 1
        if reset_scores:
            self.score = 0
        self.combo_mult = 0.0
        self.last_kill_time = -999.0
        self.grid = EnemyGrid(self.wave)
        self.boss = None
        self.next_boss_time = self._rand_boss_timer()
        self.just_made_highscore = False

    def _next_wave(self):
        self.wave += 1
        self.grid = EnemyGrid(self.wave)
        self.bullets = []
        self.enemy_bullets = []
        # Keep shields between waves for a classic feel

    # ============================
    # MAIN LOOP
    # ============================
    def run(self):
        global GODMODE
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.scene == SCENE_PLAYING:
                            self.scene = SCENE_PAUSED
                        elif self.scene in (SCENE_PAUSED, SCENE_MENU):
                            running = False
                        elif self.scene == SCENE_GAME_OVER:
                            self.scene = SCENE_MENU
                    if event.key == pygame.K_RETURN:
                        if self.scene == SCENE_MENU:
                            self._start_new_game(reset_scores=True)
                            self.scene = SCENE_PLAYING
                        elif self.scene == SCENE_GAME_OVER:
                            self.scene = SCENE_MENU
                        elif self.scene == SCENE_PAUSED:
                            self.scene = SCENE_PLAYING
                    if event.key == pygame.K_p:
                        if self.scene == SCENE_PLAYING:
                            self.scene = SCENE_PAUSED
                        elif self.scene == SCENE_PAUSED:
                            self.scene = SCENE_PLAYING
                    if event.key == pygame.K_s and self.scene == SCENE_MENU:
                        # Toggle sound from menu
                        self.sound.enabled = not self.sound.enabled
                    # Debug keys
                    if event.key == pygame.K_F1:
                        if self.grid:
                            b = self.grid.bounds()
                            print(f"Wave {self.wave} | Enemies {self.grid.alive()} | Speed {self.grid.speed:.1f} | Fire {self.grid.fire_rate:.2f} | Bounds {b}")
                    if event.key == pygame.K_F2:
                        GODMODE = not GODMODE
                        self.debug_god = GODMODE
                        print("GODMODE:", GODMODE)
                    if event.key == pygame.K_F3 and self.scene == SCENE_PLAYING:
                        # Skip wave
                        self.grid.enemies = []

            if self.scene == SCENE_MENU:
                self.update_menu(dt)
            elif self.scene == SCENE_PLAYING:
                self.update_game(dt)
            elif self.scene == SCENE_PAUSED:
                self.update_paused(dt)
            elif self.scene == SCENE_GAME_OVER:
                self.update_game_over(dt)

            self.draw()
        pygame.quit()

    # ============================
    # UPDATE SCENES
    # ============================
    def update_menu(self, dt: float):
        pass  # nothing to update continuously

    def update_paused(self, dt: float):
        pass

    def update_game_over(self, dt: float):
        pass

    def update_game(self, dt: float):
        keys = pygame.key.get_pressed()
        # 1) Input -> player update
        self.player.update(dt, keys)
        if keys[pygame.K_SPACE] and self.player.can_shoot(sum(1 for b in self.bullets if b.is_player)):
            self.bullets.append(self.player.shoot())
            self.sound.play("shoot")

        # 2) Spawns: boss timer, enemy shots
        if self.grid is not None:
            self.grid.update(dt)
            self.grid.try_enemy_shot(self.bullets, ENEMY_MAX_BULLETS, self.sound)
        # Boss logic
        self.next_boss_time -= dt
        if self.next_boss_time <= 0.0 and self.boss is None and self.scene == SCENE_PLAYING:
            self.boss = Boss(y=50)
            self.next_boss_time = self._rand_boss_timer()
        if self.boss is not None:
            self.boss.update(dt)
            if not self.boss.alive:
                self.boss = None

        # 3) Movement -> bullets
        for b in list(self.bullets):
            b.update(dt)
            if not b.alive:
                self.bullets.remove(b)

        # 4) Collisions
        self.handle_collisions(dt)

        # 5) Cleanup already handled inline

        # 6) Effects
        if self.shake_timer > 0:
            self.shake_timer -= dt
            self.shake_mag = max(0.0, self.shake_mag - 60 * dt)
        if ENABLE_PARTICLES:
            for p in list(self.particles):
                p.update(dt)
                if p.life <= 0:
                    self.particles.remove(p)

        # 7) End-of-wave check
        if self.grid and self.grid.alive() == 0:
            self._next_wave()

    def handle_collisions(self, dt: float):
        # Player bullets vs enemies / shields / boss
        for b in list(self.bullets):
            if not b.is_player:
                continue
            # Shields
            if self.shields and self.shields.collide_bullet(b):
                self.bullets.remove(b)
                continue
            # Boss
            if self.boss and b.rect.colliderect(self.boss.rect):
                self.score_add(100)
                self.spawn_hit_effect(self.boss.rect.centerx, self.boss.rect.centery, COLOR_BOSS)
                self.boss.alive = False
                self.boss = None
                self.bullets.remove(b)
                self.sound.play("explosion")
                continue
            # Enemies
            if self.grid is None:
                continue
            hit = False
            for e in list(self.grid.enemies):
                if e is None:
                    continue
                if e.rect.colliderect(b.rect):
                    dead = e.take_damage(b.damage)
                    self.spawn_hit_effect(b.rect.centerx, b.rect.centery, e.color)
                    self.bullets.remove(b)
                    hit = True
                    if dead:
                        self.grid.enemies.remove(e)
                        self.score_add(e.points)
                        self.sound.play("explosion")
                    break
            if hit:
                continue

        # Enemy bullets vs player / shields
        for b in list(self.bullets):
            if b.is_player:
                continue
            # Shields
            if self.shields and self.shields.collide_bullet(b):
                self.bullets.remove(b)
                continue
            # Player
            if b.rect.colliderect(self.player.rect):
                if self.player.hit():
                    self.shake(10)
                self.bullets.remove(b)
                if self.player.lives <= 0 and not GODMODE:
                    self.game_over()
                continue

        # Enemies reaching bottom or colliding with player
        if self.grid:
            for e in self.grid.enemies:
                if e is None:
                    continue
                if e.rect.colliderect(self.player.rect) or e.rect.bottom >= HEIGHT - 50:
                    if self.player.hit():
                        self.shake(12)
                    # Soft reset enemy position: start a new wave (penalty)
                    self.grid = EnemyGrid(max(1, self.wave))
                    self.bullets = []
                    self.player.reset_position()
                    if self.player.lives <= 0 and not GODMODE:
                        self.game_over()
                    break

    def spawn_hit_effect(self, x: int, y: int, color: Tuple[int, int, int]):
        if not ENABLE_PARTICLES:
            return
        for _ in range(random.randint(6, 12)):
            self.particles.append(Particle(x, y))

    def shake(self, amount: float):
        self.shake_timer = 0.28
        self.shake_mag = max(self.shake_mag, amount)

    def score_add(self, base_points: int):
        t = time.time()
        if t - self.last_kill_time <= COMBO_WINDOW:
            self.combo_mult += COMBO_STEP
        else:
            self.combo_mult = 0.0
        self.last_kill_time = t
        pts = int(round(base_points * (1.0 + self.combo_mult)))
        self.score += pts

    def game_over(self):
        # Update highscores (top-5)
        top = self.highscores.get("top", [])
        top.append(self.score)
        top = list(sorted(top, reverse=True))[:5]
        self.just_made_highscore = self.score in top and self.score not in self.highscores.get("top", [])
        save_highscores(top)
        self.highscores["top"] = top
        if self.just_made_highscore:
            self.sound.play("highscore")
        self.scene = SCENE_GAME_OVER

    # ============================
    # RENDERING
    # ============================
    def draw(self):
        self.screen.fill(COLOR_BG)
        ox = oy = 0
        if self.shake_timer > 0:
            ox = random.randint(int(-self.shake_mag), int(self.shake_mag))
            oy = random.randint(int(-self.shake_mag), int(self.shake_mag))
        if self.scene in (SCENE_PLAYING, SCENE_PAUSED):
            self.draw_game(ox, oy)
        if self.scene == SCENE_MENU:
            self.draw_menu()
        elif self.scene == SCENE_PAUSED:
            self.draw_paused()
        elif self.scene == SCENE_GAME_OVER:
            self.draw_game_over()

        pygame.display.flip()

    def draw_game(self, ox: int, oy: int):
        # Shields
        if self.shields:
            self.shields.draw(self.screen, ox, oy)
        # Enemies
        if self.grid:
            self.grid.draw(self.screen, ox, oy)
        # Boss
        if self.boss:
            self.boss.draw(self.screen, ox, oy)
        # Bullets
        for b in self.bullets:
            b.draw(self.screen, ox, oy)
        # Player
        self.player.draw(self.screen, ox, oy)
        # Particles
        if ENABLE_PARTICLES:
            for p in self.particles:
                p.draw(self.screen, COLOR_HIGHLIGHT, ox, oy)
        # HUD
        self.draw_hud()

    def draw_hud(self):
        pad = 8
        # Score and highscore
        txt = self.font.render(f"Score: {self.score}", True, COLOR_UI)
        self.screen.blit(txt, (pad, pad))
        high = (self.highscores.get("top") or [0])[0] if self.highscores.get("top") else 0
        txt2 = self.font.render(f"High: {high}", True, COLOR_UI)
        self.screen.blit(txt2, (pad, pad + 22))
        # Wave
        txt3 = self.font.render(f"Wave: {self.wave}", True, COLOR_UI)
        self.screen.blit(txt3, (WIDTH//2 - 40, pad))
        # Lives as hearts (triangles)
        for i in range(self.player.lives):
            cx = WIDTH - 20 - i * 24
            cy = pad + 12
            heart = [(cx, cy-6), (cx-8, cy+6), (cx+8, cy+6)]
            pygame.draw.polygon(self.screen, (255, 100, 120), heart)
        # Debug god mode banner
        if self.debug_god:
            g = self.font.render("GODMODE", True, (255, 200, 200))
            self.screen.blit(g, (WIDTH - 120, pad + 22))

    def draw_menu(self):
        title = self.bigfont.render(TITLE, True, COLOR_UI)
        self.screen.blit(title, (WIDTH//2 - title.get_width()//2, 120))
        press = self.font.render("Press Enter to Start", True, COLOR_HIGHLIGHT)
        self.screen.blit(press, (WIDTH//2 - press.get_width()//2, 220))

        tips = [
            "Controls:",
            "Left/Right or A/D — Move",
            "Space — Shoot",
            "P or Esc — Pause",
            "Esc in Menu — Quit",
            "S — Toggle Sound (menu)",
        ]
        for i, t in enumerate(tips):
            s = self.font.render(t, True, COLOR_DIM)
            self.screen.blit(s, (WIDTH//2 - 180, 280 + i*22))

        # Highscores list
        top = self.highscores.get("top") or []
        hs_title = self.font.render("Top-5 Highscores:", True, COLOR_UI)
        self.screen.blit(hs_title, (WIDTH//2 - hs_title.get_width()//2, 280 - 40))
        for i, sc in enumerate(top[:5]):
            line = self.font.render(f"{i+1}. {sc}", True, COLOR_UI)
            self.screen.blit(line, (WIDTH//2 - 60, 280 - 18 + i*22))

    def draw_paused(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))
        p = self.bigfont.render("Paused", True, COLOR_UI)
        self.screen.blit(p, (WIDTH//2 - p.get_width()//2, HEIGHT//2 - 40))
        t = self.font.render("Press P or Enter to continue", True, COLOR_HIGHLIGHT)
        self.screen.blit(t, (WIDTH//2 - t.get_width()//2, HEIGHT//2 + 10))

    def draw_game_over(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))
        p = self.bigfont.render("Game Over", True, COLOR_UI)
        self.screen.blit(p, (WIDTH//2 - p.get_width()//2, HEIGHT//2 - 100))
        s = self.font.render(f"Your score: {self.score}", True, COLOR_UI)
        self.screen.blit(s, (WIDTH//2 - s.get_width()//2, HEIGHT//2 - 50))
        if self.just_made_highscore:
            n = self.font.render("New Highscore!", True, COLOR_HIGHLIGHT)
            self.screen.blit(n, (WIDTH//2 - n.get_width()//2, HEIGHT//2 - 20))
        hint = self.font.render("Press Enter for Menu", True, COLOR_DIM)
        self.screen.blit(hint, (WIDTH//2 - hint.get_width()//2, HEIGHT//2 + 20))


if __name__ == "__main__":
    Game().run()