from pathlib import Path
from array import array
import json
import math
import random
import sys
import pygame

# Shadow Parkour: расширенная версия. Ассеты полностью необязательны.
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

WHITE, BLACK = (245, 245, 245), (8, 10, 18)
GRAY, DARK_GRAY = (150, 160, 180), (35, 40, 58)
SKY, GREEN = (18, 23, 48), (70, 190, 105)
RED, PURPLE, GOLD = (220, 65, 75), (155, 80, 200), (255, 210, 70)
BLUE, ORANGE, CYAN = (75, 150, 240), (240, 135, 55), (75, 220, 220)
font_title = pygame.font.SysFont("arial", 70, bold=True)
font_big = pygame.font.SysFont("arial", 43, bold=True)
font_medium = pygame.font.SysFont("arial", 26, bold=True)
font_small = pygame.font.SysFont("arial", 19)
font_tiny = pygame.font.SysFont("arial", 15)

DIFFICULTIES = {
    "Легко": dict(speed=285, jump=800, enemy_speed=65, damage=8, health=150, scale=.85),
    "Средне": dict(speed=315, jump=850, enemy_speed=88, damage=14, health=100, scale=1),
    "Сложно": dict(speed=345, jump=900, enemy_speed=112, damage=22, health=75, scale=1.25),
}


class SoundManager:
    """Загружает sounds/*.wav, а если файла нет — создаёт короткий beep-заглушку."""
    def __init__(self):
        self.sounds = {}
        for name, frequency, duration in {
            "jump": (520, .09), "dash": (180, .12), "hit": (90, .10),
            "coin": (880, .10), "hurt": (120, .16), "boss": (55, .35),
            "victory": (660, .35), "click": (300, .06),
        }.items():
            self.sounds[name] = self.load_or_beep(name, frequency, duration)
        self.music = None
        music_path = SOUNDS_DIR / "music.ogg"
        try:
            if music_path.exists():
                pygame.mixer.music.load(str(music_path))
                self.music = music_path
        except (pygame.error, OSError):
            self.music = None

    def load_or_beep(self, name, frequency, duration):
        path = SOUNDS_DIR / f"{name}.wav"
        try:
            if path.exists():
                return pygame.mixer.Sound(str(path))
            if not pygame.mixer.get_init():
                return None
            rate = 44100
            samples = array("h")
            for i in range(int(rate * duration)):
                fade = 1 - i / (rate * duration)
                samples.append(int(12000 * fade * math.sin(2 * math.pi * frequency * i / rate)))
            return pygame.mixer.Sound(buffer=samples.tobytes())
        except (pygame.error, OSError):
            return None

    def play(self, name):
        sound = self.sounds.get(name)
        if sound:
            try:
                sound.play()
            except pygame.error:
                pass

    def start_music(self):
        if self.music:
            try:
                pygame.mixer.music.play(-1)
            except pygame.error:
                pass


sounds = SoundManager()


def fallback_surface(size, color, label=""):
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill(color)
    pygame.draw.rect(surface, BLACK, surface.get_rect(), 3)
    for x in range(-size[1], size[0], 16):
        pygame.draw.line(surface, (255, 255, 255, 40), (x, 0), (x + size[1], size[1]), 2)
    if label:
        text = font_tiny.render(label, True, WHITE)
        surface.blit(text, text.get_rect(center=surface.get_rect().center))
    return surface


IMAGE_CACHE = {}


def load_sheet(filename, frame_size, color, label, frame_count=4):
    """Поддерживает горизонтальный sprite-sheet: кадры идут слева направо."""
    key = (filename, frame_size, color, label, frame_count)
    if key in IMAGE_CACHE:
        return IMAGE_CACHE[key]
    frames = []
    try:
        image = pygame.image.load(str(TEXTURES_DIR / filename)).convert_alpha()
        for i in range(frame_count):
            part = pygame.Rect(i * frame_size[0], 0, frame_size[0], frame_size[1])
            if part.right <= image.get_width() and part.bottom <= image.get_height():
                frames.append(pygame.transform.smoothscale(image.subsurface(part).copy(), frame_size))
        if not frames:
            raise pygame.error("sprite-sheet has no frames")
    except (pygame.error, FileNotFoundError, OSError):
        frames = [fallback_surface(frame_size, color, f"{label} {i + 1}") for i in range(frame_count)]
    IMAGE_CACHE[key] = frames
    return frames


