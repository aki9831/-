from pathlib import Path
import json
import math
import random
import sys
from array import array

import pygame


# ============================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================

pygame.init()
try:
    pygame.mixer.init(frequency=44100, size=-16, channels=1)
except pygame.error:
    pass

WIDTH, HEIGHT, FPS = 1100, 650, 60
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Shadow Parkour: Nightfall")
clock = pygame.time.Clock()

BASE_DIR = Path(__file__).resolve().parent
TEXTURES_DIR = BASE_DIR / "textures"
SOUNDS_DIR = BASE_DIR / "sounds"
SAVE_FILE = BASE_DIR / "shadow_parkour_save.json"

TEXTURES_DIR.mkdir(exist_ok=True)
SOUNDS_DIR.mkdir(exist_ok=True)

# Цвета
WHITE = (245, 245, 245)
BLACK = (8, 10, 18)
GRAY = (150, 160, 180)
DARK_GRAY = (35, 40, 58)
SKY = (18, 23, 48)
GREEN = (70, 190, 105)
RED = (220, 65, 75)
PURPLE = (155, 80, 200)
GOLD = (255, 210, 70)
BLUE = (75, 150, 240)
ORANGE = (240, 135, 55)
CYAN = (75, 220, 220)

# Шрифты
font_title = pygame.font.SysFont("arial", 72, bold=True)
font_big = pygame.font.SysFont("arial", 44, bold=True)
font_medium = pygame.font.SysFont("arial", 28, bold=True)
font_small = pygame.font.SysFont("arial", 20)
font_tiny = pygame.font.SysFont("arial", 15)

DIFFICULTIES = {
    "Легко": {
        "player_speed": 285,
        "jump_power": 800,
        "enemy_speed": 65,
        "enemy_damage": 8,
        "player_health": 150,
        "enemy_scale": 0.85,
    },
    "Средне": {
        "player_speed": 315,
        "jump_power": 850,
        "enemy_speed": 88,
        "enemy_damage": 14,
        "player_health": 100,
        "enemy_scale": 1.0,
    },
    "Сложно": {
        "player_speed": 345,
        "jump_power": 900,
        "enemy_speed": 112,
        "enemy_damage": 22,
        "player_health": 75,
        "enemy_scale": 1.25,
    },
}


# ============================================================
# ЗАГЛУШКИ И ЗВУК
# ============================================================

def fallback_surface(size, color, label=""):
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill(color)
    pygame.draw.rect(surface, BLACK, surface.get_rect(), 3)

    for x in range(-size[1], size[0], 16):
        pygame.draw.line(
            surface,
            (255, 255, 255, 45),
            (x, 0),
            (x + size[1], size[1]),
            2,
        )

    if label:
        text = font_tiny.render(label, True, WHITE)
        surface.blit(text, text.get_rect(center=surface.get_rect().center))

    return surface


IMAGE_CACHE = {}


def load_sheet(filename, frame_size, color, label, frame_count=4):
    """
    Поддержка sprite-sheet: ряд кадров лежит горизонтально слева направо.
    Если файла нет или он битый — создаёт заглушку.
    """
    key = (filename, frame_size, color, label, frame_count)
    if key in IMAGE_CACHE:
        return IMAGE_CACHE[key]

    path = TEXTURES_DIR / filename
    frames = []

    try:
        image = pygame.image.load(str(path)).convert_alpha()
        for i in range(frame_count):
            rect = pygame.Rect(
                i * frame_size[0],
                0,
                frame_size[0],
                frame_size[1],
            )
            if rect.right <= image.get_width() and rect.bottom <= image.get_height():
                frame = image.subsurface(rect).copy()
                frame = pygame.transform.smoothscale(frame, frame_size)
                frames.append(frame)

        if not frames:
            raise pygame.error("sprite-sheet has no valid frames")

    except (pygame.error, FileNotFoundError, OSError):
        frames = [
            fallback_surface(frame_size, color, f"{label} {i + 1}")
            for i in range(frame_count)
        ]

    IMAGE_CACHE[key] = frames
    return frames


def load_image(filename, size, color, label):
    path = TEXTURES_DIR / filename
    try:
        image = pygame.image.load(str(path)).convert_alpha()
        return pygame.transform.smoothscale(image, size)
    except (pygame.error, FileNotFoundError, OSError):
        return fallback_surface(size, color, label)


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def save_best(value):
    try:
        SAVE_FILE.write_text(json.dumps({"best": int(value)}), encoding="utf-8")
    except OSError:
        pass


