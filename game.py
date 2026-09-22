import math
import random
import sys
import json
from pathlib import Path

import pygame

from assets import (
    WIDTH, HEIGHT, FPS,
    BLACK, WHITE, BLUE, GREEN, RED, GOLD, PURPLE, CYAN,
    ORANGE, DARK_GRAY, SKY, GRAY, PINK, TEAL,
    clamp, draw_text, fallback_surface,
    SoundManager
)

# ============================================================
# НАСТРОЙКИ ИГРЫ
# ============================================================

SAVE_FILE = Path(__file__).resolve().parent / "save.json"

def load_best():
    try:
        data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        return int(data.get("best", 0))
    except Exception:
        return 0

def save_best(value):
    try:
        SAVE_FILE.write_text(json.dumps({"best": int(value)}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

# ============================================================
# КЛАССЫ ЭФФЕКТОВ И КНОПОК
# ============================================================

class Particle:
    def __init__(self, x, y, color, life=0.5, speed=120, gravity=260):
        angle = random.uniform(0, math.tau)
        velocity = random.uniform(speed * 0.4, speed)
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * velocity
        self.vy = math.sin(angle) * velocity
        self.color = color
        self.life = self.max_life = life
        self.gravity = gravity
        self.size = random.randint(2, 6)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += self.gravity * dt
        self.life -= dt
        return self.life > 0

    def draw(self, camera_x, screen):
        radius = max(1, int(self.size * self.life / self.max_life))
        pygame.draw.circle(screen, self.color, (int(self.x - camera_x), int(self.y)), radius)


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

    def draw(self, camera_x, screen, font):
        image = font.render(self.text, True, self.color)
        image.set_alpha(int(255 * clamp(self.life, 0, 1)))
        screen.blit(image, image.get_rect(center=(self.x - camera_x, self.y)))


class Button:
    def __init__(self, rect, text, color=BLUE, hover_color=CYAN):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.hovered = False

    def update(self, mouse_pos):
        self.hovered = self.rect.collidepoint(mouse_pos)

    def draw(self, screen, font):
        color = self.hover_color if self.hovered else self.color
        pygame.draw.rect(screen, color, self.rect, border_radius=12)
        pygame.draw.rect(screen, WHITE, self.rect, width=2, border_radius=12)
        draw_text(self.text, font, WHITE, self.rect.centerx, self.rect.centery, center=True)


# ============================================================
# ХАРАКТЕРЫ
# ============================================================

CHARACTER_PRESETS = {
    "Knight": {"speed": 320, "jump": 860, "health": 165, "attack": 42, "dash": 1000},
    "Ranger": {"speed": 350, "jump": 820, "health": 130, "attack": 36, "dash": 1080},
    "Mage":   {"speed": 300, "jump": 900, "health": 120, "attack": 55, "dash": 1020},
}

# ============================================================
# ИГРОК
# ============================================================

class Player:
    def __init__(self, game, character_name):
        self.game = game
        self.character_name = character_name
        preset = CHARACTER_PRESETS[character_name]
        self.width = 58
        self.height = 82
        self.speed = preset["speed"]
        self.jump_power = preset["jump"]
        self.max_health = preset["health"]
        self.health = self.max_health
        self.attack_damage = preset["attack"]
        self.dash_speed = preset["dash"]
        self.rect = pygame.Rect(150, 350, self.width, self.height)
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.coyote_time = 0.0
        self.jump_buffer = 0.0
        self.double_jump = True
        self.jump_count = 0
        self.direction = 1
        self.invulnerability = 0.0
        self.attack_timer = 0.0
        self.attack_cooldown = 0.0
        self.dash_timer = 0.0
        self.dash_cooldown = 0.0
        self.ranged_cooldown = 0.0
        self.slide_timer = 0.0
        self.stamina = 100.0
        self.max_stamina = 100.0
        self.animation_time = 0.0
        self.frame = 0

        self.name_color = {
            "Knight": BLUE,
            "Ranger": GREEN,
            "Mage": PURPLE
        }[character_name]

    def reset(self, position):
        self.x = float(position[0])
        self.y = float(position[1])
        self.rect.topleft = position
        self.vx = 0.0
        self.vy = 0.0
        self.health = self.max_health
        self.stamina = self.max_stamina
        self.invulnerability = 0.8
        self.double_jump = True
        self.jump_count = 0
        self.attack_timer = 0.0
        self.attack_cooldown = 0.0
        self.dash_timer = 0.0
        self.dash_cooldown = 0.0
        self.ranged_cooldown = 0.0
        self.slide_timer = 0.0

    def jump_action(self):
        if self.on_ground or self.coyote_time > 0:
            self.vy = -self.jump_power
            self.on_ground = False
            self.coyote_time = 0.0
            self.jump_count = 1
            self.game.sound.play("jump")
            self.game.burst(self.rect.centerx, self.rect.bottom, CYAN, 10)
            return

        if self.double_jump and self.jump_count < 2:
            self.vy = -self.jump_power * 0.82
            self.double_jump = False
            self.jump_count += 1
            self.game.sound.play("jump")
            self.game.burst(self.rect.centerx, self.rect.centery, ORANGE, 12)

    def melee_attack(self):
        if self.attack_cooldown > 0 or self.stamina < 12:
            return

        self.attack_timer = 0.22
        self.attack_cooldown = 0.32
        self.stamina = max(0, self.stamina - 12)

        hit_rect = pygame.Rect(
            self.rect.right if self.direction > 0 else self.rect.left - 90,
            self.rect.y + 10,
            90,
            52,
        )
        self.game.burst(hit_rect.centerx, hit_rect.centery, GOLD, 7, gravity=0)

        for enemy in self.game.enemies:
            if enemy.alive and hit_rect.colliderect(enemy.rect):
                enemy.take_damage(self.attack_damage + self.game.upgrade_levels.get("melee", 0) * 6)
                self.game.score += 25
                self.game.floating.append(FloatingText("+25", enemy.rect.centerx, enemy.rect.y, GOLD))

        if self.game.boss and self.game.boss.alive and hit_rect.colliderect(self.game.boss.rect):
            self.game.boss.take_damage(self.attack_damage + self.game.upgrade_levels.get("melee", 0) * 6)
            self.game.score += 25

        self.game.sound.play("hit")

    def ranged_attack(self):
        if self.ranged_cooldown > 0 or self.stamina < 18:
            return

        self.ranged_cooldown = 0.36
        self.stamina = max(0, self.stamina - 18)

        vx = self.direction * 520
        vy = 0.0
        self.game.projectiles.append(
            Projectile(
                self.rect.centerx + self.direction * 28,
                self.rect.centery - 8,
                vx, vy,
                PINK,
                self.attack_damage + self.game.upgrade_levels.get("magic", 0) * 8,
                520,
                is_player=True
            )
        )
        self.game.sound.play("shoot")

    def dash(self):
        if self.dash_cooldown > 0 or self.stamina < 20:
            return

        self.dash_timer = 0.12
        self.dash_cooldown = 0.8
        self.stamina = max(0, self.stamina - 20)
        self.vx = self.direction * self.dash_speed
        self.invulnerability = max(self.invulnerability, 0.2)
        self.game.sound.play("dash")
        self.game.shake = max(self.game.shake, 5)
        self.game.burst(self.rect.centerx, self.rect.centery, BLUE, 18, gravity=0)

    def slide(self):
        if self.on_ground and self.slide_timer <= 0 and self.stamina >= 10:
            self.slide_timer = 0.42
            self.stamina = max(0, self.stamina - 10)
            self.vx = self.direction * 430

    def take_damage(self, amount):
        if self.invulnerability > 0:
            return
        self.health -= amount
        self.invulnerability = 0.55
        self.game.shake = max(self.game.shake, 8)
        self.game.sound.play("hurt")

        if self.health <= 0:
            self.game.respawn_player()

    def use_potion(self, kind="health"):
        if kind == "health":
            count = self.game.inventory.get("health_potion", 0)
            if count <= 0:
                return False
            self.game.inventory["health_potion"] -= 1
            self.health = min(self.max_health, self.health + 35)
            self.game.floating.append(FloatingText("+35 HP", self.rect.centerx, self.rect.y, GREEN))
            self.game.sound.play("heal")
            return True

        if kind == "mana":
            count = self.game.inventory.get("mana_potion", 0)
            if count <= 0:
                return False
            self.game.inventory["mana_potion"] -= 1
            self.stamina = min(self.max_stamina, self.stamina + 30)
            self.game.floating.append(FloatingText("+30 MP", self.rect.centerx, self.rect.y, TEAL))
            self.game.sound.play("heal")
            return True

        return False

    def update(self, dt, keys):
        self.invulnerability = max(0, self.invulnerability - dt)
        self.attack_cooldown = max(0, self.attack_cooldown - dt)
        self.attack_timer = max(0, self.attack_timer - dt)
        self.dash_cooldown = max(0, self.dash_cooldown - dt)
        self.dash_timer = max(0, self.dash_timer - dt)
        self.ranged_cooldown = max(0, self.ranged_cooldown - dt)
        self.slide_timer = max(0, self.slide_timer - dt)
        self.coyote_time = max(0, self.coyote_time - dt)
        self.jump_buffer = max(0, self.jump_buffer - dt)
        self.stamina = clamp(self.stamina + dt * 17, 0, self.max_stamina)

        left = keys[pygame.K_a] or keys[pygame.K_LEFT]
        right = keys[pygame.K_d] or keys[pygame.K_RIGHT]

        if self.dash_timer > 0:
            self.vx = self.direction * self.dash_speed
        else:
            if left:
                self.vx = -self.speed
                self.direction = -1
            elif right:
                self.vx = self.speed
                self.direction = 1
            else:
                self.vx *= 0.75 if self.on_ground else 0.92
                if abs(self.vx) < 2:
                    self.vx = 0.0

        if self.slide_timer > 0:
            self.vx = self.direction * 430
            self.rect.height = 58
        else:
            self.rect.height = self.height

        if self.jump_buffer > 0:
            self.jump_action()
            self.jump_buffer = 0.0

        if keys[pygame.K_f] or keys[pygame.K_j]:
            self.melee_attack()
        if keys[pygame.K_k]:
            self.ranged_attack()
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            self.dash()
        if keys[pygame.K_LCTRL] or keys[pygame.K_c]:
            self.slide()

        if keys[pygame.K_1]:
            self.use_potion("health")
        if keys[pygame.K_2]:
            self.use_potion("mana")

        self.vy += 1900 * dt

        old_bottom = self.rect.bottom
        old_left = self.rect.left
        old_right = self.rect.right

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rect.topleft = (int(self.x), int(self.y))
        self.on_ground = False

        for platform in self.game.platforms:
            if self.rect.colliderect(platform):
                if self.vy >= 0 and old_bottom <= platform.top + 8:
                    self.rect.bottom = platform.top
                    self.y = float(self.rect.y)
                    self.vy = 0
                    self.on_ground = True
                    self.double_jump = True
                    self.jump_count = 0
                elif self.vy > 0 and self.rect.bottom > platform.top and self.rect.top < platform.bottom:
                    if old_right <= platform.left + 8 and self.rect.right > platform.left:
                        self.rect.right = platform.left
                        self.x = float(self.rect.x)
                        self.vx = 0
                    elif old_left >= platform.right - 8 and self.rect.left < platform.right:
                        self.rect.left = platform.right
                        self.x = float(self.rect.x)
                        self.vx = 0

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

        for moving_hazard in self.game.moving_hazards:
            if self.rect.colliderect(moving_hazard.rect):
                self.take_damage(28 * dt)

        if self.rect.top > self.game.level_height + 260:
            self.game.respawn_player()

        if self.attack_timer > 0:
            frames = self.game.player_attack_frames
            anim_speed = 12
        elif self.slide_timer > 0:
            frames = self.game.player_slide_frames
            anim_speed = 9
        elif not self.on_ground:
            frames = self.game.player_jump_frames
            anim_speed = 5
        elif self.vx != 0:
            frames = self.game.player_run_frames
            anim_speed = 10
        else:
            frames = self.game.player_idle_frames
            anim_speed = 5

        self.animation_time += dt * anim_speed
        self.frame = int(self.animation_time) % len(frames)

    def draw(self, camera_x, screen, font):
        if self.invulnerability > 0 and int(self.invulnerability * 18) % 2 == 0:
            return

        if self.attack_timer > 0:
            frames = self.game.player_attack_frames
        elif self.slide_timer > 0:
            frames = self.game.player_slide_frames
        elif not self.on_ground:
            frames = self.game.player_jump_frames
        elif self.vx != 0:
            frames = self.game.player_run_frames
        else:
            frames = self.game.player_idle_frames

        image = frames[self.frame]
        if self.direction < 0:
            image = pygame.transform.flip(image, True, False)

        screen.blit(image, (self.rect.x - camera_x, self.rect.y))

        # stamina bar
        bar = pygame.Rect(self.rect.x - camera_x, self.rect.y - 14, self.width, 6)
        pygame.draw.rect(screen, BLACK, bar)
        pygame.draw.rect(screen, TEAL, (bar.x, bar.y, int(bar.width * self.stamina / self.max_stamina), bar.height))


# ============================================================
# ВРАГИ
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
            self.max_health = self.health = 70
            self.damage = 10
            self.speed = 70
            self.frames = [fallback_surface((58, 78), GREEN, "ZOMBIE") for _ in range(4)]
        elif enemy_type == "vampire":
            self.max_health = self.health = 55
            self.damage = 13
            self.speed = 85
            self.frames = [fallback_surface((58, 78), PURPLE, "VAMP") for _ in range(4)]
        elif enemy_type == "brute":
            self.max_health = self.health = 110
            self.damage = 16
            self.speed = 62
            self.frames = [fallback_surface((58, 78), ORANGE, "BRUTE") for _ in range(4)]
        else:
            self.max_health = self.health = 90
            self.damage = 15
            self.speed = 90
            self.frames = [fallback_surface((58, 78), PINK, "BAT") for _ in range(4)]

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
            self.game.floating.append(FloatingText("+150", self.rect.centerx, self.rect.y, GOLD))
            self.game.burst(self.rect.centerx, self.rect.centery, PURPLE, 22)
            if random.random() < 0.28:
                self.game.pickups.append(Pickup(self.rect.centerx, self.rect.centery, "heal"))

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

    def draw(self, camera_x, screen):
        if not self.alive:
            return

        image = self.frames[self.frame]
        if self.direction < 0:
            image = pygame.transform.flip(image, True, False)
        screen.blit(image, (self.rect.x - camera_x, self.rect.y))

        bar = pygame.Rect(self.rect.x - camera_x, self.rect.y - 12, self.width, 7)
        pygame.draw.rect(screen, BLACK, bar)
        pygame.draw.rect(screen, RED, (bar.x, bar.y, int(bar.width * max(self.health, 0) / self.max_health), bar.height))


# ============================================================
# БОСС
# ============================================================

class Boss:
    def __init__(self, game, x, y):
        self.game = game
        self.x = float(x)
        self.y = float(y)
        self.width = 120
        self.height = 140
        self.rect = pygame.Rect(x, y, self.width, self.height)
        self.max_health = 980
        self.health = self.max_health
        self.damage = 20
        self.speed = 70
        self.alive = True
        self.direction = -1
        self.phase = 1
        self.rage = False
        self.cooldown = 1.2
        self.animation_time = 0
        self.frame = 0
        self.frames = [fallback_surface((120, 140), RED, "BOSS") for _ in range(4)]

    def take_damage(self, amount):
        if not self.alive:
            return

        self.health -= amount
        self.game.burst(self.rect.centerx, self.rect.centery, RED, 12)
        self.game.sound.play("hit")

        if self.health <= self.max_health * 0.6 and self.phase == 1:
            self.phase = 2
            self.rage = True
            self.game.floating.append(FloatingText("ФАЗА 2", self.rect.centerx, self.rect.y - 30, RED))
            self.game.sound.play("boss")

        if self.health <= self.max_health * 0.25 and self.phase == 2:
            self.phase = 3
            self.rage = True
            self.game.floating.append(FloatingText("ФАЗА 3", self.rect.centerx, self.rect.y - 30, PURPLE))
            self.game.sound.play("boss")

        if self.health <= 0:
            self.alive = False
            self.game.score += 2000
            self.game.floating.append(FloatingText("+2000", self.rect.centerx, self.rect.y, GOLD))
            self.game.burst(self.rect.centerx, self.rect.centery, PURPLE, 32)
            self.game.sound.play("victory")
            self.game.completed = True

    def update(self, dt):
        if not self.alive:
            return

        player = self.game.player
        distance = player.rect.centerx - self.rect.centerx
        self.direction = 1 if distance > 0 else -1
        if abs(distance) < 900:
            self.x += self.direction * self.speed * (1.6 if self.rage else 1.0) * dt
            self.rect.x = int(self.x)

        self.cooldown -= dt
        if self.cooldown <= 0 and abs(distance) < 850:
            self.cooldown = 0.8 if self.rage else 1.4

            dx = player.rect.centerx - self.rect.centerx
            dy = player.rect.centery - self.rect.centery
            length = max(1.0, math.hypot(dx, dy))
            vx = (dx / length) * (280 + self.phase * 45)
            vy = (dy / length) * (280 + self.phase * 45)

            self.game.projectiles.append(
                Projectile(
                    self.rect.centerx,
                    self.rect.centery,
                    vx, vy,
                    RED if self.rage else PURPLE,
                    18 + self.phase * 2,
                    260,
                    is_player=False
                )
            )
            self.game.burst(self.rect.centerx, self.rect.centery, RED, 9, gravity=0)
            self.game.sound.play("boss")

        self.animation_time += dt * (10 if self.rage else 5)
        self.frame = int(self.animation_time) % len(self.frames)

    def draw(self, camera_x, screen):
        if not self.alive:
            return

        image = self.frames[self.frame]
        if self.direction < 0:
            image = pygame.transform.flip(image, True, False)
        screen.blit(image, (self.rect.x - camera_x, self.rect.y))

        bar = pygame.Rect(240, 18, 620, 20)
        pygame.draw.rect(screen, BLACK, bar)
        health_width = int(bar.width * max(self.health, 0) / self.max_health)
        color = RED if self.phase <= 2 else PURPLE
        pygame.draw.rect(screen, color, (bar.x, bar.y, health_width, bar.height))
        pygame.draw.rect(screen, WHITE, bar, 2)
        draw_text("ВЛАДЫКА БЕЗДНЫ", self.game.font_small, WHITE, WIDTH // 2, 50)


# ============================================================
# СНАРЯДЫ
# ============================================================

class Projectile:
    def __init__(self, x, y, vx, vy, color, damage, speed, is_player=True):
        self.x = float(x)
        self.y = float(y)
        self.vx = vx
        self.vy = vy
        self.color = color
        self.damage = damage
        self.speed = speed
        self.life = 4.0
        self.is_player = is_player

    def update(self, dt, game):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt

        rect = pygame.Rect(int(self.x - 10), int(self.y - 10), 20, 20)

        if self.is_player:
            for enemy in game.enemies:
                if enemy.alive and rect.colliderect(enemy.rect):
                    enemy.take_damage(self.damage)
                    return False
            if game.boss and game.boss.alive and rect.colliderect(game.boss.rect):
                game.boss.take_damage(self.damage)
                return False
        else:
            if rect.colliderect(game.player.rect):
                game.player.take_damage(self.damage)
                return False

        return (
            self.life > 0
            and -50 < self.x < game.level_width + 50
            and -50 < self.y < HEIGHT + 100
        )

    def draw(self, camera_x, screen):
        pygame.draw.circle(screen, self.color, (int(self.x - camera_x), int(self.y)), 10)
        pygame.draw.circle(screen, WHITE, (int(self.x - camera_x), int(self.y)), 4)


# ============================================================
# ПЛАТФОРМЫ / ЛОВУШКИ / ПОДБОРЫ
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


class MovingHazard:
    def __init__(self, x, y, width, height, distance, speed):
        self.rect = pygame.Rect(x, y, width, height)
        self.start_x = float(x)
        self.distance = distance
        self.speed = speed
        self.time = random.random() * 5.0

    def update(self, dt):
        self.time += dt * self.speed
        self.rect.x = int(self.start_x + math.sin(self.time) * self.distance)


class Pickup:
    def __init__(self, x, y, kind="coin"):
        self.rect = pygame.Rect(x - 12, y - 12, 24, 24)
        self.kind = kind
        self.angle = random.random() * math.tau

    def update(self, dt, game):
        self.angle += dt * 4
        if self.rect.colliderect(game.player.rect):
            if self.kind == "heal":
                game.player.health = min(game.player.max_health, game.player.health + 35)
                game.player.stamina = min(game.player.max_stamina, game.player.stamina + 25)
                game.floating.append(FloatingText("+35 HP", self.rect.centerx, self.rect.y, GREEN))
                game.sound.play("heal")
            elif self.kind == "coin":
                game.coins += 1
                game.score += 150
                game.floating.append(FloatingText("+150", self.rect.centerx, self.rect.y, GOLD))
                game.sound.play("coin")
            return False
        return True

    def draw(self, camera_x, screen):
        x = self.rect.centerx - camera_x
        y = self.rect.centery
        if self.kind == "heal":
            size = 10
            pygame.draw.circle(screen, GREEN, (x, y), size)
            pygame.draw.circle(screen, WHITE, (x, y), size - 3)
        else:
            size = 11 + int(2 * math.sin(self.angle))
            pygame.draw.circle(screen, GOLD, (x, y), size)
            pygame.draw.circle(screen, (255, 245, 160), (x, y), max(5, size - 4))


# ============================================================
# ИГРОВАЯ ЛОГИКА
# ============================================================

class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Shadow Parkour: Nightfall — Deluxe")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.sound = SoundManager()
        self.font_title = pygame.font.SysFont("arial", 72, bold=True)
        self.font_big = pygame.font.SysFont("arial", 44, bold=True)
        self.font_medium = pygame.font.SysFont("arial", 28, bold=True)
        self.font_small = pygame.font.SysFont("arial", 20)
        self.font_tiny = pygame.font.SysFont("arial", 15)

        self.state = "menu"
        self.best_score = load_best()
        self.selected_character = "Knight"
        self.inventory = {"health_potion": 2, "mana_potion": 1, "smoke_bomb": 1}
        self.upgrade_levels = {"speed": 0, "jump": 0, "health": 0, "melee": 0, "magic": 0}

        self.time_limit = 120
        self.mission_text = "Собрать артефакты и победить босса"
        self.completed = False

        self.level_index = 0
        self.levels = []
        self.level_width = 4700
        self.level_height = 600
        self.camera_x = 0
        self.score = 0
        self.coins = 0
        self.shake = 0.0
        self.particles = []
        self.floating = []
        self.projectiles = []
        self.pickups = []
        self.enemies = []
        self.hazards = []
        self.moving_hazards = []
        self.checkpoints = []
        self.coin_rects = []
        self.platforms = []
        self.moving_platforms = []

        self.player = None
        self.boss = None

        self.player_idle_frames = [fallback_surface((58, 82), BLUE, "IDLE") for _ in range(4)]
        self.player_run_frames = [fallback_surface((58, 82), GREEN, "RUN") for _ in range(6)]
        self.player_jump_frames = [fallback_surface((58, 82), ORANGE, "JUMP") for _ in range(2)]
        self.player_attack_frames = [fallback_surface((58, 82), RED, "ATTACK") for _ in range(4)]
        self.player_slide_frames = [fallback_surface((58, 82), TEAL, "SLIDE") for _ in range(2)]

        self.menu_buttons = [
            Button((350, 220, 400, 58), "Старт"),
            Button((350, 300, 400, 58), "Персонаж"),
            Button((350, 380, 400, 58), "Инвентарь"),
            Button((350, 460, 400, 58), "Выход"),
        ]

        self.char_buttons = [
            Button((150, 230, 220, 58), "Knight"),
            Button((440, 230, 220, 58), "Ranger"),
            Button((730, 230, 220, 58), "Mage"),
            Button((430, 470, 240, 58), "Назад"),
        ]

        self.inventory_buttons = [
            Button((220, 210, 220, 52), "Леч. зелье"),
            Button((220, 280, 220, 52), "Мана"),
            Button((220, 350, 220, 52), "Дым"),
            Button((700, 480, 200, 52), "Назад"),
        ]

        self.build_levels()
        self.create_player()

    # ============================================================
    # ИНИЦИАЛИЗАЦИЯ УРОВНЕЙ
    # ============================================================

    def build_levels(self):
        self.levels = [self.build_level_1(), self.build_level_2()]

    def build_level_1(self):
        level = {
            "name": "Ground Zero",
            "timer": 120,
            "goal_x": 4400,
            "mission": "Собери 4 артефакта и добей босса",
            "platforms": [
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
            ],
            "moving_platforms": [
                MovingPlatform(710, 470, 130, 25, 75, 1.5),
                MovingPlatform(2200, 440, 130, 25, 120, 1.2),
                MovingPlatform(2910, 450, 120, 25, 90, 1.8),
            ],
            "hazards": [
                pygame.Rect(700, 615, 150, 35),
                pygame.Rect(1400, 615, 150, 35),
                pygame.Rect(2200, 615, 150, 35),
                pygame.Rect(2900, 615, 150, 35),
                pygame.Rect(3600, 615, 150, 35)
            ],
            "moving_hazards": [
                MovingHazard(1730, 560, 120, 22, 80, 1.7),
                MovingHazard(3350, 560, 120, 22, 100, 1.9)
            ],
            "checkpoints": [
                pygame.Rect(1350, 490, 35, 50),
                pygame.Rect(2700, 490, 35, 50),
                pygame.Rect(3600, 490, 35, 50),
            ],
            "coins": [pygame.Rect(470, 380, 28, 28), pygame.Rect(570, 380, 28, 28), pygame.Rect(1010, 340, 28, 28),
                pygame.Rect(1290, 250, 28, 28), pygame.Rect(1760, 360, 28, 28), pygame.Rect(2100, 270, 28, 28),
                pygame.Rect(2540, 370, 28, 28), pygame.Rect(2840, 250, 28, 28), pygame.Rect(3240, 360, 28, 28),
                pygame.Rect(3540, 250, 28, 28), pygame.Rect(3990, 340, 28, 28), pygame.Rect(4370, 260, 28, 28)],
            "enemies": [
                Enemy(self, 570, 462, "zombie"),
                Enemy(self, 1080, 312, "vampire"),
                Enemy(self, 1250, 222, "zombie"),
                Enemy(self, 1800, 332, "vampire"),
                Enemy(self, 2150, 242, "brute"),
                Enemy(self, 2600, 342, "vampire"),
                Enemy(self, 3280, 332, "zombie"),
                Enemy(self, 3550, 222, "brute"),
                Enemy(self, 3980, 312, "zombie"),
            ],
            "boss": Boss(self, 4300, 180)
        }
        return level

    def build_level_2(self):
        level = {
            "name": "Deep Rift",
            "timer": 150,
            "goal_x": 4500,
            "mission": "Пройди хребет, забери реликвию и уничтожь «Вратаря Тьмы»",
            "platforms": [
                pygame.Rect(0, 540, 760, 110),
                pygame.Rect(900, 520, 200, 28),
                pygame.Rect(1200, 450, 220, 28),
                pygame.Rect(1650, 410, 220, 28),
                pygame.Rect(2050, 340, 180, 28),
                pygame.Rect(2420, 300, 160, 28),
                pygame.Rect(2820, 430, 230, 28),
                pygame.Rect(3200, 520, 200, 28),
                pygame.Rect(3550, 430, 220, 28),
                pygame.Rect(3960, 360, 180, 28),
                pygame.Rect(4300, 540, 300, 110),
                pygame.Rect(1110, 540, 250, 110),
                pygame.Rect(1880, 540, 200, 110),
                pygame.Rect(2600, 540, 280, 110),
                pygame.Rect(3330, 540, 220, 110),
                pygame.Rect(3700, 540, 220, 110)
            ],
            "moving_platforms": [
                MovingPlatform(1480, 430, 130, 22, 110, 1.8),
                MovingPlatform(2250, 430, 130, 22, 90, 1.6),
                MovingPlatform(3450, 320, 140, 22, 80, 1.9)
            ],
            "hazards": [
                pygame.Rect(760, 615, 140, 35),
                pygame.Rect(1440, 615, 130, 35),
                pygame.Rect(2100, 615, 150, 35),
                pygame.Rect(3000, 615, 180, 35),
                pygame.Rect(3880, 615, 140, 35)
            ],
            "moving_hazards": [
                MovingHazard(1220, 470, 120, 20, 90, 2.0),
                MovingHazard(3440, 500, 140, 20, 100, 2.4)
            ],
            "checkpoints": [
                pygame.Rect(1380, 390, 35, 50),
                pygame.Rect(2750, 370, 35, 50),
                pygame.Rect(3920, 300, 35, 50)
            ],
            "coins": [
                pygame.Rect(925, 470, 28, 28), pygame.Rect(1235, 400, 28, 28), pygame.Rect(1700, 360, 28, 28),
                pygame.Rect(2080, 290, 28, 28), pygame.Rect(2460, 250, 28, 28), pygame.Rect(2850, 380, 28, 28),
                pygame.Rect(3260, 470, 28, 28), pygame.Rect(3590, 380, 28, 28), pygame.Rect(4020, 310, 28, 28)
            ],
            "enemies": [
                Enemy(self, 980, 442, "zombie"),
                Enemy(self, 1510, 360, "vampire"),
                Enemy(self, 2080, 280, "brute"),
                Enemy(self, 2890, 380, "vampire"),
                Enemy(self, 3340, 470, "zombie"),
                Enemy(self, 4010, 300, "brute"),
            ],
            "boss": Boss(self, 4380, 170)
        }
        return level

    # ============================================================
    # СОЗДАНИЕ ГЕРОЯ
    # ============================================================

    def create_player(self):
        self.player = Player(self, self.selected_character)
        self.player_idle_frames = [fallback_surface((58, 82), BLUE, "IDLE") for _ in range(4)]
        self.player_run_frames = [fallback_surface((58, 82), GREEN, "RUN") for _ in range(6)]
        self.player_jump_frames = [fallback_surface((58, 82), ORANGE, "JUMP") for _ in range(2)]
        self.player_attack_frames = [fallback_surface((58, 82), RED, "ATTACK") for _ in range(4)]
        self.player_slide_frames = [fallback_surface((58, 82), TEAL, "SLIDE") for _ in range(2)]

        preset = CHARACTER_PRESETS[self.selected_character]
        self.player.max_health = preset["health"]
        self.player.health = preset["health"]
        self.player.speed = preset["speed"]
        self.player.jump_power = preset["jump"]
        self.player.attack_damage = preset["attack"]
        self.player.dash_speed = preset["dash"]
        self.player.reset((150, 350))

    def start_level(self):
        self.completed = False
        level = self.levels[self.level_index]
        self.level_width = 4700
        self.level_height = 600
        self.time_limit = level["timer"]
        self.mission_text = level["mission"]

        self.platforms = list(level["platforms"]) + [p.rect for p in level["moving_platforms"]]
        self.moving_platforms = level["moving_platforms"]
        self.hazards = level["hazards"]
        self.moving_hazards = level["moving_hazards"]
        self.checkpoints = level["checkpoints"]
        self.coin_rects = level["coins"]
        self.enemies = level["enemies"]
        self.projectiles = []
        self.boss = level["boss"]
        self.pickups = []

        self.player.reset((150, 350))
        self.player.max_health = CHARACTER_PRESETS[self.selected_character]["health"] + self.upgrade_levels.get("health", 0) * 20
        self.player.health = self.player.max_health
        self.score = 0
        self.coins = 0
        self.camera_x = 0
        self.floating = []
        self.particles = []
        self.state = "playing"

    def change_character(self, name):
        self.selected_character = name
        self.create_player()

    def respawn_player(self):
        self.player.reset(self.player.rect.topleft if self.player else (150, 350))
        self.burst(self.player.rect.centerx, self.player.rect.centery, RED, 12)

    def burst(self, x, y, color, count=8, gravity=500):
        for _ in range(count):
            self.particles.append(
                Particle(
                    x, y, color,
                    life=random.uniform(0.25, 0.7),
                    speed=random.uniform(60, 180),
                    gravity=gravity
                )
            )

    # ============================================================
    # ОБНОВЛЕНИЕ ИГРЫ
    # ============================================================

    def update(self, dt):
        self.shake = max(0, self.shake - 20 * dt)
        self.particles = [p for p in self.particles if p.update(dt)]
        self.floating = [f for f in self.floating if f.update(dt)]
        self.projectiles = [p for p in self.projectiles if p.update(dt, self)]

        if self.state != "playing":
            return

        self.time_limit -= dt

        if self.time_limit <= 0:
            self.state = "menu"
            self.best_score = max(self.best_score, int(self.score))
            save_best(self.best_score)
            self.floating.append(FloatingText("Время вышло", WIDTH // 2, HEIGHT // 2, RED))
            return

        for platform in self.moving_platforms:
            platform.update(dt)
        self.platforms = list(self.levels[self.level_index]["platforms"]) + [p.rect for p in self.moving_platforms]

        for hazard in self.moving_hazards:
            hazard.update(dt)

        keys = pygame.key.get_pressed()
        self.player.update(dt, keys)

        for enemy in self.enemies:
            enemy.update(dt)

        if self.boss and self.boss.alive:
            self.boss.update(dt)

        self.collect_coins()
        self.update_checkpoint()
        self.pickups = [p for p in self.pickups if p.update(dt, self)]

        self.score += dt * 10
        self.camera_x = clamp(self.player.rect.centerx - WIDTH // 2, 0, self.level_width - WIDTH)

        if self.player.rect.x > self.levels[self.level_index]["goal_x"] and (not self.boss or not self.boss.alive):
            self.level_index += 1
            if self.level_index >= len(self.levels):
                self.state = "victory"
                self.best_score = max(self.best_score, int(self.score))
                save_best(self.best_score)
            else:
                self.start_level()

    def update_checkpoint(self):
        for checkpoint in self.checkpoints:
            if self.player.rect.colliderect(checkpoint) and checkpoint.x > self.player.x - 40:
                self.player.x = float(checkpoint.x) + 30
                self.player.rect.x = int(self.player.x)
                self.score += 200
                self.floating.append(FloatingText("ЧЕКПОИНТ +200", checkpoint.x + 15, checkpoint.y - 25, GOLD))
                self.burst(checkpoint.centerx, checkpoint.centery, GOLD, 18)

    def collect_coins(self):
        remaining = []
        for coin in self.coin_rects:
            if self.player.rect.colliderect(coin):
                self.coins += 1
                self.score += 100
                self.sound.play("coin")
                self.floating.append(FloatingText("+100", coin.centerx, coin.y, GOLD))
                self.burst(coin.centerx, coin.centery, GOLD, 12, gravity=0)
            else:
                remaining.append(coin)
        self.coin_rects = remaining

    # ============================================================
    # СОБЫТИЯ
    # ============================================================

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.state in ("playing", "paused", "char_select", "inventory", "victory"):
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

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos

            if self.state == "menu":
                if self.menu_buttons[0].rect.collidepoint(pos):
                    self.start_level()
                    self.sound.play("click")
                elif self.menu_buttons[1].rect.collidepoint(pos):
                    self.state = "char_select"
                    self.sound.play("click")
                elif self.menu_buttons[2].rect.collidepoint(pos):
                    self.state = "inventory"
                    self.sound.play("click")
                elif self.menu_buttons[3].rect.collidepoint(pos):
                    pygame.quit()
                    sys.exit()

            elif self.state == "char_select":
                for i, btn in enumerate(self.char_buttons[:-1]):
                    if btn.rect.collidepoint(pos):
                        names = ["Knight", "Ranger", "Mage"]
                        self.change_character(names[i])
                        self.sound.play("click")
                        return
                if self.char_buttons[-1].rect.collidepoint(pos):
                    self.state = "menu"
                    self.sound.play("click")

            elif self.state == "inventory":
                if self.inventory_buttons[0].rect.collidepoint(pos):
                    if self.inventory.get("health_potion", 0) > 0:
                        self.player.use_potion("health")
                    self.sound.play("click")
                elif self.inventory_buttons[1].rect.collidepoint(pos):
                    if self.inventory.get("mana_potion", 0) > 0:
                        self.player.use_potion("mana")
                    self.sound.play("click")
                elif self.inventory_buttons[2].rect.collidepoint(pos):
                    if self.inventory.get("smoke_bomb", 0) > 0:
                        self.inventory["smoke_bomb"] -= 1
                        self.player.invulnerability = 0.9
                        self.floating.append(FloatingText("Туман", self.player.rect.centerx, self.player.rect.y, WHITE))
                    self.sound.play("click")
                elif self.inventory_buttons[-1].rect.collidepoint(pos):
                    self.state = "menu"

            elif self.state == "victory":
                self.state = "menu"

    # ============================================================
    # ОТРИСОВКА
    # ============================================================

    def draw_background(self, screen):
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
        for _ in range(60):
            x = (random.randint(0, WIDTH) - int(self.camera_x * 0.04)) % WIDTH
            y = random.randint(35, 280)
            brightness = 140 + int(80 * (math.sin(self.time_limit * 2 + x) + 1) / 2)
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

    def draw_level(self, screen):
        self.draw_background(screen)

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
                pygame.draw.polygon(screen, RED, [(x, rect.bottom), (x + 9, rect.top), (x + 18, rect.bottom)])

        for hazard in self.moving_hazards:
            rect = hazard.rect.copy()
            rect.x -= int(self.camera_x)
            for x in range(rect.left, rect.right, 18):
                pygame.draw.polygon(screen, RED, [(x, rect.bottom), (x + 9, rect.top), (x + 18, rect.bottom)])

        for checkpoint in self.checkpoints:
            x = checkpoint.x - self.camera_x
            pygame.draw.line(screen, WHITE, (x + 15, checkpoint.y), (x + 15, checkpoint.y + 50), 4)
            pygame.draw.polygon(screen, GOLD, [(x + 17, checkpoint.y), (x + 55, checkpoint.y + 14), (x + 17, checkpoint.y + 28)])

        for coin in self.coin_rects:
            rect = coin.copy()
            rect.x -= int(self.camera_x)
            pulse = int(2 * math.sin(self.time_limit * 6 + coin.x))
            pygame.draw.circle(screen, GOLD, rect.center, 14 + pulse)
            pygame.draw.circle(screen, (255, 245, 160), rect.center, 7)

        for enemy in self.enemies:
            enemy.draw(self.camera_x, screen)

        if self.boss:
            self.boss.draw(self.camera_x, screen)

        for projectile in self.projectiles:
            projectile.draw(self.camera_x, screen)

        for pickup in self.pickups:
            pickup.draw(self.camera_x, screen)

        self.player.draw(self.camera_x, screen, self.font_small)

        for particle in self.particles:
            particle.draw(self.camera_x, screen)

        for floating in self.floating:
            floating.draw(self.camera_x, screen, self.font_small)

        finish_x = self.levels[self.level_index]["goal_x"] - self.camera_x
        pygame.draw.line(screen, WHITE, (finish_x, 350), (finish_x, 540), 5)
        draw_text("ФИНИШ", self.font_small, GOLD, finish_x, 320)

        # dark overlay
        darkness = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(darkness, (0, 0, 0, 150), (int(self.player.rect.centerx - self.camera_x), int(self.player.rect.centery)), 190)
        screen.blit(darkness, (0, 0))

        # fog
        for i in range(5):
            x = (self.camera_x * 0.15 + i * 180 + self.time_limit * 8) % (WIDTH + 120) - 60
            y = 150 + (i % 3) * 70 + math.sin((self.time_limit + i) * 1.2) * 18
            pygame.draw.circle(screen, (220, 220, 240, 60), (int(x), int(y)), 80)

        # HUD
        pygame.draw.rect(screen, (8, 10, 20, 180), (12, 12, 310, 108), border_radius=10)
        pygame.draw.rect(screen, BLACK, (25, 25, 180, 15))
        pygame.draw.rect(screen, RED, (25, 25, int(180 * max(self.player.health, 0) / self.player.max_health), 15))
        pygame.draw.rect(screen, WHITE, (25, 25, 180, 15), 2)

        draw_text(f"Счёт: {int(self.score)}", self.font_small, WHITE, 25, 48, center=False)
        draw_text(f"Монеты: {self.coins}   Лучший: {self.best_score}", self.font_small, GOLD, 25, 77, center=False)
        draw_text(f"Уровень: {self.levels[self.level_index]['name']}", self.font_tiny, WHITE, 25, 98, center=False)
        draw_text(f"Время: {int(self.time_limit)}", self.font_small, CYAN, WIDTH - 120, 35, center=True)
        draw_text(self.mission_text[:38], self.font_tiny, WHITE, WIDTH // 2, 20, center=True)

    def draw_menu(self, screen):
        self.draw_background(screen)
        draw_text("SHADOW PARKOUR", self.font_title, WHITE, WIDTH // 2, 110)
        draw_text("NIGHTFALL — охота на Владыку Бездны", self.font_medium, BLUE, WIDTH // 2, 180)
        draw_text(f"Выбранный герой: {self.selected_character}", self.font_medium, GOLD, WIDTH // 2, 260)

        mouse = pygame.mouse.get_pos()
        for button in self.menu_buttons:
            button.update(mouse)
            button.draw(screen, self.font_medium)

        draw_text(f"Лучший счёт: {self.best_score}", self.font_small, GRAY, WIDTH // 2, 560)

    def draw_char_select(self, screen):
        self.draw_background(screen)
        draw_text("ВЫБОР ПЕРСОНАЖА", self.font_title, WHITE, WIDTH // 2, 110)

        names = ["Knight", "Ranger", "Mage"]
        for i, button in enumerate(self.char_buttons[:-1]):
            button.update(pygame.mouse.get_pos())
            button.draw(screen, self.font_medium)
            draw_text(names[i], self.font_small, WHITE, button.rect.centerx, button.rect.centery)

        self.char_buttons[-1].update(pygame.mouse.get_pos())
        self.char_buttons[-1].draw(screen, self.font_medium)

    def draw_inventory(self, screen):
        self.draw_background(screen)
        draw_text("ИНВЕНТАРЬ", self.font_title, WHITE, WIDTH // 2, 120)
        draw_text(f"Леч. зелье: {self.inventory.get('health_potion', 0)}", self.font_medium, GREEN, 420, 220)
        draw_text(f"Мана: {self.inventory.get('mana_potion', 0)}", self.font_medium, TEAL, 420, 290)
        draw_text(f"Дым: {self.inventory.get('smoke_bomb', 0)}", self.font_medium, WHITE, 420, 360)

        mouse = pygame.mouse.get_pos()
        for button in self.inventory_buttons:
            button.update(mouse)
            button.draw(screen, self.font_medium)

        draw_text("1 — Леч. зелье   2 — Мана", self.font_small, WHITE, WIDTH // 2, 520)

    def draw_pause(self, screen):
        self.draw_level(screen)
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 175))
        screen.blit(overlay, (0, 0))
        draw_text("ПАУЗА", self.font_title, WHITE, WIDTH // 2, 250)
        draw_text("P — продолжить   ESC — меню", self.font_medium, GRAY, WIDTH // 2, 350)

    def draw_victory(self, screen):
        self.draw_background(screen)
        draw_text("ПОБЕДА!", self.font_title, GOLD, WIDTH // 2, 180)
        draw_text("Все уровни пройдены", self.font_big, WHITE, WIDTH // 2, 275)
        draw_text(f"Счёт: {int(self.score)}", self.font_medium, GOLD, WIDTH // 2, 360)
        draw_text(f"Рекорд: {self.best_score}", self.font_medium, WHITE, WIDTH // 2, 405)
        draw_text("Нажмите ESC или мышь, чтобы вернуться в меню", self.font_small, GRAY, WIDTH // 2, 490)

    def draw(self):
        if self.state == "menu":
            self.draw_menu(self.screen)
        elif self.state == "char_select":
            self.draw_char_select(self.screen)
        elif self.state == "inventory":
            self.draw_inventory(self.screen)
        elif self.state == "playing":
            self.draw_level(self.screen)
        elif self.state == "paused":
            self.draw_pause(self.screen)
        elif self.state == "victory":
            self.draw_victory(self.screen)

    def run(self):
        running = True
        while running:
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                self.handle_event(event)

            self.update(dt)
            self.draw()
            pygame.display.flip()

        pygame.quit()
        sys.exit()