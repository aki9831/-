from pathlib import Path
import random
import sys
import pygame


# ============================================================
# ОСНОВНЫЕ НАСТРОЙКИ
# ============================================================

pygame.init()

WIDTH = 1100
HEIGHT = 650
FPS = 60

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Shadow Parkour")

clock = pygame.time.Clock()

BASE_DIR = Path(__file__).resolve().parent
TEXTURES_DIR = BASE_DIR / "textures"
SOUNDS_DIR = BASE_DIR / "sounds"

TEXTURES_DIR.mkdir(exist_ok=True)
SOUNDS_DIR.mkdir(exist_ok=True)


# ============================================================
# ЦВЕТА
# ============================================================

WHITE = (245, 245, 245)
BLACK = (10, 12, 20)
GRAY = (150, 160, 180)
DARK_GRAY = (35, 40, 58)

SKY = (25, 30, 58)
SKY_LIGHT = (55, 70, 120)

GREEN = (70, 180, 100)
RED = (210, 65, 75)
PURPLE = (145, 75, 190)
GOLD = (255, 210, 70)
BLUE = (75, 150, 240)
ORANGE = (240, 135, 55)


# ============================================================
# ШРИФТЫ
# ============================================================

font_title = pygame.font.SysFont("arial", 72, bold=True)
font_big = pygame.font.SysFont("arial", 44, bold=True)
font_medium = pygame.font.SysFont("arial", 28, bold=True)
font_small = pygame.font.SysFont("arial", 21)


# ============================================================
# НАСТРОЙКИ СЛОЖНОСТИ
# ============================================================

DIFFICULTIES = {
    "Легко": {
        "player_speed": 270,
        "jump_power": 800,
        "enemy_speed": 65,
        "enemy_damage": 8,
        "player_health": 150,
    },
    "Средне": {
        "player_speed": 300,
        "jump_power": 850,
        "enemy_speed": 85,
        "enemy_damage": 14,
        "player_health": 100,
    },
    "Сложно": {
        "player_speed": 330,
        "jump_power": 900,
        "enemy_speed": 110,
        "enemy_damage": 22,
        "player_health": 75,
    },
}


# ============================================================
# ЗАГРУЗКА ТЕКСТУР
# ============================================================

def fallback_surface(size, color, label=""):
    """
    Создаёт картинку-заглушку, если текстуры нет.
    """
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill(color)

    pygame.draw.rect(
        surface,
        BLACK,
        surface.get_rect(),
        width=3,
    )

    # Диагональные полосы на заглушке.
    for x in range(-surface.get_height(), surface.get_width(), 16):
        pygame.draw.line(
            surface,
            (255, 255, 255, 45),
            (x, 0),
            (x + surface.get_height(), surface.get_height()),
            2,
        )

    if label:
        label_font = pygame.font.SysFont("arial", 12, bold=True)
        text = label_font.render(label, True, WHITE)
        text_rect = text.get_rect(center=surface.get_rect().center)
        surface.blit(text, text_rect)

    return surface


def load_image(filename, size, color, label):
    """
    Загружает обычную текстуру.
    При ошибке возвращает заглушку.
    """
    path = TEXTURES_DIR / filename

    try:
        image = pygame.image.load(str(path)).convert_alpha()
        return pygame.transform.smoothscale(image, size)
    except (pygame.error, FileNotFoundError, OSError):
        print(f"Нет текстуры: {path}")
        return fallback_surface(size, color, label)


