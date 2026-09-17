from pathlib import Path
import json
import math
import random
import sys
import pygame

# Shadow Parkour — расширенная версия без обязательных ассетов.
# Все картинки и звуки необязательны: при их отсутствии используются заглушки.
pygame.init()

WIDTH, HEIGHT, FPS = 1100, 650, 60
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Shadow Parkour")
clock = pygame.time.Clock()
BASE_DIR = Path(__file__).resolve().parent
TEXTURES_DIR = BASE_DIR / "textures"
SOUNDS_DIR = BASE_DIR / "sounds"
SAVE_FILE = BASE_DIR / "shadow_parkour_save.json"
TEXTURES_DIR.mkdir(exist_ok=True)
SOUNDS_DIR.mkdir(exist_ok=True)

WHITE = (245, 245, 245)
BLACK = (10, 12, 20)
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

font_title = pygame.font.SysFont("arial", 72, bold=True)
font_big = pygame.font.SysFont("arial", 44, bold=True)
font_medium = pygame.font.SysFont("arial", 27, bold=True)
font_small = pygame.font.SysFont("arial", 20)
font_tiny = pygame.font.SysFont("arial", 16)

DIFFICULTIES = {
    "Легко": dict(player_speed=285, jump_power=800, enemy_speed=65,
                  enemy_damage=8, player_health=150, enemy_health=0.85),
    "Средне": dict(player_speed=315, jump_power=850, enemy_speed=88,
                   enemy_damage=14, player_health=100, enemy_health=1),
    "Сложно": dict(player_speed=345, jump_power=900, enemy_speed=112,
                   enemy_damage=22, player_health=75, enemy_health=1.25),
}


def fallback_surface(size, color, label=""):
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill(color)
    pygame.draw.rect(surface, BLACK, surface.get_rect(), 3)
    for x in range(-size[1], size[0], 16):
        pygame.draw.line(surface, (255, 255, 255, 45), (x, 0),
                         (x + size[1], size[1]), 2)
    if label:
        text = font_tiny.render(label, True, WHITE)
        surface.blit(text, text.get_rect(center=surface.get_rect().center))
    return surface


_IMAGE_CACHE = {}


def load_sheet(filename, frame_size, color, label, frame_count=4):
    key = (filename, frame_size, color, label, frame_count)
    if key in _IMAGE_CACHE:
        return _IMAGE_CACHE[key]
    path = TEXTURES_DIR / filename
    frames = []
    try:
        image = pygame.image.load(str(path)).convert_alpha()
        for i in range(frame_count):
            rect = pygame.Rect(i * frame_size[0], 0, *frame_size)
            if rect.right <= image.get_width() and rect.bottom <= image.get_height():
                frames.append(pygame.transform.smoothscale(
                    image.subsurface(rect).copy(), frame_size))
        if not frames:
            raise pygame.error("empty sprite sheet")
    except (pygame.error, FileNotFoundError, OSError):
        frames = [fallback_surface(frame_size, color, f"{label} {i + 1}")
                  for i in range(frame_count)]
    _IMAGE_CACHE[key] = frames
    return frames


def draw_text(text, font, color, x, y, center=True, target=screen):
    image = font.render(str(text), True, color)
    rect = image.get_rect(center=(x, y) if center else (0, 0))
    if not center:
        rect.topleft = (x, y)
    target.blit(image, rect)


def clamp(value, low, high):
    return max(low, min(value, high))


def save_best(value):
    try:
        SAVE_FILE.write_text(json.dumps({"best_score": int(value)}), encoding="utf-8")
    except OSError:
        pass


