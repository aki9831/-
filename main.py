import math
import pygame

import game as core
from game import Game, Player, Projectile, FloatingText
from assets import WIDTH, HEIGHT, WHITE, BLACK, GOLD, RED, PURPLE, CYAN, TEAL, PINK, BLUE, GREEN


def install_features():
    """Adds the optional deluxe systems without replacing the stable core engine."""
    original_game_init = Game.__init__
    original_game_start_level = Game.start_level
    original_game_handle_event = Game.handle_event
    original_game_update = Game.update
    original_game_draw = Game.draw
    original_player_update = Player.update

    def game_init(self):
        original_game_init(self)
        self.quest = {
            "artifacts": 0,
            "artifacts_goal": 5,
            "kills": 0,
            "kills_goal": 6,
            "boss_done": False,
            "rewarded": False,
        }
        self.quest_message = "Найдите 5 артефактов"
        self.quest_banner = 0.0
        self.inventory_open = False
        self.inventory_tab = "items"
        self.smoke_timer = 0.0
        self._known_alive = sum(enemy.alive for enemy in self.enemies)

    def reset_quest(self):
        self.quest = {
            "artifacts": 0,
            "artifacts_goal": 5 if self.level_index == 0 else 7,
            "kills": 0,
            "kills_goal": 6 if self.level_index == 0 else 5,
            "boss_done": False,
            "rewarded": False,
        }
        self.quest_message = (
            "Соберите 5 артефактов и победите босса"
            if self.level_index == 0
            else "Соберите 7 артефактов и уничтожьте Вратаря"
        )
        self.quest_banner = 3.0
        self._known_alive = sum(enemy.alive for enemy in self.enemies)

    def start_level(self):
        original_game_start_level(self)
        reset_quest(self)

    def player_special_attack(self):
        if getattr(self, "special_cooldown", 0) > 0 or self.stamina < 35:
            return
        self.special_cooldown = 2.0
        self.stamina -= 35
        self.game.sound.play("special") if "special" in self.game.sound.sounds else None
        self.game.burst(self.rect.centerx, self.rect.centery, PURPLE, 28, gravity=0)

        if self.character_name == "Knight":
            radius = 190
            for enemy in self.game.enemies:
                if enemy.alive and math.hypot(enemy.rect.centerx - self.rect.centerx, enemy.rect.centery - self.rect.centery) < radius:
                    enemy.take_damage(self.attack_damage * 2.4)
            if self.game.boss and self.game.boss.alive and math.hypot(self.game.boss.rect.centerx - self.rect.centerx, self.game.boss.rect.centery - self.rect.centery) < 230:
                self.game.boss.take_damage(self.attack_damage * 2.2)
        elif self.character_name == "Ranger":
            for angle in (-0.35, -0.17, 0, 0.17, 0.35):
                direction = 1 if self.direction > 0 else -1
                vx = math.cos(angle) * direction * 700
                vy = math.sin(angle) * 700
                self.game.projectiles.append(Projectile(self.rect.centerx, self.rect.centery, vx, vy, GOLD, 70, 700, True))
        else:
            for enemy in self.game.enemies:
                if enemy.alive:
                    enemy.take_damage(105)
            if self.game.boss and self.game.boss.alive:
                self.game.boss.take_damage(125)
            self.game.floating.append(FloatingText("ARCANE NOVA", self.rect.centerx, self.rect.y - 30, PINK))

    def player_update(self, dt, keys):
        self.special_cooldown = max(0.0, getattr(self, "special_cooldown", 0.0) - dt)
        self.smoke_timer = max(0.0, getattr(self, "smoke_timer", 0.0) - dt)
        original_player_update(self, dt, keys)

    def game_handle_event(self, event):
        if event.type == pygame.KEYDOWN and self.state == "playing":
            if event.key == pygame.K_q:
                self.player.special_attack()
            elif event.key == pygame.K_i:
                self.inventory_open = True
                self.state = "inventory_playing"
                return
        elif event.type == pygame.KEYDOWN and self.state == "inventory_playing":
            if event.key in (pygame.K_i, pygame.K_ESCAPE):
                self.inventory_open = False
                self.state = "playing"
                return
            if event.key == pygame.K_1:
                self.player.use_potion("health")
                return
            if event.key == pygame.K_2:
                self.player.use_potion("mana")
                return
            if event.key == pygame.K_3:
                self.use_smoke_bomb()
                return
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.state == "inventory_playing":
            x, y = event.pos
            if pygame.Rect(260, 260, 260, 58).collidepoint(x, y):
                self.player.use_potion("health")
                return
            if pygame.Rect(580, 260, 260, 58).collidepoint(x, y):
                self.player.use_potion("mana")
                return
            if pygame.Rect(260, 340, 260, 58).collidepoint(x, y):
                self.use_smoke_bomb()
                return
        original_game_handle_event(self, event)

    def use_smoke_bomb(self):
        if self.inventory.get("smoke_bomb", 0) <= 0:
            return
        self.inventory["smoke_bomb"] -= 1
        self.player.invulnerability = max(self.player.invulnerability, 3.0)
        self.player.smoke_timer = 3.0
        self.burst(self.player.rect.centerx, self.player.rect.centery, WHITE, 60, gravity=0)
        self.floating.append(FloatingText("ДЫМОВАЯ ЗАВЕСА", self.player.rect.centerx, self.player.rect.y - 20, WHITE))

    def game_update(self, dt):
        if self.state == "inventory_playing":
            self.particles = [p for p in self.particles if p.update(dt)]
            self.floating = [f for f in self.floating if f.update(dt)]
            return
        original_game_update(self, dt)
        if self.state != "playing":
            return

        alive_now = sum(enemy.alive for enemy in self.enemies)
        if alive_now < self._known_alive:
            self.quest["kills"] += self._known_alive - alive_now
            self._known_alive = alive_now

        collected = 12 - len(self.coin_rects)
        self.quest["artifacts"] = min(self.quest["artifacts_goal"], collected)
        if self.boss and not self.boss.alive:
            self.quest["boss_done"] = True

        complete = (
            self.quest["artifacts"] >= self.quest["artifacts_goal"]
            and self.quest["kills"] >= self.quest["kills_goal"]
            and self.quest["boss_done"]
        )
        if complete and not self.quest["rewarded"]:
            self.quest["rewarded"] = True
            self.coins += 8
            self.score += 750
            self.quest_message = "Квест выполнен! Награда: +8 монет, +750 очков"
            self.quest_banner = 4.0

        self.quest_banner = max(0.0, self.quest_banner - dt)

    def draw_inventory_overlay(self):
        self.draw_level(self.screen)
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((5, 7, 15, 220))
        self.screen.blit(overlay, (0, 0))
        pygame.draw.rect(self.screen, (20, 28, 52), (150, 110, 800, 440), border_radius=18)
        pygame.draw.rect(self.screen, CYAN, (150, 110, 800, 440), 3, border_radius=18)
        draw_text("ИНТЕРАКТИВНЫЙ ИНВЕНТАРЬ", self.font_big, WHITE, WIDTH // 2, 155)
        draw_text("I/ESC — закрыть | 1/2/3 — использовать предмет", self.font_small, CYAN, WIDTH // 2, 195)

        slots = [
            (pygame.Rect(260, 260, 260, 58), "1  Лечебное зелье", self.inventory.get("health_potion", 0), GREEN),
            (pygame.Rect(580, 260, 260, 58), "2  Энергия", self.inventory.get("mana_potion", 0), TEAL),
            (pygame.Rect(260, 340, 260, 58), "3  Дымовая завеса", self.inventory.get("smoke_bomb", 0), WHITE),
        ]
        mouse = pygame.mouse.get_pos()
        for rect, title, count, color in slots:
            hovered = rect.collidepoint(mouse)
            pygame.draw.rect(self.screen, (45, 65, 100) if hovered else (30, 43, 75), rect, border_radius=10)
            pygame.draw.rect(self.screen, color, rect, 2, border_radius=10)
            draw_text(title, self.font_small, WHITE, rect.centerx - 25, rect.centery - 8)
            draw_text(f"x{count}", self.font_small, color, rect.right - 35, rect.centery - 8)

        draw_text("Q — специальная атака", self.font_medium, GOLD, WIDTH // 2, 470)

    def game_draw(self):
        if self.state == "inventory_playing":
            self.draw_inventory_overlay()
            return
        original_game_draw(self)
        if self.state == "playing":
            # Quest panel over the normal HUD.
            panel = pygame.Surface((390, 82), pygame.SRCALPHA)
            panel.fill((5, 8, 18, 190))
            self.screen.blit(panel, (350, 48))
            draw_text("КВЕСТ", self.font_tiny, GOLD, 365, 57, center=False)
            draw_text(f"Артефакты: {self.quest['artifacts']}/{self.quest['artifacts_goal']}  Убийства: {self.quest['kills']}/{self.quest['kills_goal']}", self.font_tiny, WHITE, 365, 77, center=False)
            draw_text("Босс: " + ("✓" if self.quest["boss_done"] else "не побеждён"), self.font_tiny, GREEN if self.quest["boss_done"] else RED, 365, 96, center=False)
            if self.quest_banner > 0:
                draw_text(self.quest_message, self.font_small, GOLD, WIDTH // 2, 135)
            if getattr(self.player, "smoke_timer", 0) > 0:
                fog = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                fog.fill((225, 230, 245, 35))
                self.screen.blit(fog, (0, 0))

    Game.__init__ = game_init
    Game.start_level = start_level
    Game.handle_event = game_handle_event
    Game.update = game_update
    Game.draw = game_draw
    Player.update = player_update
    Player.special_attack = player_special_attack
    Game.use_smoke_bomb = use_smoke_bomb


def main():
    install_features()
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