def load_sheet(filename, frame_size, color, label, frame_count=4):
    """
    Загружает длинную горизонтальную картинку-анимацию.

    Например:
    player_sheet.png = 4 кадра по 64x80,
    итоговый размер картинки = 256x80.
    """
    path = TEXTURES_DIR / filename
    frames = []

    try:
        image = pygame.image.load(str(path)).convert_alpha()

        for index in range(frame_count):
            source_rect = pygame.Rect(
                index * frame_size[0],
                0,
                frame_size[0],
                frame_size[1],
            )

            if source_rect.right <= image.get_width():
                frame = image.subsurface(source_rect).copy()
                frame = pygame.transform.smoothscale(frame, frame_size)
                frames.append(frame)

        if not frames:
            raise pygame.error("В sprite-sheet нет кадров")

        print(f"Анимация загружена: {path}")
        return frames

    except (pygame.error, FileNotFoundError, OSError):
        print(f"Нет анимации: {path}")

        for index in range(frame_count):
            frame = fallback_surface(
                frame_size,
                color,
                f"{label} {index + 1}",
            )
            frames.append(frame)

        return frames


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def draw_text(text, font, color, x, y, center=True):
    image = font.render(text, True, color)
    rect = image.get_rect()

    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)

    screen.blit(image, rect)


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


# ============================================================
# КНОПКА МЕНЮ
# ============================================================

class Button:
    def __init__(self, rect, text):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.hovered = False

    def update(self, mouse_position):
        self.hovered = self.rect.collidepoint(mouse_position)

    def draw(self):
        if self.hovered:
            color = BLUE
        else:
            color = DARK_GRAY

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


# ============================================================
# ИГРОК
# ============================================================

class Player:
    def __init__(self, game):
        self.game = game

        self.width = 58
        self.height = 82

        self.rect = pygame.Rect(
            150,
            350,
            self.width,
            self.height,
        )

        self.x = float(self.rect.x)
        self.y = float(self.rect.y)

        self.velocity_x = 0
        self.velocity_y = 0

        self.direction = 1
        self.on_ground = False

        self.health = 100
        self.max_health = 100

        self.attack_timer = 0
        self.attack_cooldown = 0

        self.animation_time = 0
        self.animation_frame = 0

        self.frames_idle = load_sheet(
            "player_idle.png",
            (self.width, self.height),
            BLUE,
            "IDLE",
            4,
        )

        self.frames_run = load_sheet(
            "player_run.png",
            (self.width, self.height),
            GREEN,
            "RUN",
            6,
        )

        self.frames_jump = load_sheet(
            "player_jump.png",
            (self.width, self.height),
            ORANGE,
            "JUMP",
            2,
        )

        self.frames_attack = load_sheet(
            "player_attack.png",
            (self.width, self.height),
            RED,
            "ATTACK",
            4,
        )

    def reset(self, position):
        self.x = float(position[0])
        self.y = float(position[1])

        self.rect.topleft = position

        self.velocity_x = 0
        self.velocity_y = 0

        self.health = self.max_health
        self.attack_timer = 0
        self.attack_cooldown = 0

    def get_attack_rect(self):
        if self.direction > 0:
            return pygame.Rect(
                self.rect.right,
                self.rect.y + 18,
                55,
                42,
            )

        return pygame.Rect(
            self.rect.left - 55,
            self.rect.y + 18,
            55,
            42,
        )

    def attack(self):
        if self.attack_cooldown > 0:
            return

        self.attack_timer = 0.25
        self.attack_cooldown = 0.42

        attack_rect = self.get_attack_rect()

        for enemy in self.game.enemies:
            if enemy.alive and attack_rect.colliderect(enemy.rect):
                enemy.take_damage(35)

    def update(self, dt, keys):
        difficulty = DIFFICULTIES[self.game.difficulty]

        self.attack_cooldown = max(0, self.attack_cooldown - dt)
        self.attack_timer = max(0, self.attack_timer - dt)

        moving = False

        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.velocity_x = -difficulty["player_speed"]
            self.direction = -1
            moving = True

        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.velocity_x = difficulty["player_speed"]
            self.direction = 1
            moving = True

        else:
            self.velocity_x = 0

        if keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]:
            if self.on_ground:
                self.velocity_y = -difficulty["jump_power"]
                self.on_ground = False

        if keys[pygame.K_f] or keys[pygame.K_j]:
            self.attack()

        self.velocity_y += 1900 * dt

        self.x += self.velocity_x * dt
        self.y += self.velocity_y * dt

        self.rect.x = int(self.x)
        self.rect.y = int(self.y)

        self.on_ground = False

        # Столкновение с платформами сверху.
        for platform in self.game.platforms:
            if self.rect.colliderect(platform) and self.velocity_y >= 0:
                previous_bottom = self.rect.bottom - int(self.velocity_y * dt)

                if previous_bottom <= platform.top + 20:
                    self.rect.bottom = platform.top
                    self.y = float(self.rect.y)
                    self.velocity_y = 0
                    self.on_ground = True

        # Ограничение выхода за границы уровня.
        self.rect.left = max(self.rect.left, 0)
        self.x = float(self.rect.x)

        # Урон от врагов.
        for enemy in self.game.enemies:
            if enemy.alive and self.rect.colliderect(enemy.rect):
                self.take_damage(enemy.damage * dt)

        # Падение.
        if self.rect.top > self.game.level_height + 300:
            self.game.respawn_player()

        # Анимация.
        if self.attack_timer > 0:
            frames = self.frames_attack
            animation_speed = 12
        elif not self.on_ground:
            frames = self.frames_jump
            animation_speed = 5
        elif moving:
            frames = self.frames_run
            animation_speed = 10
        else:
            frames = self.frames_idle
            animation_speed = 5

        self.animation_time += dt * animation_speed
        self.animation_frame = int(self.animation_time) % len(frames)

    def take_damage(self, amount):
        self.health -= amount

        if self.health <= 0:
            self.game.respawn_player()

    def draw(self, camera_x):
        if self.direction < 0:
            image = pygame.transform.flip(
                self.get_current_frame(),
                True,
                False,
            )
        else:
            image = self.get_current_frame()

        screen.blit(
            image,
            (
                self.rect.x - camera_x,
                self.rect.y,
            ),
        )

        # Полоса здоровья.
        bar_width = 180
        bar_height = 15

        pygame.draw.rect(
            screen,
            BLACK,
            (20, 20, bar_width, bar_height),
        )

        health_width = int(
            bar_width * self.health / self.max_health
        )

        pygame.draw.rect(
            screen,
            RED,
            (20, 20, health_width, bar_height),
        )

        pygame.draw.rect(
            screen,
            WHITE,
            (20, 20, bar_width, bar_height),
            width=2,
        )

    def get_current_frame(self):
        if self.attack_timer > 0:
            return self.frames_attack[self.animation_frame]

        if not self.on_ground:
            return self.frames_jump[self.animation_frame]

        if self.velocity_x != 0:
            return self.frames_run[self.animation_frame]

        return self.frames_idle[self.animation_frame]