def load_best():
    try:
        data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        return int(data.get("best", 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


class SoundManager:
    """
    Если .wav/.ogg нет — генерирует короткий beep.
    Это позволяет игре работать без звуковой папки.
    """
    def __init__(self):
        self.sounds = {}
        for name, (frequency, duration) in {
    "jump": (520, .09),
    "dash": (180, .12),
    "hit": (90, .10),
    "coin": (880, .10),
    "hurt": (120, .16),
    "boss": (55, .35),
    "victory": (660, .35),
    "click": (300, .06),
}.items():
    self.sounds[name] = self.load_or_beep(
        name,
        frequency,
        duration,
    )
            self.sounds[name] = self._load_or_beep(name, frequency, duration)

        self.music = None
        try:
            music_path = SOUNDS_DIR / "music.ogg"
            if music_path.exists():
                pygame.mixer.music.load(str(music_path))
                self.music = music_path
        except (pygame.error, OSError):
            self.music = None

    def _load_or_beep(self, name, frequency, duration):
        path = SOUNDS_DIR / f"{name}.wav"
        if path.exists():
            try:
                return pygame.mixer.Sound(str(path))
            except pygame.error:
                pass

        path_ogg = SOUNDS_DIR / f"{name}.ogg"
        if path_ogg.exists():
            try:
                return pygame.mixer.Sound(str(path_ogg))
            except pygame.error:
                pass

        if not pygame.mixer.get_init():
            return None

        sample_rate = 44100
        samples = array("h")
        total_samples = int(sample_rate * duration)

        for i in range(total_samples):
            t = i / sample_rate
            env = 1.0 - (i / total_samples)
            wave = math.sin(2 * math.pi * frequency * t)
            value = int(12000 * env * wave)
            samples.append(value)

        try:
            return pygame.mixer.Sound(buffer=samples.tobytes())
        except (pygame.error, ValueError):
            return None

    def play(self, name):
        sound = self.sounds.get(name)
        if sound is None:
            return
        try:
            sound.play()
        except pygame.error:
            pass

    def start_music(self):
        if self.music is not None:
            try:
                pygame.mixer.music.play(-1)
            except pygame.error:
                pass


sound = SoundManager()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ
# ============================================================

class Particle:
    def __init__(self, x, y, color, life=0.5, speed=140, gravity=500):
        angle = random.uniform(0, math.tau)
        velocity = random.uniform(speed * 0.3, speed)
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * velocity
        self.vy = math.sin(angle) * velocity
        self.color = color
        self.life = self.max_life = life
        self.gravity = gravity
        self.size = random.randint(2, 5)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.life -= dt
        return self.life > 0

    def draw(self, camera_x):
        radius = max(1, int(self.size * self.life / self.max_life))
        pygame.draw.circle(
            screen,
            self.color,
            (int(self.x - camera_x), int(self.y)),
            radius,
        )


class FloatingText:
    def __init__(self, text, x, y, color=WHITE):
        self.text = str(text)
        self.x = x
        self.y = y
        self.color = color
        self.life = 1.0

    def update(self, dt):
        self.y -= 35 * dt
        self.life -= dt
        return self.life > 0

    def draw(self, camera_x):
        image = font_small.render(self.text, True, self.color)
        image.set_alpha(int(255 * clamp(self.life, 0, 1)))
        screen.blit(image, image.get_rect(center=(self.x - camera_x, self.y)))


class Button:
    def __init__(self, rect, text):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.hovered = False

    def update(self, mouse_position):
        self.hovered = self.rect.collidepoint(mouse_position)

    def draw(self):
        color = BLUE if self.hovered else DARK_GRAY

        pygame.draw.rect(
            screen,
            color,
            self.rect,
            border_radius=12,
        )
        pygame.draw.rect(
            screen,
            WHITE,
            self.rect,
            width=2,
            border_radius=12,
        )
        draw_text(
            self.text,
            font_medium,
            WHITE,
            self.rect.centerx,
            self.rect.centery,
        )


def draw_text(text, font, color, x, y, center=True):
    image = font.render(str(text), True, color)
    rect = image.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    screen.blit(image, rect)


# ============================================================
# ИГРОК
# ============================================================

class Player:
    def __init__(self, game):
        self.game = game
        self.width = 58
        self.height = 82

        self.rect = pygame.Rect(150, 350, self.width, self.height)
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

        self.vx = 0.0
        self.vy = 0.0
        self.direction = 1
        self.on_ground = False
        self.coyote_time = 0.0
        self.jump_buffer = 0.0
        self.double_jump = True

        self.health = 100
        self.max_health = 100
        self.invulnerability = 0.0
        self.attack_timer = 0.0
        self.attack_cooldown = 0.0
        self.dash_timer = 0.0
        self.dash_cooldown = 0.0

        self.animation_time = 0
        self.frame = 0

        self.frames_idle = load_sheet("player_idle.png", (58, 82), BLUE, "IDLE", 4)
        self.frames_run = load_sheet("player_run.png", (58, 82), GREEN, "RUN", 6)
        self.frames_jump = load_sheet("player_jump.png", (58, 82), ORANGE, "JUMP", 2)
        self.frames_attack = load_sheet("player_attack.png", (58, 82), RED, "ATTACK", 4)

    def reset(self, position):
        self.x = float(position[0])
        self.y = float(position[1])
        self.rect.topleft = position
        self.vx = 0.0
        self.vy = 0.0
        self.health = self.max_health
        self.invulnerability = 0.9
        self.double_jump = True
        self.attack_timer = 0.0
        self.attack_cooldown = 0.0
        self.dash_timer = 0.0
        self.dash_cooldown = 0.0

    def jump_action(self):
        difficulty = DIFFICULTIES[self.game.difficulty]
        if self.on_ground or self.coyote_time > 0:
            self.vy = -difficulty["jump_power"]
            self.on_ground = False
            self.coyote_time = 0.0
            sound.play("jump")
            self.game.burst(self.rect.centerx, self.rect.bottom, CYAN, 10)
            return

        if self.double_jump:
            self.vy = -difficulty["jump_power"] * 0.82
            self.double_jump = False
            self.game.burst(self.rect.centerx, self.rect.centery, ORANGE, 12)
            sound.play("jump")

    def attack(self):
        if self.attack_cooldown > 0:
            return

        self.attack_timer = 0.25
        self.attack_cooldown = 0.42

        hit_rect = pygame.Rect(
            self.rect.right if self.direction > 0 else self.rect.left - 70,
            self.rect.y + 15,
            70,
            52,
        )
        self.game.burst(hit_rect.centerx, hit_rect.centery, GOLD, 7, gravity=0)

        for enemy in self.game.enemies:
            if enemy.alive and hit_rect.colliderect(enemy.rect):
                enemy.take_damage(35)
                self.game.score += 25
                self.game.floating.append(
                    FloatingText("+25", enemy.rect.centerx, enemy.rect.y, GOLD)
                )

        if self.game.boss and self.game.boss.alive and hit_rect.colliderect(self.game.boss.rect):
            self.game.boss.take_damage(35)
            self.game.score += 25

    def dash(self):
        if self.dash_cooldown <= 0:
            self.dash_timer = 0.14
            self.dash_cooldown = 0.8
            self.vx = self.direction * 950
            self.invulnerability = max(self.invulnerability, 0.2)
            sound.play("dash")
            self.game.shake = max(self.game.shake, 5)
            self.game.burst(self.rect.centerx, self.rect.centery, BLUE, 18, gravity=0)

    def take_damage(self, amount):
        if self.invulnerability > 0:
            return

        self.health -= amount
        self.invulnerability = 0.55
        self.game.shake = max(self.game.shake, 8)
        sound.play("hurt")

        if self.health <= 0:
            self.game.respawn_player()

    def update(self, dt, keys):
        difficulty = DIFFICULTIES[self.game.difficulty]

        self.invulnerability = max(0, self.invulnerability - dt)
        self.attack_cooldown = max(0, self.attack_cooldown - dt)
        self.attack_timer = max(0, self.attack_timer - dt)
        self.dash_cooldown = max(0, self.dash_cooldown - dt)
        self.dash_timer = max(0, self.dash_timer - dt)
        self.coyote_time = max(0, self.coyote_time - dt)
        self.jump_buffer = max(0, self.jump_buffer - dt)

        left = keys[pygame.K_a] or keys[pygame.K_LEFT]
        right = keys[pygame.K_d] or keys[pygame.K_RIGHT]

        if self.dash_timer <= 0:
            if left:
                self.vx = -difficulty["player_speed"]
                self.direction = -1
            elif right:
                self.vx = difficulty["player_speed"]
                self.direction = 1
            else:
                self.vx = 0.0

        if self.jump_buffer > 0:
            self.jump_action()
            self.jump_buffer = 0.0

        if keys[pygame.K_f] or keys[pygame.K_j]:
            self.attack()

        self.vy += 1900 * dt

        old_bottom = self.rect.bottom
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rect.topleft = (int(self.x), int(self.y))
        self.on_ground = False

        for platform in self.game.platforms:
            if self.rect.colliderect(platform) and self.vy >= 0 and old_bottom <= platform.top + 8:
                self.rect.bottom = platform.top
                self.y = float(self.rect.y)
                self.vy = 0
                self.on_ground = True
                self.double_jump = True

        if not self.on_ground and old_bottom <= self.game.level_height:
            self.coyote_time = 0.1

        self.rect.left = max(0, self.rect.left)
        self.x = float(self.rect.x)

        for enemy in self.game.enemies:
            if enemy.alive and self.rect.colliderect(enemy.rect):
                self.take_damage(enemy.damage * dt)

        if self.game.boss and self.game.boss.alive and self.rect.colliderect(self.game.boss.rect):
            self.take_damage(self.game.boss.damage * dt)

        for hazard in self.game.hazards:
            if self.rect.colliderect(hazard):
                self.take_damage(35 * dt)

        if self.rect.top > self.game.level_height + 260:
            self.game.respawn_player()

        if self.attack_timer > 0:
            frames = self.frames_attack
            anim_speed = 12
        elif not self.on_ground:
            frames = self.frames_jump
            anim_speed = 5
        elif self.vx != 0:
            frames = self.frames_run
            anim_speed = 10
        else:
            frames = self.frames_idle
            anim_speed = 5

        self.animation_time += dt * anim_speed
        self.frame = int(self.animation_time) % len(frames)

    def draw(self, camera_x):
        if self.invulnerability > 0 and int(self.invulnerability * 18) % 2 == 0:
            return

        if self.attack_timer > 0:
            frames = self.frames_attack
        elif not self.on_ground:
            frames = self.frames_jump
        elif self.vx != 0:
            frames = self.frames_run
        else:
            frames = self.frames_idle

        image = frames[self.frame]
        if self.direction < 0:
            image = pygame.transform.flip(image, True, False)

        screen.blit(image, (self.rect.x - camera_x, self.rect.y))


# ============================================================
# ВРАГ
# ============================================================

class Enemy:
    def __init__(self, game, x, y, enemy_type="zombie"):
        self.game = game
        self.enemy_type = enemy_type
        self.width = 58
        self.height = 78
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.x = float(x)
        self.y = float(y)

        if enemy_type == "zombie":
            self.max_health = self.health = 60 * DIFFICULTIES[game.difficulty]["enemy_scale"]
            self.damage = DIFFICULTIES[game.difficulty]["enemy_damage"]
            self.speed = DIFFICULTIES[game.difficulty]["enemy_speed"]
            self.frames = load_sheet("zombie_sheet.png", (58, 78), GREEN, "ZOMBIE", 4)
        elif enemy_type == "vampire":
            self.max_health = self.health = 48 * DIFFICULTIES[game.difficulty]["enemy_scale"]
            self.damage = DIFFICULTIES[game.difficulty]["enemy_damage"] * 1.35
            self.speed = DIFFICULTIES[game.difficulty]["enemy_speed"] * 1.15
            self.frames = load_sheet("vampire_sheet.png", (58, 78), PURPLE, "VAMPIRE", 4)
        else:
            self.max_health = self.health = 110 * DIFFICULTIES[game.difficulty]["enemy_scale"]
            self.damage = DIFFICULTIES[game.difficulty]["enemy_damage"] * 1.6
            self.speed = DIFFICULTIES[game.difficulty]["enemy_speed"] * 0.8
            self.frames = load_sheet("brute_sheet.png", (58, 78), ORANGE, "BRUTE", 4)

        self.alive = True
        self.direction = -1
        self.animation_time = 0
        self.frame = 0

    def take_damage(self, amount):
        if not self.alive:
            return

        self.health -= amount
        self.game.burst(self.rect.centerx, self.rect.centery, RED, 7)

        if self.health <= 0:
            self.alive = False
            self.game.score += 150
            self.game.floating.append(
                FloatingText("+150", self.rect.centerx, self.rect.y, GOLD)
            )
            self.game.burst(self.rect.centerx, self.rect.centery, PURPLE, 22)

    def update(self, dt):
        if not self.alive:
            return

        distance = self.game.player.rect.centerx - self.rect.centerx
        if abs(distance) < 520:
            if distance > 8:
                self.direction = 1
                self.x += self.speed * dt
            elif distance < -8:
                self.direction = -1
                self.x -= self.speed * dt

        self.rect.x = int(self.x)

        old_bottom = self.rect.bottom
        self.y += 1900 * dt
        self.rect.y = int(self.y)

        for platform in self.game.platforms:
            if self.rect.colliderect(platform) and old_bottom <= platform.top + 12:
                self.rect.bottom = platform.top
                self.y = float(self.rect.y)

        self.animation_time += dt * 7
        self.frame = int(self.animation_time) % len(self.frames)

    def draw(self, camera_x):
        if not self.alive:
            return

        image = self.frames[self.frame]
        if self.direction < 0:
            image = pygame.transform.flip(image, True, False)

        screen.blit(image, (self.rect.x - camera_x, self.rect.y))

        bar = pygame.Rect(self.rect.x - camera_x, self.rect.y - 12, self.width, 7)
        pygame.draw.rect(screen, BLACK, bar)
        pygame.draw.rect(
            screen,
            RED,
            (
                bar.x,
                bar.y,
                int(bar.width * max(self.health, 0) / self.max_health),
                bar.height,
            ),
        )


# ============================================================
# БОСС
# ============================================================

class Boss(Enemy):
    def __init__(self, game, x, y):
        self.game = game
        self.width = 120
        self.height = 140
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.x = float(x)
        self.y = float(y)
        self.max_health = self.health = 880 * DIFFICULTIES[game.difficulty]["enemy_scale"]
        self.damage = DIFFICULTIES[game.difficulty]["enemy_damage"] * 2.2
        self.speed = 68
        self.alive = True
        self.direction = -1
        self.phase = 1
        self.rage = False
        self.cooldown = 1.2
        self.animation_time = 0
        self.frame = 0
        self.frames = load_sheet("boss_sheet.png", (120, 140), RED, "BOSS", 4)

    def take_damage(self, amount):
        if not self.alive:
            return

        self.health -= amount
        self.game.burst(self.rect.centerx, self.rect.centery, RED, 12)
        sound.play("hit")

        if self.health <= self.max_health * 0.5 and self.phase == 1:
            self.phase = 2
            self.rage = True
            sound.play("boss")
            self.game.floating.append(
                FloatingText("БЕЗДНА ПРОСЫПАЕТСЯ!", self.rect.centerx, self.rect.y - 25, RED)
            )

        if self.health <= 0:
            self.alive = False
            self.game.score += 1000
            self.game.floating.append(FloatingText("+1000", self.rect.centerx, self.rect.y, GOLD))
            self.game.burst(self.rect.centerx, self.rect.centery, PURPLE, 30)
            sound.play("victory")

    def update(self, dt):
        if not self.alive:
            return

        player = self.game.player
        distance = player.rect.centerx - self.rect.centerx
        self.direction = 1 if distance > 0 else -1

        if abs(distance) < 900:
            self.x += self.direction * self.speed * (1.45 if self.rage else 1.0) * dt
            self.rect.x = int(self.x)

        self.cooldown -= dt
        if self.cooldown <= 0 and abs(distance) < 850:
            self.cooldown = 0.75 if self.rage else 1.3
            self.game.projectiles.append(
                Projectile(
                    self.rect.centerx,
                    self.rect.centery,
                    player.rect.centerx,
                    player.rect.centery,
                    RED,
                    18,
                    260,
                )
            )
            self.game.burst(self.rect.centerx, self.rect.centery, RED, 9, gravity=0)
            sound.play("boss")

        self.animation_time += dt * (10 if self.rage else 5)
        self.frame = int(self.animation_time) % len(self.frames)

    def draw(self, camera_x):
        if not self.alive:
            return

        image = self.frames[self.frame]
        if self.direction < 0:
            image = pygame.transform.flip(image, True, False)

        screen.blit(image, (self.rect.x - camera_x, self.rect.y))

        # Полоса здоровья босса
        bar = pygame.Rect(240, 18, 620, 20)
        pygame.draw.rect(screen, BLACK, bar)
        health_width = int(bar.width * max(self.health, 0) / self.max_health)
        pygame.draw.rect(
            screen,
            RED if self.rage else PURPLE,
            (bar.x, bar.y, health_width, bar.height),
        )
        pygame.draw.rect(screen, WHITE, bar, 2)

        draw_text("ВЛАДЫКА БЕЗДНЫ", font_small, WHITE, WIDTH // 2, 50)


# ============================================================
# СНАРЯД
# ============================================================

class Projectile:
    def __init__(self, x, y, target_x, target_y, color, damage, speed):
        self.x = x
        self.y = y
        self.color = color
        self.damage = damage
        self.speed = speed
        self.life = 4.0

        dx = target_x - x
        dy = target_y - y
        length = max(1.0, math.hypot(dx, dy))
        self.vx = (dx / length) * speed
        self.vy = (dy / length) * speed

    def update(self, dt, game):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt

        rect = pygame.Rect(int(self.x - 10), int(self.y - 10), 20, 20)
        if rect.colliderect(game.player.rect):
            game.player.take_damage(self.damage)
            return False

        return (
            self.life > 0
            and -50 < self.x < game.level_width + 50
            and -50 < self.y < HEIGHT + 100
        )

    def draw(self, camera_x):
        pygame.draw.circle(screen, self.color, (int(self.x - camera_x), int(self.y)), 10)
        pygame.draw.circle(screen, WHITE, (int(self.x - camera_x), int(self.y)), 4)


# ============================================================
# НОВЫЙ ПЛАТФОРМЕР
# ============================================================

class MovingPlatform:
    def __init__(self, x, y, width, height, distance, speed):
        self.rect = pygame.Rect(x, y, width, height)
        self.start_x = float(x)
        self.distance = distance
        self.speed = speed
        self.time = random.random() * 5.0

    def update(self, dt):
        self.time += dt * self.speed
        self.rect.x = int(self.start_x + math.sin(self.time) * self.distance)


# ============================================================
# ИГРА
# ============================================================

class Game:
    def __init__(self):
        self.state = "menu"
        self.difficulty = "Средне"

        self.level_width = 4700
        self.level_height = 600

        self.camera_x = 0
        self.score = 0.0
        self.coins = 0
        self.best_score = load_best()
        self.checkpoint_position = (150, 350)

        self.time = 0.0
        self.shake = 0.0

        self.platforms = []
        self.hazards = []
        self.checkpoints = []
        self.coin_rects = []
        self.enemies = []
        self.projectiles = []
        self.particles = []
        self.floating = []
        self.moving_platforms = []

        self.player = Player(self)
        self.boss = None

        self.menu_buttons = [
            Button((400, 270, 300, 58), "Начать игру"),
            Button((400, 340, 300, 58), "Настройки"),
            Button((400, 410, 300, 58), "Выход"),
        ]

        self.settings_buttons = [
            Button((400, 270, 300, 58), "Сложность"),
            Button((400, 340, 300, 58), "Назад"),
        ]

        self.create_level()

    def create_level(self):
        self.platforms = [
            pygame.Rect(0, 540, 700, 110),
            pygame.Rect(850, 540, 550, 110),
            pygame.Rect(1550, 540, 650, 110),
            pygame.Rect(2350, 540, 550, 110),
            pygame.Rect(3050, 540, 550, 110),
            pygame.Rect(3750, 540, 950, 110),

            pygame.Rect(430, 430, 190, 28),
            pygame.Rect(970, 390, 190, 28),
            pygame.Rect(1250, 300, 180, 28),
            pygame.Rect(1720, 410, 220, 28),
            pygame.Rect(2050, 320, 190, 28),
            pygame.Rect(2500, 420, 220, 28),
            pygame.Rect(2800, 300, 180, 28),
            pygame.Rect(3200, 410, 220, 28),
            pygame.Rect(3500, 300, 180, 28),
            pygame.Rect(3950, 390, 220, 28),
            pygame.Rect(4300, 320, 250, 28),
        ]

        self.moving_platforms = [
            MovingPlatform(710, 470, 130, 25, 75, 1.5),
            MovingPlatform(2200, 440, 130, 25, 120, 1.2),
            MovingPlatform(2910, 450, 120, 25, 90, 1.8),
        ]
        self.platforms.extend([p.rect for p in self.moving_platforms])

        self.hazards = [
            pygame.Rect(700, 615, 150, 35),
            pygame.Rect(1400, 615, 150, 35),
            pygame.Rect(2200, 615, 150, 35),
            pygame.Rect(2900, 615, 150, 35),
            pygame.Rect(3600, 615, 150, 35),
        ]

        self.checkpoints = [
            pygame.Rect(1350, 490, 35, 50),
            pygame.Rect(2700, 490, 35, 50),
            pygame.Rect(3600, 490, 35, 50),
        ]

        self.coin_rects = [
            pygame.Rect(470, 380, 28, 28),
            pygame.Rect(570, 380, 28, 28),
            pygame.Rect(1010, 340, 28, 28),
            pygame.Rect(1290, 250, 28, 28),
            pygame.Rect(1760, 360, 28, 28),
            pygame.Rect(2100, 270, 28, 28),
            pygame.Rect(2540, 370, 28, 28),
            pygame.Rect(2840, 250, 28, 28),
            pygame.Rect(3240, 360, 28, 28),
            pygame.Rect(3540, 250, 28, 28),
            pygame.Rect(3990, 340, 28, 28),
            pygame.Rect(4370, 260, 28, 28),
        ]

        self.enemies = [
            Enemy(self, 570, 462, "zombie"),
            Enemy(self, 1080, 312, "vampire"),
            Enemy(self, 1250, 222, "zombie"),
            Enemy(self, 1800, 332, "vampire"),
            Enemy(self, 2150, 242, "brute"),
            Enemy(self, 2600, 342, "vampire"),
            Enemy(self, 3280, 332, "zombie"),
            Enemy(self, 3550, 222, "brute"),
            Enemy(self, 3980, 312, "zombie"),
        ]

        self.projectiles = []
        self.boss = Boss(self, 4300, 180)

    def burst(self, x, y, color, count=8, gravity=500):
        for _ in range(count):
            self.particles.append(
                Particle(
                    x,
                    y,
                    color,
                    life=random.uniform(0.25, 0.65),
                    speed=random.uniform(60, 180),
                    gravity=gravity,
                )
            )

    def start_game(self):
        self.state = "playing"
        self.score = 0.0
        self.coins = 0
        self.camera_x = 0
        self.checkpoint_position = (150, 350)

        self.player.max_health = DIFFICULTIES[self.difficulty]["player_health"]
        self.player.reset(self.checkpoint_position)
        self.projectiles = []
        self.create_level()
        sound.start_music()

    def respawn_player(self):
        self.player.reset(self.checkpoint_position)
        self.burst(self.checkpoint_position[0], self.checkpoint_position[1], RED, 15)

    def update_checkpoint(self):
        for checkpoint in self.checkpoints:
            if self.player.rect.colliderect(checkpoint) and checkpoint.x > self.checkpoint_position[0]:
                self.checkpoint_position = (checkpoint.x, checkpoint.y - self.player.height)
                self.score += 200
                self.floating.append(FloatingText("ЧЕКПОИНТ +200", checkpoint.x, checkpoint.y - 25, GOLD))
                self.burst(checkpoint.centerx, checkpoint.centery, GOLD, 18)

    def collect_coins(self):
        remaining = []
        for coin in self.coin_rects:
            if self.player.rect.colliderect(coin):
                self.coins += 1
                self.score += 100
                sound.play("coin")
                self.floating.append(FloatingText("+100", coin.centerx, coin.y, GOLD))
                self.burst(coin.centerx, coin.centery, GOLD, 12, gravity=0)
            else:
                remaining.append(coin)
        self.coin_rects = remaining

    def update(self, dt):
        self.time += dt
        self.shake = max(0, self.shake - 20 * dt)

        self.particles = [p for p in self.particles if p.update(dt)]
        self.floating = [f for f in self.floating if f.update(dt)]

        if self.state != "playing":
            return

        for platform in self.moving_platforms:
            platform.update(dt)

        keys = pygame.key.get_pressed()
        self.player.update(dt, keys)

        for enemy in self.enemies:
            enemy.update(dt)

        if self.boss and self.boss.alive:
            self.boss.update(dt)

        self.projectiles = [p for p in self.projectiles if p.update(dt, self)]

        self.update_checkpoint()
        self.collect_coins()

        self.score += dt * 10

        self.camera_x = clamp(
            self.player.rect.centerx - WIDTH // 2,
            0,
            self.level_width - WIDTH,
        )

        end_condition = self.player.rect.x > 4450 and (not self.boss or not self.boss.alive)
        if end_condition:
            self.state = "victory"
            self.best_score = max(self.best_score, int(self.score))
            save_best(self.best_score)
            sound.play("victory")

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.state in ("playing", "paused", "settings", "victory"):
                    self.state = "menu"

            if self.state == "playing":
                if event.key == pygame.K_p:
                    self.state = "paused"
                elif event.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                    self.player.jump_buffer = 0.15
                elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                    self.player.dash()

            elif self.state == "paused":
                if event.key == pygame.K_p:
                    self.state = "playing"

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button != 1:
                return

            pos = event.pos

            if self.state == "menu":
                if self.menu_buttons[0].rect.collidepoint(pos):
                    self.start_game()
                    sound.play("click")
                elif self.menu_buttons[1].rect.collidepoint(pos):
                    self.state = "settings"
                    sound.play("click")
                elif self.menu_buttons[2].rect.collidepoint(pos):
                    pygame.quit()
                    sys.exit()

            elif self.state == "settings":
                if self.settings_buttons[0].rect.collidepoint(pos):
                    names = list(DIFFICULTIES.keys())
                    idx = names.index(self.difficulty)
                    self.difficulty = names[(idx + 1) % len(names)]
                    sound.play("click")
                elif self.settings_buttons[1].rect.collidepoint(pos):
                    self.state = "menu"
                    sound.play("click")

            elif self.state == "victory":
                self.state = "menu"

    def draw_background(self):
        for y in range(HEIGHT):
            ratio = y / HEIGHT
            color = (
                int(SKY[0] + ratio * 25),
                int(SKY[1] + ratio * 25),
                int(SKY[2] + ratio * 40),
            )
            pygame.draw.line(screen, color, (0, y), (WIDTH, y))

        moon_x = int(850 - self.camera_x * 0.08)
        pygame.draw.circle(screen, (240, 230, 175), (moon_x, 100), 55)

        random.seed(8)
        for _ in range(55):
            x = (random.randint(0, WIDTH) - int(self.camera_x * 0.04)) % WIDTH
            y = random.randint(35, 280)
            brightness = 140 + int(80 * (math.sin(self.time * 2 + x) + 1) / 2)
            pygame.draw.circle(screen, (brightness, brightness, 210), (x, y), 1)
        random.seed()

        for layer, color, base in [
            (0.12, (35, 45, 78), 460),
            (0.25, (28, 38, 66), 500),
        ]:
            points = []
            for x in range(-100, WIDTH + 150, 100):
                world_x = x + self.camera_x * layer
                y = int(base - 120 * math.sin(world_x / 210))
                points.append((x, y))
            pygame.draw.polygon(screen, color, [(0, HEIGHT)] + points + [(WIDTH, HEIGHT)])

    def draw_level(self):
        self.draw_background()

        for platform in self.platforms:
            rect = platform.copy()
            rect.x -= int(self.camera_x)
            if rect.right < 0 or rect.left > WIDTH:
                continue
            pygame.draw.rect(screen, DARK_GRAY, rect, border_radius=5)
            pygame.draw.rect(screen, GREEN, (rect.x, rect.y, rect.width, 8), border_radius=4)

        for hazard in self.hazards:
            rect = hazard.copy()
            rect.x -= int(self.camera_x)
            for x in range(rect.left, rect.right, 18):
                pygame.draw.polygon(
                    screen,
                    RED,
                    [(x, rect.bottom), (x + 9, rect.top), (x + 18, rect.bottom)],
                )

        for checkpoint in self.checkpoints:
            x = checkpoint.x - self.camera_x
            pygame.draw.line(screen, WHITE, (x + 15, checkpoint.y), (x + 15, checkpoint.y + 50), 4)
            pygame.draw.polygon(
                screen,
                GOLD,
                [(x + 17, checkpoint.y), (x + 55, checkpoint.y + 14), (x + 17, checkpoint.y + 28)],
            )

        for coin in self.coin_rects:
            rect = coin.copy()
            rect.x -= int(self.camera_x)
            pulse = int(2 * math.sin(self.time * 6 + coin.x))
            pygame.draw.circle(screen, GOLD, rect.center, 14 + pulse)
            pygame.draw.circle(screen, (255, 245, 160), rect.center, 7)

        for enemy in self.enemies:
            enemy.draw(self.camera_x)

        if self.boss:
            self.boss.draw(self.camera_x)

        for projectile in self.projectiles:
            projectile.draw(self.camera_x)

        self.player.draw(self.camera_x)

        for particle in self.particles:
            particle.draw(self.camera_x)

        for floating in self.floating:
            floating.draw(self.camera_x)

        finish_x = 4450 - self.camera_x
        pygame.draw.line(screen, WHITE, (finish_x, 350), (finish_x, 540), 5)
        draw_text("ФИНИШ", font_small, GOLD, finish_x, 320)

        pygame.draw.rect(screen, (8, 10, 20, 180), (12, 12, 310, 108), border_radius=10)
        pygame.draw.rect(screen, BLACK, (25, 25, 180, 15))
        pygame.draw.rect(
            screen,
            RED,
            (25, 25, int(180 * max(self.player.health, 0) / self.player.max_health), 15),
        )
        pygame.draw.rect(screen, WHITE, (25, 25, 180, 15), 2)

        draw_text(f"Счёт: {int(self.score)}", font_small, WHITE, 25, 48, center=False)
        draw_text(
            f"Монеты: {self.coins}   Лучший: {self.best_score}",
            font_small,
            GOLD,
            25,
            77,
            center=False,
        )

        draw_text(
            "A/D — ходьба   SPACE — прыжок   F — удар",
            font_tiny,
            WHITE,
            WIDTH - 440,
            18,
            center=False,
        )
        draw_text("SHIFT — рывок   P — пауза", font_tiny, WHITE, WIDTH - 245, 42, center=False)

    def draw_menu(self):
        self.draw_background()
        draw_text("SHADOW PARKOUR", font_title, WHITE, WIDTH // 2, 135)
        draw_text("NIGHTFALL — охота на Владыку Бездны", font_medium, BLUE, WIDTH // 2, 205)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.menu_buttons:
            button.update(mouse_pos)
            button.draw()

        draw_text(
            f"Сложность: {self.difficulty}    Лучший счёт: {self.best_score}",
            font_small,
            GRAY,
            WIDTH // 2,
            525,
        )

    def draw_settings(self):
        self.draw_background()
        draw_text("НАСТРОЙКИ", font_title, WHITE, WIDTH // 2, 145)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.settings_buttons:
            button.update(mouse_pos)
            button.draw()

        draw_text(f"Текущая сложность: {self.difficulty}", font_medium, GOLD, WIDTH // 2, 455)
        draw_text("Двойной прыжок, рывок и босс уже встроены", font_small, GRAY, WIDTH // 2, 505)

    def draw_pause(self):
        self.draw_level()
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        screen.blit(overlay, (0, 0))
        draw_text("ПАУЗА", font_title, WHITE, WIDTH // 2, 250)
        draw_text("P — продолжить   ESC — меню", font_medium, GRAY, WIDTH // 2, 350)

    def draw_victory(self):
        self.draw_background()
        draw_text("ПОБЕДА!", font_title, GOLD, WIDTH // 2, 180)
        draw_text("Владыка Бездны повержен", font_big, WHITE, WIDTH // 2, 275)
        draw_text(f"Счёт: {int(self.score)}   Монет: {self.coins}", font_medium, GOLD, WIDTH // 2, 360)
        draw_text(f"Рекорд: {self.best_score}", font_medium, WHITE, WIDTH // 2, 405)
        draw_text("Мышь или ESC — вернуться в меню", font_small, GRAY, WIDTH // 2, 490)

    def draw(self):
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "settings":
            self.draw_settings()
        elif self.state == "playing":
            self.draw_level()
        elif self.state == "paused":
            self.draw_pause()
        elif self.state == "victory":
            self.draw_victory()


# ============================================================
# ЗАПУСК
# ============================================================

def main():
    game = Game()
    running = True

    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            game.handle_event(event)

        game.update(dt)
        game.draw()
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