def draw_text(text, font, color, x, y, center=True):
    image = font.render(str(text), True, color)
    rect = image.get_rect(center=(x, y) if center else (0, 0))
    if not center:
        rect.topleft = (x, y)
    screen.blit(image, rect)


def clamp(value, low, high):
    return max(low, min(value, high))


def load_best():
    try:
        return int(json.loads(SAVE_FILE.read_text(encoding="utf-8")).get("best", 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


def save_best(value):
    try:
        SAVE_FILE.write_text(json.dumps({"best": int(value)}), encoding="utf-8")
    except OSError:
        pass


class Particle:
    def __init__(self, x, y, color, life=.5, speed=140, gravity=500):
        angle, velocity = random.random() * math.tau, random.uniform(speed * .3, speed)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(angle) * velocity, math.sin(angle) * velocity
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

    def draw(self, camera):
        size = max(1, int(self.size * self.life / self.max_life))
        pygame.draw.circle(screen, self.color, (int(self.x - camera), int(self.y)), size)


class FloatingText:
    def __init__(self, text, x, y, color=WHITE):
        self.text, self.x, self.y, self.color, self.life = text, x, y, color, 1

    def update(self, dt):
        self.y -= 35 * dt
        self.life -= dt
        return self.life > 0

    def draw(self, camera):
        image = font_small.render(self.text, True, self.color)
        image.set_alpha(int(255 * clamp(self.life, 0, 1)))
        screen.blit(image, image.get_rect(center=(self.x - camera, self.y)))


class Button:
    def __init__(self, rect, text):
        self.rect, self.text, self.hovered = pygame.Rect(rect), text, False

    def draw(self):
        pygame.draw.rect(screen, BLUE if self.hovered else DARK_GRAY, self.rect, border_radius=12)
        pygame.draw.rect(screen, WHITE, self.rect, 2, border_radius=12)
        draw_text(self.text, font_medium, WHITE, self.rect.centerx, self.rect.centery)

    def update(self, mouse):
        self.hovered = self.rect.collidepoint(mouse)


class Player:
    def __init__(self, game):
        self.game, self.rect = game, pygame.Rect(150, 350, 58, 82)
        self.x, self.y = 150., 350.
        self.vx = self.vy = 0.
        self.direction, self.grounded, self.double_jump = 1, False, True
        self.coyote, self.jump_buffer = 0., 0.
        self.max_health = self.health = 100
        self.invuln = self.attack_timer = self.attack_cd = 0.
        self.dash_timer = self.dash_cd = 0.
        self.anim_time = 0
        self.idle = load_sheet("player_idle.png", (58, 82), BLUE, "IDLE", 4)
        self.run = load_sheet("player_run.png", (58, 82), GREEN, "RUN", 6)
        self.jump = load_sheet("player_jump.png", (58, 82), ORANGE, "JUMP", 2)
        self.attack_frames = load_sheet("player_attack.png", (58, 82), RED, "ATTACK", 4)

    def reset(self, position):
        self.x, self.y = map(float, position)
        self.rect.topleft = position
        self.vx = self.vy = 0
        self.health = self.max_health
        self.invuln, self.double_jump, self.dash_cd = .9, True, 0

    def jump_action(self):
        power = DIFFICULTIES[self.game.difficulty]["jump"]
        if self.grounded or self.coyote > 0:
            self.vy, self.grounded, self.coyote = -power, False, 0
        elif self.double_jump:
            self.vy, self.double_jump = -power * .82, False
        else:
            return
        sounds.play("jump")
        self.game.burst(self.rect.centerx, self.rect.bottom, CYAN, 10)

    def attack(self):
        if self.attack_cd > 0:
            return
        self.attack_timer, self.attack_cd = .25, .42
        hit = pygame.Rect(self.rect.right if self.direction > 0 else self.rect.left - 70, self.rect.y + 15, 70, 52)
        self.game.burst(hit.centerx, hit.centery, GOLD, 7, gravity=0)
        for enemy in self.game.enemies + ([self.game.boss] if self.game.boss else []):
            if enemy and enemy.alive and hit.colliderect(enemy.rect):
                enemy.take_damage(35)
                self.game.score += 25

    def dash(self):
        if self.dash_cd <= 0:
            self.dash_timer, self.dash_cd = .14, .8
            self.vx, self.invuln = self.direction * 950, .2
            sounds.play("dash")
            self.game.shake = 6
            self.game.burst(self.rect.centerx, self.rect.centery, BLUE, 18, gravity=0)

    def take_damage(self, amount):
        if self.invuln > 0:
            return
        self.health -= amount
        self.invuln = .55
        self.game.shake = 8
        sounds.play("hurt")
        if self.health <= 0:
            self.game.respawn()

    def update(self, dt, keys):
        difficulty = DIFFICULTIES[self.game.difficulty]
        self.invuln = max(0, self.invuln - dt)
        self.attack_cd = max(0, self.attack_cd - dt)
        self.attack_timer = max(0, self.attack_timer - dt)
        self.dash_cd = max(0, self.dash_cd - dt)
        self.dash_timer = max(0, self.dash_timer - dt)
        self.coyote = max(0, self.coyote - dt)
        self.jump_buffer = max(0, self.jump_buffer - dt)
        left, right = keys[pygame.K_a] or keys[pygame.K_LEFT], keys[pygame.K_d] or keys[pygame.K_RIGHT]
        if self.dash_timer <= 0:
            self.vx = -difficulty["speed"] if left else difficulty["speed"] if right else 0
        if self.vx:
            self.direction = 1 if self.vx > 0 else -1
        if self.jump_buffer:
            self.jump_action(); self.jump_buffer = 0
        if keys[pygame.K_f] or keys[pygame.K_j]:
            self.attack()
        self.vy += 1900 * dt
        old_bottom = self.rect.bottom
        self.x += self.vx * dt; self.y += self.vy * dt
        self.rect.topleft = (int(self.x), int(self.y))
        self.grounded = False
        for platform in self.game.platforms:
            if self.rect.colliderect(platform) and self.vy >= 0 and old_bottom <= platform.top + 10:
                self.rect.bottom, self.y, self.vy = platform.top, float(platform.top - self.rect.height), 0
                self.grounded, self.double_jump = True, True
        if not self.grounded and old_bottom <= self.game.level_height:
            self.coyote = .1
        self.rect.left = max(0, self.rect.left); self.x = float(self.rect.x)
        for enemy in self.game.enemies + ([self.game.boss] if self.game.boss else []):
            if enemy and enemy.alive and self.rect.colliderect(enemy.rect):
                self.take_damage(enemy.damage * dt)
        for hazard in self.game.hazards:
            if self.rect.colliderect(hazard):
                self.take_damage(40 * dt)
        if self.rect.top > self.game.level_height + 250:
            self.game.respawn()
        frames = self.attack_frames if self.attack_timer else self.jump if not self.grounded else self.run if self.vx else self.idle
        self.anim_time += dt * (12 if self.attack_timer else 5 if not self.grounded else 10 if self.vx else 5)
        self.frame = int(self.anim_time) % len(frames)

    def draw(self, camera):
        if self.invuln > 0 and int(self.invuln * 18) % 2 == 0:
            return
        frames = self.attack_frames if self.attack_timer else self.jump if not self.grounded else self.run if self.vx else self.idle
        image = frames[self.frame]
        if self.direction < 0:
            image = pygame.transform.flip(image, True, False)
        screen.blit(image, (self.rect.x - camera, self.rect.y))


class Enemy:
    def __init__(self, game, x, y, kind="zombie"):
        self.game, self.kind = game, kind
        self.rect = pygame.Rect(x, y, 58, 78); self.x, self.y = float(x), float(y)
        base = 60 if kind == "zombie" else 48 if kind == "vampire" else 110
        self.max_health = self.health = base * DIFFICULTIES[game.difficulty]["scale"]
        self.damage = DIFFICULTIES[game.difficulty]["damage"] * (1.35 if kind == "vampire" else 1.0)
        self.speed = DIFFICULTIES[game.difficulty]["enemy_speed"] * (1.3 if kind == "vampire" else .75 if kind == "brute" else 1)
        self.alive, self.direction, self.anim_time = True, -1, random.random() * 4
        colors = {"zombie": (GREEN, "ZOMBIE"), "vampire": (PURPLE, "VAMPIRE"), "brute": (ORANGE, "BRUTE")}
        color, label = colors.get(kind, (RED, "ENEMY"))
        self.frames = load_sheet(f"{kind}_sheet.png", (58, 78), color, label, 4)

    def take_damage(self, amount):
        if not self.alive: return
        self.health -= amount; sounds.play("hit"); self.game.burst(self.rect.centerx, self.rect.centery, RED, 8)
        if self.health <= 0:
            self.alive = False; self.game.score += 150; self.game.burst(self.rect.centerx, self.rect.centery, PURPLE, 22)

    def update(self, dt):
        if not self.alive: return
        distance = self.game.player.rect.centerx - self.rect.centerx
        if abs(distance) < 520:
            self.direction = 1 if distance > 8 else -1 if distance < -8 else self.direction
            self.x += self.direction * self.speed * dt
        self.rect.x = int(self.x)
        old_bottom = self.rect.bottom; self.y += 1900 * dt; self.rect.y = int(self.y)
        for platform in self.game.platforms:
            if self.rect.colliderect(platform) and old_bottom <= platform.top + 12:
                self.rect.bottom = platform.top; self.y = float(self.rect.y)
        self.anim_time += dt * 7
        self.frame = int(self.anim_time) % len(self.frames)

    def draw(self, camera):
        if not self.alive: return
        image = self.frames[self.frame]
        if self.direction < 0: image = pygame.transform.flip(image, True, False)
        screen.blit(image, (self.rect.x - camera, self.rect.y))
        bar = pygame.Rect(self.rect.x - camera, self.rect.y - 12, self.rect.width, 7)
        pygame.draw.rect(screen, BLACK, bar)
        pygame.draw.rect(screen, RED, (bar.x, bar.y, int(bar.width * max(self.health, 0) / self.max_health), 7))


class Boss(Enemy):
    def __init__(self, game, x, y):
        super().__init__(game, x, y, "brute")
        self.rect = pygame.Rect(x, y, 120, 140); self.max_health = self.health = 850 * DIFFICULTIES[game.difficulty]["scale"]
        self.damage = DIFFICULTIES[game.difficulty]["damage"] * 2.0; self.speed = 65
        self.phase, self.cooldown, self.rage = 1, 1.2, False
        self.frames = load_sheet("boss_sheet.png", (120, 140), RED, "BOSS", 4)

    def take_damage(self, amount):
        super().take_damage(amount)
        if self.health <= self.max_health * .5 and self.phase == 1:
            self.phase, self.rage = 2, True
            sounds.play("boss"); self.game.floating.append(FloatingText("БЕЗДНА ПРОСЫПАЕТСЯ!", self.rect.centerx, self.rect.y - 25, RED))

    def update(self, dt):
        if not self.alive: return
        player = self.game.player; distance = player.rect.centerx - self.rect.centerx
        self.direction = 1 if distance > 0 else -1
        self.x += self.direction * self.speed * (1.45 if self.rage else 1) * dt
        self.rect.x = int(self.x); self.cooldown -= dt
        if self.cooldown <= 0 and abs(distance) < 850:
            self.cooldown = .8 if self.rage else 1.35
            self.game.projectiles.append(Projectile(self.rect.centerx, self.rect.centery, player.rect.centerx, player.rect.centery, RED, 16, 260))
            self.game.burst(self.rect.centerx, self.rect.centery, RED, 10, gravity=0); sounds.play("boss")
        self.anim_time += dt * (10 if self.rage else 5); self.frame = int(self.anim_time) % len(self.frames)

    def draw(self, camera):
        if not self.alive: return
        image = self.frames[self.frame]
        if self.direction < 0: image = pygame.transform.flip(image, True, False)
        screen.blit(image, (self.rect.x - camera, self.rect.y))
        bar = pygame.Rect(240, 18, 620, 20)
        pygame.draw.rect(screen, BLACK, bar); pygame.draw.rect(screen, RED if self.rage else PURPLE, (bar.x, bar.y, int(bar.width * max(self.health, 0) / self.max_health), bar.height)); pygame.draw.rect(screen, WHITE, bar, 2)
        draw_text("ВЛАДЫКА БЕЗДНЫ", font_small, WHITE, WIDTH // 2, 50)


class Projectile:
    def __init__(self, x, y, tx, ty, color, damage, speed):
        self.x, self.y, self.color, self.damage, self.speed = x, y, color, damage, speed
        length = max(1, math.hypot(tx - x, ty - y)); self.vx, self.vy = (tx - x) / length * speed, (ty - y) / length * speed
        self.life = 4

    def update(self, dt, game):
        self.x += self.vx * dt; self.y += self.vy * dt; self.life -= dt
        if pygame.Rect(int(self.x - 10), int(self.y - 10), 20, 20).colliderect(game.player.rect):
            game.player.take_damage(self.damage); return False
        return self.life > 0 and -50 < self.x < game.level_width + 50 and -50 < self.y < HEIGHT + 100

    def draw(self, camera):
        pygame.draw.circle(screen, self.color, (int(self.x - camera), int(self.y)), 10)
        pygame.draw.circle(screen, WHITE, (int(self.x - camera), int(self.y)), 4)


class Game:
    def __init__(self):
        self.state, self.difficulty = "menu", "Средне"; self.level_width, self.level_height = 4700, 600
        self.camera, self.score, self.coins, self.best = 0, 0, 0, load_best(); self.time = self.shake = 0
        self.checkpoint = (150, 350); self.particles, self.floating, self.projectiles = [], [], []
        self.platforms, self.hazards, self.checkpoints, self.coins_rects = [], [], [], []
        self.enemies, self.boss = [], None; self.player = Player(self)
        self.menu = [Button((400, 270, 300, 58), "Начать игру"), Button((400, 340, 300, 58), "Настройки"), Button((400, 410, 300, 58), "Выход")]
        self.settings = [Button((400, 270, 300, 58), "Сложность"), Button((400, 340, 300, 58), "Назад")]
        self.create_level()

    def create_level(self):
        self.platforms = [pygame.Rect(0, 540, 700, 110), pygame.Rect(850, 540, 550, 110), pygame.Rect(1550, 540, 650, 110), pygame.Rect(2350, 540, 550, 110), pygame.Rect(3050, 540, 550, 110), pygame.Rect(3750, 540, 950, 110), pygame.Rect(430, 430, 190, 28), pygame.Rect(970, 390, 190, 28), pygame.Rect(1250, 300, 180, 28), pygame.Rect(1720, 410, 220, 28), pygame.Rect(2050, 320, 190, 28), pygame.Rect(2500, 420, 220, 28), pygame.Rect(2800, 300, 180, 28), pygame.Rect(3200, 410, 220, 28), pygame.Rect(3500, 300, 180, 28), pygame.Rect(3950, 390, 220, 28), pygame.Rect(4300, 320, 250, 28)]
        self.hazards = [pygame.Rect(x, 615, 150, 35) for x in (700, 1400, 2200, 2900, 3600)]
        self.checkpoints = [pygame.Rect(x, 490, 35, 50) for x in (1350, 2700, 3600)]
        self.coins_rects = [pygame.Rect(x, y, 28, 28) for x, y in [(470,380),(570,380),(1010,340),(1290,250),(1760,360),(2100,270),(2540,370),(2840,250),(3240,360),(3540,250),(3990,340),(4370,260)]]
        positions = [(570,462,"zombie"),(1080,312,"vampire"),(1250,222,"zombie"),(1800,332,"vampire"),(2150,242,"brute"),(2600,342,"vampire"),(3280,332,"zombie"),(3550,222,"brute"),(3980,312,"zombie")]
        self.enemies = [Enemy(self, *item) for item in positions]; self.boss = Boss(self, 4300, 180)

    def burst(self, x, y, color, count=8, gravity=500):
        self.particles += [Particle(x, y, color, random.uniform(.25, .65), random.uniform(60, 180), gravity) for _ in range(count)]

    def start(self):
        self.state, self.score, self.coins, self.camera, self.checkpoint = "playing", 0, 0, 0, (150, 350)
        self.player.max_health = DIFFICULTIES[self.difficulty]["health"]; self.player.reset(self.checkpoint); self.projectiles.clear(); self.create_level(); sounds.start_music()

    def respawn(self):
        self.player.reset(self.checkpoint); self.burst(*self.checkpoint, RED, 15)

    def update(self, dt):
        self.time += dt; self.shake = max(0, self.shake - 20 * dt)
        self.particles = [p for p in self.particles if p.update(dt)]; self.floating = [f for f in self.floating if f.update(dt)]
        if self.state != "playing": return
        self.player.update(dt, pygame.key.get_pressed())
        for enemy in self.enemies: enemy.update(dt)
        if self.boss: self.boss.update(dt)
        self.projectiles = [p for p in self.projectiles if p.update(dt, self)]
        for checkpoint in self.checkpoints:
            if self.player.rect.colliderect(checkpoint) and checkpoint.x > self.checkpoint[0]:
                self.checkpoint = (checkpoint.x, checkpoint.y - self.player.rect.height); self.score += 200; self.floating.append(FloatingText("ЧЕКПОИНТ +200", checkpoint.x, checkpoint.y, GOLD)); self.burst(checkpoint.centerx, checkpoint.centery, GOLD, 18)
        remaining = []
        for coin in self.coins_rects:
            if self.player.rect.colliderect(coin): self.coins += 1; self.score += 100; sounds.play("coin"); self.burst(coin.centerx, coin.centery, GOLD, 12, 0)
            else: remaining.append(coin)
        self.coins_rects = remaining; self.score += dt * 10
        self.camera = clamp(self.player.rect.centerx - WIDTH // 2, 0, self.level_width - WIDTH)
        if self.boss and not self.boss.alive and self.player.rect.x > 4450:
            self.state = "victory"; self.best = max(self.best, int(self.score)); save_best(self.best); sounds.play("victory")

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and self.state in ("playing", "paused", "settings", "victory"): self.state = "menu"
            elif self.state == "playing":
                if event.key == pygame.K_p: self.state = "paused"
                elif event.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP): self.player.jump_buffer = .14
                elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT): self.player.dash()
            elif self.state == "paused" and event.key == pygame.K_p: self.state = "playing"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.state == "menu":
                if self.menu[0].rect.collidepoint(pos): self.start()
                elif self.menu[1].rect.collidepoint(pos): self.state = "settings"
                elif self.menu[2].rect.collidepoint(pos): pygame.quit(); sys.exit()
            elif self.state == "settings":
                if self.settings[0].rect.collidepoint(pos):
                    names = list(DIFFICULTIES); self.difficulty = names[(names.index(self.difficulty) + 1) % len(names)]; sounds.play("click")
                elif self.settings[1].rect.collidepoint(pos): self.state = "menu"
            elif self.state == "victory": self.state = "menu"

    def background(self):
        for y in range(HEIGHT):
            ratio = y / HEIGHT; pygame.draw.line(screen, (int(SKY[0]+ratio*25), int(SKY[1]+ratio*25), int(SKY[2]+ratio*40)), (0,y), (WIDTH,y))
        pygame.draw.circle(screen, (240,230,175), (int(850-self.camera*.08), 100), 55)
        random.seed(8)
        for _ in range(55):
            x = (random.randrange(WIDTH) - int(self.camera*.04)) % WIDTH; y = random.randrange(40, 280)
            pygame.draw.circle(screen, (150+int(70*(math.sin(self.time*2+x)+1)/2), 160, 210), (x,y), 1)
        random.seed()
        for layer, color, base in ((.12,(35,45,78),460),(.25,(28,38,66),500)):
            points = [(x, int(base - 120*math.sin((x+self.camera*layer)/210))) for x in range(-100, WIDTH+150, 100)]
            pygame.draw.polygon(screen, color, [(0,HEIGHT)] + points + [(WIDTH,HEIGHT)])

    def draw_level(self):
        self.background()
        for platform in self.platforms:
            r = platform.copy(); r.x -= int(self.camera); pygame.draw.rect(screen, DARK_GRAY, r, border_radius=5); pygame.draw.rect(screen, GREEN, (r.x,r.y,r.width,8), border_radius=4)
        for hazard in self.hazards:
            r = hazard.copy(); r.x -= int(self.camera)
            for x in range(r.left, r.right, 18): pygame.draw.polygon(screen, RED, [(x,r.bottom),(x+9,r.top),(x+18,r.bottom)])
        for checkpoint in self.checkpoints:
            x = checkpoint.x - self.camera; pygame.draw.line(screen, WHITE, (x+15,checkpoint.y), (x+15,checkpoint.y+50),4); pygame.draw.polygon(screen,GOLD,[(x+17,checkpoint.y),(x+55,checkpoint.y+14),(x+17,checkpoint.y+28)])
        for coin in self.coins_rects:
            r=coin.copy(); r.x-=int(self.camera); pygame.draw.circle(screen,GOLD,r.center,14+int(2*math.sin(self.time*6+coin.x))); pygame.draw.circle(screen,(255,245,160),r.center,7)
        for enemy in self.enemies: enemy.draw(self.camera)
        if self.boss: self.boss.draw(self.camera)
        for projectile in self.projectiles: projectile.draw(self.camera)
        self.player.draw(self.camera)
        for particle in self.particles: particle.draw(self.camera)
        for text in self.floating: text.draw(self.camera)
        pygame.draw.line(screen, WHITE, (4450-self.camera,350), (4450-self.camera,540),5)
        draw_text("ФИНИШ ПОСЛЕ БОССА", font_small, GOLD, 4450-self.camera, 320)
        pygame.draw.rect(screen,(8,10,20), (12,12,310,108), border_radius=10); pygame.draw.rect(screen,BLACK,(25,25,180,15)); pygame.draw.rect(screen,RED,(25,25,int(180*max(self.player.health,0)/self.player.max_health),15)); pygame.draw.rect(screen,WHITE,(25,25,180,15),2)
        draw_text(f"Счёт: {int(self.score)}",font_small,WHITE,25,48,False); draw_text(f"Монеты: {self.coins}   Рекорд: {self.best}",font_small,GOLD,25,77,False); draw_text("A/D движение  SPACE прыжок  F удар  SHIFT рывок  P пауза",font_tiny,WHITE,WIDTH-470,18,False)

    def draw(self):
        if self.state == "menu":
            self.background(); draw_text("SHADOW PARKOUR",font_title,WHITE,WIDTH//2,135); draw_text("NIGHTFALL — охота на Владыку Бездны",font_medium,BLUE,WIDTH//2,205)
            for b in self.menu: b.update(pygame.mouse.get_pos()); b.draw()
            draw_text(f"Сложность: {self.difficulty}    Рекорд: {self.best}",font_small,GRAY,WIDTH//2,525)
        elif self.state == "settings":
            self.background(); draw_text("НАСТРОЙКИ",font_title,WHITE,WIDTH//2,145)
            for b in self.settings: b.update(pygame.mouse.get_pos()); b.draw()
            draw_text(f"Текущая сложность: {self.difficulty}",font_medium,GOLD,WIDTH//2,455); draw_text("В игре есть двойной прыжок, рывок и босс",font_small,GRAY,WIDTH//2,505)
        elif self.state == "playing": self.draw_level()
        elif self.state == "paused":
            self.draw_level(); overlay=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA); overlay.fill((0,0,0,175)); screen.blit(overlay,(0,0)); draw_text("ПАУЗА",font_title,WHITE,WIDTH//2,250); draw_text("P — продолжить  ESC — меню",font_medium,GRAY,WIDTH//2,350)
        else:
            self.background(); draw_text("ПОБЕДА!",font_title,GOLD,WIDTH//2,180); draw_text("Владыка Бездны повержен",font_big,WHITE,WIDTH//2,275); draw_text(f"Счёт: {int(self.score)}   Монеты: {self.coins}",font_medium,GOLD,WIDTH//2,360); draw_text(f"Рекорд: {self.best}",font_medium,WHITE,WIDTH//2,405); draw_text("Мышь или ESC — вернуться в меню",font_small,GRAY,WIDTH//2,490)


def main():
    game = Game(); running = True
    while running:
        dt = min(clock.tick(FPS) / 1000, .05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            else: game.handle_event(event)
        game.update(dt); game.draw(); pygame.display.flip()
    pygame.quit(); sys.exit()


if __name__ == "__main__":
    main()