# ============================================================
# ВРАГ
# ============================================================

class Enemy:
    def __init__(self, game, x, y, enemy_type):
        self.game = game
        self.enemy_type = enemy_type

        self.width = 58
        self.height = 78

        self.rect = pygame.Rect(
            x,
            y,
            self.width,
            self.height,
        )

        self.x = float(x)
        self.y = float(y)

        self.health = 60 if enemy_type == "zombie" else 45
        self.damage = (
            DIFFICULTIES[game.difficulty]["enemy_damage"]
            if enemy_type == "zombie"
            else DIFFICULTIES[game.difficulty]["enemy_damage"] * 1.4
        )

        self.alive = True
        self.direction = -1
        self.animation_time = 0
        self.animation_frame = 0

        if enemy_type == "zombie":
            self.frames = load_sheet(
                "zombie_sheet.png",
                (self.width, self.height),
                GREEN,
                "ZOMBIE",
                4,
            )
        else:
            self.frames = load_sheet(
                "vampire_sheet.png",
                (self.width, self.height),
                PURPLE,
                "VAMPIRE",
                4,
            )

    def take_damage(self, amount):
        self.health -= amount

        if self.health <= 0:
            self.alive = False

    def update(self, dt):
        if not self.alive:
            return

        player = self.game.player
        difficulty = DIFFICULTIES[self.game.difficulty]

        distance = player.rect.centerx - self.rect.centerx

        detection_range = 420

        if abs(distance) < detection_range:
            if distance > 10:
                self.direction = 1
                self.x += difficulty["enemy_speed"] * dt

            elif distance < -10:
                self.direction = -1
                self.x -= difficulty["enemy_speed"] * dt

        self.rect.x = int(self.x)

        # Враг не проваливается сквозь платформы.
        for platform in self.game.platforms:
            if self.rect.colliderect(platform):
                if self.rect.bottom <= platform.top + 30:
                    self.rect.bottom = platform.top
                    self.y = float(self.rect.y)

        self.animation_time += dt * 7
        self.animation_frame = int(self.animation_time) % len(self.frames)

    def draw(self, camera_x):
        if not self.alive:
            return

        image = self.frames[self.animation_frame]

        if self.direction < 0:
            image = pygame.transform.flip(
                image,
                True,
                False,
            )

        screen.blit(
            image,
            (
                self.rect.x - camera_x,
                self.rect.y,
            ),
        )

        # Полоса здоровья врага.
        pygame.draw.rect(
            screen,
            BLACK,
            (
                self.rect.x - camera_x,
                self.rect.y - 12,
                self.rect.width,
                7,
            ),
        )

        pygame.draw.rect(
            screen,
            RED,
            (
                self.rect.x - camera_x,
                self.rect.y - 12,
                int(self.rect.width * max(self.health, 0) / 60),
                7,
            ),
        )