def load_best():
    try:
        return int(json.loads(SAVE_FILE.read_text(encoding="utf-8")).get("best_score", 0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


class Particle:
    def __init__(self, x, y, color, life=.5, speed=100, size=4, gravity=500):
        self.x, self.y = x, y
        angle = random.uniform(0, math.tau)
        velocity = random.uniform(speed * .35, speed)
        self.vx, self.vy = math.cos(angle) * velocity, math.sin(angle) * velocity
        self.color, self.life, self.max_life = color, life, life
        self.size, self.gravity = size, gravity

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.life -= dt
        return self.life > 0

    def draw(self, camera_x):
        radius = max(1, int(self.size * self.life / self.max_life))
        pygame.draw.circle(screen, self.color, (int(self.x - camera_x), int(self.y)), radius)


class FloatingText:
    def __init__(self, text, x, y, color=WHITE):
        self.text, self.x, self.y, self.color = text, x, y, color
        self.life = 1.0

    def update(self, dt):
        self.y -= 32 * dt
        self.life -= dt
        return self.life > 0

    def draw(self, camera_x):
        image = font_small.render(self.text, True, self.color)
        image.set_alpha(int(255 * clamp(self.life, 0, 1)))
        screen.blit(image, image.get_rect(center=(self.x - camera_x, self.y)))


class Button:
    def __init__(self, rect, text):
        self.rect, self.text, self.hovered = pygame.Rect(rect), text, False

    def update(self, pos):
        self.hovered = self.rect.collidepoint(pos)

    def draw(self):
        color = BLUE if self.hovered else DARK_GRAY
        pygame.draw.rect(screen, color, self.rect, border_radius=12)
        pygame.draw.rect(screen, WHITE, self.rect, 2, border_radius=12)
        draw_text(self.text, font_medium, WHITE, self.rect.centerx, self.rect.centery)


class Player:
    def __init__(self, game):
        self.game, self.width, self.height = game, 58, 82
        self.rect = pygame.Rect(150, 350, self.width, self.height)
        self.x, self.y = float(self.rect.x), float(self.rect.y)
        self.velocity_x = self.velocity_y = 0.0
        self.direction, self.on_ground = 1, False
        self.coyote_time = self.jump_buffer = 0.0
        self.double_jump = True
        self.health = self.max_health = 100
        self.invulnerability = self.attack_timer = self.attack_cooldown = 0.0
        self.dash_timer, self.dash_cooldown = 0.0, 0.0
        self.animation_time = self.animation_frame = 0
        self.idle = load_sheet("player_idle.png", (self.width, self.height), BLUE, "IDLE", 4)
        self.run = load_sheet("player_run.png", (self.width, self.height), GREEN, "RUN", 6)
        self.jump = load_sheet("player_jump.png", (self.width, self.height), ORANGE, "JUMP", 2)
        self.attack_frames = load_sheet("player_attack.png", (self.width, self.height), RED, "ATTACK", 4)

    def reset(self, position):
        self.x, self.y = map(float, position)
        self.rect.topleft = position
        self.velocity_x = self.velocity_y = 0
        self.health = self.max_health
        self.invulnerability = .9
        self.double_jump = True
        self.dash_timer = self.dash_cooldown = 0

    def get_attack_rect(self):
        x = self.rect.right if self.direction > 0 else self.rect.left - 65
        return pygame.Rect(x, self.rect.y + 15, 65, 50)

    def jump_action(self):
        difficulty = DIFFICULTIES[self.game.difficulty]
        if self.on_ground or self.coyote_time > 0:
            self.velocity_y = -difficulty["jump_power"]
            self.on_ground, self.coyote_time = False, 0
            self.game.burst(self.rect.centerx, self.rect.bottom, CYAN, 8)
            return
        if self.double_jump:
            self.velocity_y = -difficulty["jump_power"] * .82
            self.double_jump = False
            self.game.burst(self.rect.centerx, self.rect.centery, ORANGE, 12)

    def attack(self):
        if self.attack_cooldown > 0:
            return
        self.attack_timer, self.attack_cooldown = .25, .42
        hit = self.get_attack_rect()
        self.game.burst(hit.centerx, hit.centery, GOLD, 5, gravity=0)
        for enemy in self.game.enemies:
            if enemy.alive and hit.colliderect(enemy.rect):
                enemy.take_damage(35)
                self.game.score += 25
                self.game.floating.append(FloatingText("+25", enemy.rect.centerx, enemy.rect.y, GOLD))

    def dash(self):
        if self.dash_cooldown <= 0:
            self.dash_timer, self.dash_cooldown = .14, .8
            self.velocity_x = self.direction * 950
            self.invulnerability = max(self.invulnerability, .2)
            self.game.shake = max(self.game.shake, 5)
            self.game.burst(self.rect.centerx, self.rect.centery, BLUE, 15, gravity=0)

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
            self.velocity_x = (-difficulty["player_speed"] if left else
                               difficulty["player_speed"] if right else 0)
        if self.velocity_x:
            self.direction = 1 if self.velocity_x > 0 else -1
        if self.jump_buffer > 0:
            self.jump_action()
            self.jump_buffer = 0
        if keys[pygame.K_f] or keys[pygame.K_j]:
            self.attack()

        self.velocity_y += 1900 * dt
        old_bottom = self.rect.bottom
        self.x += self.velocity_x * dt
        self.y += self.velocity_y * dt
        self.rect.topleft = (int(self.x), int(self.y))
        self.on_ground = False
        for platform in self.game.platforms:
            if self.rect.colliderect(platform) and self.velocity_y >= 0 and old_bottom <= platform.top + 8:
                self.rect.bottom = platform.top
                self.y, self.velocity_y, self.on_ground = float(self.rect.y), 0, True
                self.double_jump = True
                if abs(self.velocity_y) > 300:
                    self.game.burst(self.rect.centerx, self.rect.bottom, GRAY, 5)
        if not self.on_ground and old_bottom <= self.game.level_height:
            self.coyote_time = .1
        self.rect.left = max(0, self.rect.left)
        self.x = float(self.rect.x)
        for enemy in self.game.enemies:
            if enemy.alive and self.rect.colliderect(enemy.rect):
                self.take_damage(enemy.damage * dt)
        for hazard in self.game.hazards:
            if self.rect.colliderect(hazard):
                self.take_damage(35 * dt)
        if self.rect.top > self.game.level_height + 260:
            self.game.respawn_player()

        frames = self.attack_frames if self.attack_timer > 0 else self.jump if not self.on_ground else self.run if self.velocity_x else self.idle
        speed = 12 if self.attack_timer > 0 else 5 if not self.on_ground else 10 if self.velocity_x else 5
        self.animation_time += dt * speed
        self.animation_frame = int(self.animation_time) % len(frames)

    def take_damage(self, amount):
        if self.invulnerability > 0:
            return
        self.health -= amount
        self.invulnerability = .55
        self.game.shake = max(self.game.shake, 8)
        if self.health <= 0:
            self.game.respawn_player()

    def draw(self, camera_x):
        if self.invulnerability > 0 and int(self.invulnerability * 18) % 2 == 0:
            return
        frames = self.attack_frames if self.attack_timer > 0 else self.jump if not self.on_ground else self.run if self.velocity_x else self.idle
        image = frames[self.animation_frame]
        if self.direction < 0:
            image = pygame.transform.flip(image, True, False)
        screen.blit(image, (self.rect.x - camera_x, self.rect.y))


class Enemy:
    def __init__(self, game, x, y, enemy_type="zombie"):
        self.game, self.enemy_type = game, enemy_type
        self.width, self.height = 58, 78
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.x, self.y = float(x), float(y)
        scale = DIFFICULTIES[game.difficulty]["enemy_health"]
        self.max_health = self.health = (60 if enemy_type == "zombie" else 45) * scale
        self.damage = DIFFICULTIES[game.difficulty]["enemy_damage"] * (1.35 if enemy_type == "vampire" else 1)
        self.alive, self.direction, self.attack_timer = True, -1, random.random()
        color, name = (GREEN, "ZOMBIE") if enemy_type == "zombie" else (PURPLE, "VAMPIRE")
        self.frames = load_sheet("zombie_sheet.png" if enemy_type == "zombie" else "vampire_sheet.png",
                                 (self.width, self.height), color, name, 4)
        self.animation_time = self.animation_frame = 0

    def take_damage(self, amount):
        self.health -= amount
        self.game.burst(self.rect.centerx, self.rect.centery, RED, 6)
        if self.health <= 0:
            self.alive = False
            self.game.score += 150
            self.game.floating.append(FloatingText("+150", self.rect.centerx, self.rect.y, GOLD))
            self.game.burst(self.rect.centerx, self.rect.centery, PURPLE, 20)

    def update(self, dt):
        if not self.alive:
            return
        player = self.game.player
        distance = player.rect.centerx - self.rect.centerx
        speed = DIFFICULTIES[self.game.difficulty]["enemy_speed"]
        if abs(distance) < 470:
            self.direction = 1 if distance > 8 else -1 if distance < -8 else self.direction
            self.x += self.direction * speed * dt
        self.rect.x = int(self.x)
        old_bottom = self.rect.bottom
        self.y += 1900 * dt
        self.rect.y = int(self.y)
        for platform in self.game.platforms:
            if self.rect.colliderect(platform) and old_bottom <= platform.top + 12:
                self.rect.bottom = platform.top
                self.y = float(self.rect.y)
        self.animation_time += dt * 7
        self.animation_frame = int(self.animation_time) % len(self.frames)

    def draw(self, camera_x):
        if not self.alive:
            return
        image = self.frames[self.animation_frame]
        if self.direction < 0:
            image = pygame.transform.flip(image, True, False)
        screen.blit(image, (self.rect.x - camera_x, self.rect.y))
        bar = pygame.Rect(self.rect.x - camera_x, self.rect.y - 12, self.width, 7)
        pygame.draw.rect(screen, BLACK, bar)
        pygame.draw.rect(screen, RED, (bar.x, bar.y, int(bar.width * max(self.health, 0) / self.max_health), bar.height))


class MovingPlatform:
    def __init__(self, x, y, w, h, distance, speed):
        self.rect = pygame.Rect(x, y, w, h)
        self.start_x, self.distance, self.speed, self.t = x, distance, speed, random.random() * 5
        self.dx = 0

    def update(self, dt):
        old = self.rect.x
        self.t += dt * self.speed
        self.rect.x = int(self.start_x + math.sin(self.t) * self.distance)
        self.dx = self.rect.x - old


class Game:
    def __init__(self):
        self.state, self.difficulty = "menu", "Средне"
        self.level_width, self.level_height = 4700, 600
        self.camera_x, self.score, self.coins, self.best_score = 0, 0, 0, load_best()
        self.checkpoint_position = (150, 350)
        self.time, self.shake = 0, 0
        self.particles, self.floating = [], []
        self.platforms, self.moving_platforms, self.hazards = [], [], []
        self.checkpoints, self.coin_rects, self.enemies = [], [], []
        self.player = Player(self)
        self.menu_buttons = [Button((400, 270, 300, 58), "Начать игру"), Button((400, 340, 300, 58), "Настройки"), Button((400, 410, 300, 58), "Выход")]
        self.settings_buttons = [Button((400, 270, 300, 58), "Сложность"), Button((400, 340, 300, 58), "Назад")]
        self.create_level()

    def create_level(self):
        self.platforms = [pygame.Rect(0, 540, 700, 110), pygame.Rect(850, 540, 550, 110), pygame.Rect(1550, 540, 650, 110), pygame.Rect(2350, 540, 550, 110), pygame.Rect(3050, 540, 550, 110), pygame.Rect(3750, 540, 950, 110),
                          pygame.Rect(430, 430, 190, 28), pygame.Rect(970, 390, 190, 28), pygame.Rect(1250, 300, 180, 28), pygame.Rect(1720, 410, 220, 28), pygame.Rect(2050, 320, 190, 28), pygame.Rect(2500, 420, 220, 28), pygame.Rect(2800, 300, 180, 28), pygame.Rect(3200, 410, 220, 28), pygame.Rect(3500, 300, 180, 28), pygame.Rect(3950, 390, 220, 28), pygame.Rect(4300, 280, 180, 28)]
        self.moving_platforms = [MovingPlatform(710, 470, 130, 25, 75, 1.5), MovingPlatform(2200, 440, 130, 25, 110, 1.2), MovingPlatform(2910, 450, 120, 25, 90, 1.8)]
        self.platforms += [p.rect for p in self.moving_platforms]
        self.hazards = [pygame.Rect(700, 615, 150, 35), pygame.Rect(1400, 615, 150, 35), pygame.Rect(2200, 615, 150, 35), pygame.Rect(2900, 615, 150, 35), pygame.Rect(3600, 615, 150, 35)]
        self.checkpoints = [pygame.Rect(1350, 490, 35, 50), pygame.Rect(2700, 490, 35, 50), pygame.Rect(3600, 490, 35, 50)]
        self.coin_rects = [pygame.Rect(x, y, 28, 28) for x, y in [(470, 380), (570, 380), (1010, 340), (1290, 250), (1760, 360), (2100, 270), (2540, 370), (2840, 250), (3240, 360), (3540, 250), (3990, 340), (4350, 230)]]
        self.enemies = [Enemy(self, x, y, kind) for x, y, kind in [(570, 462, "zombie"), (1080, 312, "vampire"), (1250, 222, "zombie"), (1800, 332, "vampire"), (2150, 242, "zombie"), (2600, 342, "vampire"), (3280, 332, "zombie"), (3550, 222, "vampire"), (3980, 312, "zombie"), (4380, 202, "vampire")]]

    def burst(self, x, y, color, count=8, gravity=500):
        for _ in range(count):
            self.particles.append(Particle(x, y, color, random.uniform(.25, .65), random.uniform(60, 180), random.randint(2, 5), gravity))

    def start_game(self):
        self.state, self.score, self.coins, self.camera_x = "playing", 0, 0, 0
        self.checkpoint_position = (150, 350)
        self.player.max_health = DIFFICULTIES[self.difficulty]["player_health"]
        self.player.reset(self.checkpoint_position)
        self.create_level()

    def respawn_player(self):
        self.player.reset(self.checkpoint_position)
        self.burst(*self.checkpoint_position, RED, 12)

    def update_checkpoint(self):
        for checkpoint in self.checkpoints:
            if self.player.rect.colliderect(checkpoint) and checkpoint.x > self.checkpoint_position[0]:
                self.checkpoint_position = (checkpoint.x, checkpoint.y - self.player.height)
                self.score += 200
                self.floating.append(FloatingText("ЧЕКПОИНТ  +200", checkpoint.x, checkpoint.y - 25, GOLD))
                self.burst(checkpoint.centerx, checkpoint.centery, GOLD, 18)

    def collect_coins(self):
        left = []
        for coin in self.coin_rects:
            if self.player.rect.colliderect(coin):
                self.coins += 1
                self.score += 100
                self.floating.append(FloatingText("+100", coin.centerx, coin.y, GOLD))
                self.burst(coin.centerx, coin.centery, GOLD, 12, gravity=0)
            else:
                left.append(coin)
        self.coin_rects = left

    def update(self, dt):
        self.time += dt
        self.shake = max(0, self.shake - 22 * dt)
        if self.state != "playing":
            self.particles = [p for p in self.particles if p.update(dt)]
            self.floating = [f for f in self.floating if f.update(dt)]
            return
        for moving in self.moving_platforms:
            moving.update(dt)
        keys = pygame.key.get_pressed()
        self.player.update(dt, keys)
        for enemy in self.enemies:
            enemy.update(dt)
        self.update_checkpoint()
        self.collect_coins()
        self.particles = [p for p in self.particles if p.update(dt)]
        self.floating = [f for f in self.floating if f.update(dt)]
        self.score += dt * 10
        self.camera_x = clamp(self.player.rect.centerx - WIDTH // 2, 0, self.level_width - WIDTH)
        if self.player.rect.x > 4450:
            self.state = "victory"
            self.best_score = max(self.best_score, int(self.score))
            save_best(self.best_score)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.state in ("playing", "paused", "settings", "victory"):
                    self.state = "menu"
            elif self.state == "playing":
                if event.key == pygame.K_p:
                    self.state = "paused"
                elif event.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                    self.player.jump_buffer = .14
                elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                    self.player.dash()
            elif self.state == "paused" and event.key in (pygame.K_p, pygame.K_ESCAPE):
                self.state = "playing"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.state == "menu":
                if self.menu_buttons[0].rect.collidepoint(pos): self.start_game()
                elif self.menu_buttons[1].rect.collidepoint(pos): self.state = "settings"
                elif self.menu_buttons[2].rect.collidepoint(pos): pygame.quit(); sys.exit()
            elif self.state == "settings":
                if self.settings_buttons[0].rect.collidepoint(pos):
                    names = list(DIFFICULTIES); self.difficulty = names[(names.index(self.difficulty) + 1) % len(names)]
                elif self.settings_buttons[1].rect.collidepoint(pos): self.state = "menu"
            elif self.state == "victory": self.state = "menu"

    def draw_background(self):
        for y in range(HEIGHT):
            ratio = y / HEIGHT
            color = (int(SKY[0] + ratio * 25), int(SKY[1] + ratio * 25), int(SKY[2] + ratio * 38))
            pygame.draw.line(screen, color, (0, y), (WIDTH, y))
        # Луна и параллакс-слои создают ощущение движ��ния.
        moon_x = int(850 - self.camera_x * .08)
        pygame.draw.circle(screen, (240, 230, 175), (moon_x, 100), 55)
        for layer, color, base in [(.12, (35, 45, 78), 460), (.25, (28, 38, 66), 500)]:
            points = []
            for x in range(-100, WIDTH + 150, 170):
                world_x = x + self.camera_x * layer
                points.extend([(x, int(base - 180 * math.sin(world_x / 210) - 55 * math.sin(world_x / 85)),)])
            pygame.draw.polygon(screen, color, [(0, HEIGHT)] + points + [(WIDTH, HEIGHT)])
        # Звёзды слегка мерцают.
        random.seed(22)
        for _ in range(45):
            x = (random.randint(0, WIDTH) - int(self.camera_x * .04)) % WIDTH
            y = random.randint(35, 280)
            brightness = 130 + int(80 * (math.sin(self.time * 2 + x) + 1) / 2)
            pygame.draw.circle(screen, (brightness, brightness, 210), (x, y), 1)
        random.seed()

    def draw_level(self):
        self.draw_background()
        for platform in self.platforms:
            r = platform.copy(); r.x -= int(self.camera_x)
            if r.right < 0 or r.left > WIDTH: continue
            pygame.draw.rect(screen, DARK_GRAY, r, border_radius=5)
            pygame.draw.rect(screen, GREEN, (r.x, r.y, r.width, 8), border_radius=4)
        for hazard in self.hazards:
            r = hazard.copy(); r.x -= int(self.camera_x)
            for x in range(r.left, r.right, 18):
                pygame.draw.polygon(screen, RED, [(x, r.bottom), (x + 9, r.top), (x + 18, r.bottom)])
        for checkpoint in self.checkpoints:
            x = checkpoint.x - self.camera_x
            pygame.draw.line(screen, WHITE, (x + 15, checkpoint.y), (x + 15, checkpoint.y + 50), 4)
            pygame.draw.polygon(screen, GOLD, [(x + 17, checkpoint.y), (x + 55, checkpoint.y + 14), (x + 17, checkpoint.y + 28)])
        for coin in self.coin_rects:
            r = coin.copy(); r.x -= int(self.camera_x)
            pulse = int(2 * math.sin(self.time * 6 + coin.x))
            pygame.draw.circle(screen, GOLD, r.center, 14 + pulse)
            pygame.draw.circle(screen, (255, 245, 160), r.center, 7)
        for enemy in self.enemies: enemy.draw(self.camera_x)
        self.player.draw(self.camera_x)
        for particle in self.particles: particle.draw(self.camera_x)
        for text in self.floating: text.draw(self.camera_x)
        finish_x = 4450 - self.camera_x
        pygame.draw.line(screen, WHITE, (finish_x, 350), (finish_x, 540), 5)
        draw_text("ФИНИШ", font_small, GOLD, finish_x, 320)
        # HUD panel.
        pygame.draw.rect(screen, (8, 10, 20, 180), (12, 12, 300, 106), border_radius=10)
        pygame.draw.rect(screen, BLACK, (25, 25, 180, 15)); pygame.draw.rect(screen, RED, (25, 25, int(180 * max(self.player.health, 0) / self.player.max_health), 15))
        pygame.draw.rect(screen, WHITE, (25, 25, 180, 15), 2)
        draw_text(f"Счёт: {int(self.score)}", font_small, WHITE, 25, 48, False)
        draw_text(f"Монеты: {self.coins}   Лучший: {self.best_score}", font_small, GOLD, 25, 77, False)
        draw_text("A/D — ходьба   SPACE — прыжок   F — удар", font_tiny, WHITE, WIDTH - 390, 18, False)
        draw_text("SHIFT — рывок   P — пауза", font_tiny, WHITE, WIDTH - 250, 42, False)

    def draw_menu(self):
        self.draw_background(); draw_text("SHADOW PARKOUR", font_title, WHITE, WIDTH // 2, 135)
        draw_text("Живой платформер без обязательных текстур", font_medium, BLUE, WIDTH // 2, 205)
        for button in self.menu_buttons: button.update(pygame.mouse.get_pos()); button.draw()
        draw_text(f"Сложность: {self.difficulty}     Лучший счёт: {self.best_score}", font_small, GRAY, WIDTH // 2, 525)

    def draw_settings(self):
        self.draw_background(); draw_text("НАСТРОЙКИ", font_title, WHITE, WIDTH // 2, 145)
        for button in self.settings_buttons: button.update(pygame.mouse.get_pos()); button.draw()
        draw_text(f"Текущая сложность: {self.difficulty}", font_medium, GOLD, WIDTH // 2, 455)
        draw_text("Прыжок можно сделать дважды, SHIFT — рывок", font_small, GRAY, WIDTH // 2, 505)

    def draw_pause(self):
        self.draw_level(); overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); overlay.fill((0, 0, 0, 175)); screen.blit(overlay, (0, 0))
        draw_text("ПАУЗА", font_title, WHITE, WIDTH // 2, 250); draw_text("P — продолжить   ESC — меню", font_medium, GRAY, WIDTH // 2, 350)

    def draw_victory(self):
        self.draw_background(); draw_text("ПОБЕДА!", font_title, GOLD, WIDTH // 2, 180)
        draw_text("Ты прошёл весь уровень", font_big, WHITE, WIDTH // 2, 275)
        draw_text(f"Счёт: {int(self.score)}    Монет: {self.coins}", font_medium, GOLD, WIDTH // 2, 360)
        draw_text(f"Рекорд: {self.best_score}", font_medium, WHITE, WIDTH // 2, 405)
        draw_text("Нажми мышкой или ESC, чтобы вернуться в меню", font_small, GRAY, WIDTH // 2, 490)

    def draw(self):
        # Небольшая тряска камеры только при попаданиях/рывке.
        offset = (random.randint(-int(self.shake), int(self.shake)), random.randint(-int(self.shake), int(self.shake))) if self.shake > 0 else (0, 0)
        if offset != (0, 0):
            canvas = pygame.Surface((WIDTH, HEIGHT)); canvas.blit(screen, offset)
        if self.state == "menu": self.draw_menu()
        elif self.state == "settings": self.draw_settings()
        elif self.state in ("playing", "paused"): self.draw_pause() if self.state == "paused" else self.draw_level()
        elif self.state == "victory": self.draw_victory()


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
