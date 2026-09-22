import math
from array import array

import pygame

# ============================================================
# КОНСТАНТЫ
# ============================================================

WIDTH, HEIGHT, FPS = 1100, 650, 60

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
TEAL = (52, 200, 180)
PINK = (240, 100, 180)

# ============================================================
# УТИЛИТЫ
# ============================================================

def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def draw_text(text, font, color, x, y, center=True):
    surface = font.render(str(text), True, color)
    rect = surface.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    pygame.display.get_surface().blit(surface, rect)


def fallback_surface(size, color, label=""):
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill(color)
    pygame.draw.rect(surface, BLACK, surface.get_rect(), 3)

    for x in range(-size[1], size[0], 16):
        pygame.draw.line(surface, (255, 255, 255, 45), (x, 0), (x + size[1], size[1]), 2)

    if label:
        text = pygame.font.SysFont("arial", 15).render(label, True, WHITE)
        surface.blit(text, text.get_rect(center=surface.get_rect().center))
    return surface


# ============================================================
# ЗВУК
# ============================================================

class SoundManager:
    def __init__(self):
        self.sounds = {}
        for name, (frequency, duration) in {
            "jump": (520, 0.09),
            "dash": (180, 0.12),
            "hit": (90, 0.10),
            "coin": (880, 0.10),
            "hurt": (120, 0.16),
            "boss": (55, 0.35),
            "victory": (660, 0.35),
            "click": (300, 0.06),
            "shoot": (300, 0.08),
            "heal": (500, 0.12),
        }.items():
            self.sounds[name] = self._load_or_beep(name, frequency, duration)

        self.music = None

    def _load_or_beep(self, name, frequency, duration):
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
        except Exception:
            return None

    def play(self, name):
        sound = self.sounds.get(name)
        if sound is None:
            return
        try:
            sound.play()
        except Exception:
            pass

    def start_music(self):
        pass