# ============================================================
# ИГРА
# ============================================================

class Game:
    def __init__(self):
        self.state = "menu"
        self.difficulty = "Средне"

        self.level_width = 4200
        self.level_height = 600

        self.camera_x = 0
        self.score = 0
        self.coins = 0

        self.checkpoint_position = (150, 350)

        self.menu_buttons = [
            Button((400, 280, 300, 58), "Начать игру"),
            Button((400, 350, 300, 58), "Настройки"),
            Button((400, 420, 300, 58), "Выход"),
        ]

        self.settings_buttons = [
            Button((400, 280, 300, 58), "Сложность"),
            Button((400, 350, 300, 58), "Назад"),
        ]

        self.player = Player(self)

        self.platforms = []
        self.enemies = []
        self.checkpoints = []
        self.coin_rects = []

        self.create_level()

    def create_level(self):
        self.platforms = [
            pygame.Rect(0, 540, 700, 110),
            pygame.Rect(850, 540, 550, 110),
            pygame.Rect(1550, 540, 650, 110),
            pygame.Rect(2350, 540, 550, 110),
            pygame.Rect(3050, 540, 550, 110),
            pygame.Rect(3750, 540, 700, 110),

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
        ]

        self.enemies = [
            Enemy(self, 570, 462, "zombie"),
            Enemy(self, 1080, 312, "vampire"),
            Enemy(self, 1250, 222, "zombie"),
            Enemy(self, 1800, 332, "vampire"),
            Enemy(self, 2150, 242, "zombie"),
            Enemy(self, 2600, 342, "vampire"),
            Enemy(self, 3280, 332, "zombie"),
            Enemy(self, 3550, 222, "vampire"),
            Enemy(self, 3980, 312, "zombie"),
        ]

    def start_game(self):
        self.state = "playing"
        self.score = 0
        self.coins = 0
        self.camera_x = 0
        self.checkpoint_position = (150, 350)

        self.player.max_health = DIFFICULTIES[
            self.difficulty
        ]["player_health"]

        self.player.reset(self.checkpoint_position)

        self.create_level()

    def respawn_player(self):
        self.player.reset(self.checkpoint_position)

    def update_checkpoint(self):
        for checkpoint in self.checkpoints:
            if self.player.rect.colliderect(checkpoint):
                if checkpoint.x > self.checkpoint_position[0]:
                    self.checkpoint_position = (
                        checkpoint.x,
                        checkpoint.y - self.player.height,
                    )

    def collect_coins(self):
        remaining = []

        for coin in self.coin_rects:
            if self.player.rect.colliderect(coin):
                self.coins += 1
                self.score += 100
            else:
                remaining.append(coin)

        self.coin_rects = remaining

    def update(self, dt):
        if self.state != "playing":
            return

        keys = pygame.key.get_pressed()

        self.player.update(dt, keys)

        for enemy in self.enemies:
            enemy.update(dt)

        self.update_checkpoint()
        self.collect_coins()

        self.score += dt * 10

        target_camera = self.player.rect.centerx - WIDTH // 2
        self.camera_x = clamp(
            target_camera,
            0,
            self.level_width - WIDTH,
        )

        # Финиш уровня.
        if self.player.rect.x > 4250:
            self.state = "victory"

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.state == "playing":
                    self.state = "menu"
                elif self.state in ("settings", "victory"):
                    self.state = "menu"

            if self.state == "playing":
                if event.key == pygame.K_p:
                    self.state = "paused"

            elif self.state == "paused":
                if event.key == pygame.K_p:
                    self.state = "playing"

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button != 1:
                return

            mouse_position = event.pos

            if self.state == "menu":
                if self.menu_buttons[0].rect.collidepoint(mouse_position):
                    self.start_game()

                elif self.menu_buttons[1].rect.collidepoint(mouse_position):
                    self.state = "settings"

                elif self.menu_buttons[2].rect.collidepoint(mouse_position):
                    pygame.quit()
                    sys.exit()

            elif self.state == "settings":
                if self.settings_buttons[0].rect.collidepoint(mouse_position):
                    names = list(DIFFICULTIES.keys())
                    index = names.index(self.difficulty)
                    self.difficulty = names[
                        (index + 1) % len(names)
                    ]

                elif self.settings_buttons[1].rect.collidepoint(mouse_position):
                    self.state = "menu"

            elif self.state == "victory":
                self.state = "menu"

    # ========================================================
    # ОТРИСОВКА
    # ========================================================

    def draw_background(self):
        screen.fill(SKY)

        # Градиентный эффект полосами.
        for y in range(HEIGHT):
            ratio = y / HEIGHT
            color = (
                int(SKY[0] + ratio * 20),
                int(SKY[1] + ratio * 20),
                int(SKY[2] + ratio * 35),
            )
            pygame.draw.line(
                screen,
                color,
                (0, y),
                (WIDTH, y),
            )

        # Луна.
        pygame.draw.circle(
            screen,
            (240, 230, 175),
            (850, 100),
            55,
        )

        # Дальние горы.
        mountains = [
            (0, 460),
            (170, 270),
            (330, 460),
            (500, 300),
            (700, 460),
            (860, 260),
            (1100, 460),
        ]

        pygame.draw.polygon(
            screen,
            (35, 45, 78),
            mountains,
        )

    def draw_level(self):
        self.draw_background()

        # Платформы.
        for platform in self.platforms:
            draw_rect = platform.copy()
            draw_rect.x -= self.camera_x

            if draw_rect.right < 0 or draw_rect.left > WIDTH:
                continue

            pygame.draw.rect(
                screen,
                DARK_GRAY,
                draw_rect,
                border_radius=5,
            )

            pygame.draw.rect(
                screen,
                GREEN,
                (
                    draw_rect.x,
                    draw_rect.y,
                    draw_rect.width,
                    9,
                ),
                border_radius=4,
            )

        # Чекпоинты.
        for checkpoint in self.checkpoints:
            x = checkpoint.x - self.camera_x

            pygame.draw.line(
                screen,
                WHITE,
                (x + 15, checkpoint.y),
                (x + 15, checkpoint.y + 50),
                4,
            )

            pygame.draw.polygon(
                screen,
                GOLD,
                [
                    (x + 17, checkpoint.y),
                    (x + 55, checkpoint.y + 14),
                    (x + 17, checkpoint.y + 28),
                ],
            )

        # Монеты.
        for coin in self.coin_rects:
            draw_rect = coin.copy()
            draw_rect.x -= self.camera_x

            pygame.draw.circle(
                screen,
                GOLD,
                draw_rect.center,
                14,
            )

            pygame.draw.circle(
                screen,
                (255, 245, 160),
                draw_rect.center,
                7,
            )

        for enemy in self.enemies:
            enemy.draw(self.camera_x)

        self.player.draw(self.camera_x)

        # Финиш.
        finish_x = 4250 - self.camera_x

        pygame.draw.line(
            screen,
            WHITE,
            (finish_x, 400),
            (finish_x, 540),
            5,
        )

        draw_text(
            "ФИНИШ",
            font_small,
            GOLD,
            finish_x,
            370,
        )

        # HUD.
        draw_text(
            f"Счёт: {int(self.score)}",
            font_small,
            WHITE,
            20,
            48,
            center=False,
        )

        draw_text(
            f"Монеты: {self.coins}",
            font_small,
            GOLD,
            20,
            78,
            center=False,
        )

        draw_text(
            "A/D или стрелки — движение",
            font_small,
            WHITE,
            WIDTH - 300,
            20,
            center=False,
        )

        draw_text(
            "SPACE — прыжок   F — атака   P — пауза",
            font_small,
            WHITE,
            WIDTH - 430,
            48,
            center=False,
        )

    def draw_menu(self):
        self.draw_background()

        draw_text(
            "SHADOW PARKOUR",
            font_title,
            WHITE,
            WIDTH // 2,
            145,
        )

        draw_text(
            "Платформер с монстрами",
            font_medium,
            BLUE,
            WIDTH // 2,
            210,
        )

        mouse_position = pygame.mouse.get_pos()

        for button in self.menu_buttons:
            button.update(mouse_position)
            button.draw()

        draw_text(
            f"Сложность: {self.difficulty}",
            font_small,
            GRAY,
            WIDTH // 2,
            530,
        )

    def draw_settings(self):
        self.draw_background()

        draw_text(
            "НАСТРОЙКИ",
            font_title,
            WHITE,
            WIDTH // 2,
            150,
        )

        mouse_position = pygame.mouse.get_pos()

        for button in self.settings_buttons:
            button.update(mouse_position)
            button.draw()

        draw_text(
            f"Текущая сложность: {self.difficulty}",
            font_medium,
            GOLD,
            WIDTH // 2,
            470,
        )

        draw_text(
            "Нажимай кнопку «Сложность», чтобы переключать режимы",
            font_small,
            GRAY,
            WIDTH // 2,
            520,
        )

    def draw_pause(self):
        self.draw_level()

        overlay = pygame.Surface(
            (WIDTH, HEIGHT),
            pygame.SRCALPHA,
        )
        overlay.fill((0, 0, 0, 170))
        screen.blit(overlay, (0, 0))

        draw_text(
            "ПАУЗА",
            font_title,
            WHITE,
            WIDTH // 2,
            250,
        )

        draw_text(
            "P — продолжить",
            font_medium,
            GRAY,
            WIDTH // 2,
            350,
        )

    def draw_victory(self):
        self.draw_background()

        draw_text(
            "ПОБЕДА!",
            font_title,
            GOLD,
            WIDTH // 2,
            190,
        )

        draw_text(
            "Ты прошёл весь уровень",
            font_big,
            WHITE,
            WIDTH // 2,
            285,
        )

        draw_text(
            f"Счёт: {int(self.score)}",
            font_medium,
            WHITE,
            WIDTH // 2,
            355,
        )

        draw_text(
            f"Монет собрано: {self.coins}",
            font_medium,
            GOLD,
            WIDTH // 2,
            400,
        )

        draw_text(
            "Нажми мышкой, чтобы вернуться в меню",
            font_small,
            GRAY,
            WIDTH // 2,
            490,
        )

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
        dt = min(clock.tick(FPS) / 1000, 0.05)

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
