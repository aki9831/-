# Ошибка "No module named 'pygame'" означает, что библиотека pygame не установлена.
# Решение: установить pygame через pip.

import subprocess
import sys

def install_pygame():
    """Установка библиотеки pygame через pip."""
    try:
        # Проверяем, установлен ли pygame
        import pygame
        print("pygame уже установлен.")
        return
    except ImportError:
        print("pygame не найден. Устанавливаю...")

    # Устанавливаем pygame с помощью pip
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pygame"])
    print("Установка завершена.")

if __name__ == "__main__":
    install_pygame()












import pygame
import sys

# Инициализация Pygame
pygame.init()

# --- Настройки Игры ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Паркур игра")

# Цвета
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (128, 128, 128)
DARK_GRAY = (50, 50, 50)

# Шрифты
font_title = pygame.font.Font(None, 74)
font_menu = pygame.font.Font(None, 50)
font_game = pygame.font.Font(None, 36)

# --- Обертка загрузки текстур ---
def load_image(path, size=(50, 50), fallback_color=(180, 180, 180)):
    """
    Пытается загрузить изображение.
    Если не удалось, возвращает простую заливку нужного размера как замещатель.
    """
    try:
        img = pygame.image.load(path).convert_alpha()
        # Убедимся, что размер подходит
        if img.get_size() != size:
            img = pygame.transform.scale(img, size)
        return img
    except (pygame.error, FileNotFoundError):
        # Создать простую заливку-замещение
        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill(fallback_color)
        # Добавим рамку, чтобы понять что это заглушка
        pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 2)
        return surf

# --- Загрузка Текстур (теперь через load_image) ---
player_img = load_image("textures/player.png", size=(50, 50), fallback_color=(255, 0, 0))
block_img = load_image("textures/block.png", size=(50, 50), fallback_color=(0, 255, 0))
checkpoint_img = load_image("textures/checkpoint.png", size=(32, 32), fallback_color=(0, 0, 255))
background_img = load_image("textures/background.png", size=(SCREEN_WIDTH, SCREEN_HEIGHT), fallback_color=(20, 20, 40))

# --- Звуки (Если есть — загрузим, иначе продолжим без них) ---
try:
    jump_sound = pygame.mixer.Sound("sounds/jump.wav")
    checkpoint_sound = pygame.mixer.Sound("sounds/checkpoint.wav")
    level_complete_sound = pygame.mixer.Sound("sounds/level_complete.wav")
except (pygame.error, FileNotFoundError):
    print("Звуковые файлы не найдены. Звук будет отключён.")
    jump_sound = None
    checkpoint_sound = None
    level_complete_sound = None

# --- Параметры Игрока ---
player_rect = player_img.get_rect(center=(100, SCREEN_HEIGHT - 50)) # Начальная позиция
player_velocity_y = 0
gravity = 1

# --- Уровни Сложности и Сами Уровни ---
difficulty_levels = {
    "Легкий": {"jump_height": 15, "speed": 5, "enemy_speed": 1},
    "Средний": {"jump_height": 20, "speed": 7, "enemy_speed": 2},
    "Сложный": {"jump_height": 25, "speed": 9, "enemy_speed": 3}
}
current_difficulty = "Легкий"

# Пример структуры уровней. Лайаут — список групп платформ; checkpoint — координаты чекпоинта
levels = {
    1: {"layout": [[(100, 550, 50, 50), (200, 500, 50, 50), (300, 450, 50, 50)]], "checkpoint": (350, 430)},
    2: {"layout": [[(100, 550, 50, 50)], [(400, 400, 50, 50)]], "checkpoint": (450, 350)},
}
current_level_index = 1
current_level_data = levels[current_level_index]
platforms = [] # Список для хранения платформ текущего уровня
checkpoints = [] # Список для хранения чекпоинтов

# --- Состояние Игры ---
game_state = "menu" # menu, playing, settings, game_over

# --- Меню ---
menu_options = ["Начать Игру", "Настройки", "Выход"]
settings_options = ["Сложность", "Назад"]
selected_menu_index = 0
selected_settings_index = 0

# --- Функции ---
def draw_text(text, font, color, x, y):
    """Отрисовка текста на экране."""
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=(x, y))
    screen.blit(text_surface, text_rect)

def create_level(level_data):
    """Создает платформы и чекпоинты для текущего уровня."""
    global platforms, checkpoints
    platforms = []
    checkpoints = []
    # Создаем платформы
    for group in level_data.get("layout", []):
        for (x, y, w, h) in group:
            platforms.append(pygame.Rect(x, y, w, h))
    # Создаем чекпоинт (если указан)
    cp = level_data.get("checkpoint")
    if cp:
        checkpoints.append(pygame.Rect(cp[0], cp[1], 32, 32))

def update_player():
    """Обновляет позицию игрока."""
    global player_velocity_y, game_state

    # Применение гравитации
    player_velocity_y += gravity
    player_rect.y += player_velocity_y

    # Проверка столкновений с платформами
    for platform in platforms:
        if player_rect.colliderect(platform):
            if player_velocity_y > 0: # Падение
                player_rect.bottom = platform.top
                player_velocity_y = 0
            elif player_velocity_y < 0: # Прыжок вверх
                player_rect.top = platform.bottom
                player_velocity_y = 0

    # Проверка выхода за пределы экрана (падение)
    if player_rect.top > SCREEN_HEIGHT:
        reset_level()
        if jump_sound:
            jump_sound.play() # Звук падения (если есть)

    # Проверка чекпоинтов
    for checkpoint in checkpoints:
        if player_rect.colliderect(checkpoint):
            if checkpoint_sound:
                checkpoint_sound.play()
            # Переход к следующему уровню
            global current_level_index
            current_level_index += 1
            if current_level_index in levels:
                current_level_data = levels[current_level_index]
                create_level(current_level_data)
                # Перемещаем игрока к последнему чекпоинту на новом уровне
                if checkpoints:
                    player_rect.topleft = (checkpoints[-1].x, checkpoints[-1].y)
            else:
                draw_text("Уровень пройден!", font_game, WHITE, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
                if level_complete_sound:
                    level_complete_sound.play()
                pygame.time.wait(2000)
                game_state = "menu" # Возврат в меню после завершения всех уровней
            break

def reset_level():
    """Сбрасывает уровень или позицию игрока."""
    global player_rect, player_velocity_y
    # Поиск последнего активного чекпоинта или начальная позиция
    if checkpoints:
        last = checkpoints[-1]
        player_rect.topleft = (last.x, last.y)
    else:
        player_rect.topleft = (100, SCREEN_HEIGHT - 50)
    player_velocity_y = 0

def draw_menu():
    """Отрисовка главного меню."""
    screen.blit(background_img, (0,0)) # Фон меню
    draw_text("Паркур Игра", font_title, WHITE, SCREEN_WIDTH // 2, 100)
    for i, option in enumerate(menu_options):
        color = WHITE if i == selected_menu_index else GRAY
        draw_text(option, font_menu, color, SCREEN_WIDTH // 2, 250 + i * 60)

def draw_settings():
    """Отрисовка меню настроек."""
    screen.blit(background_img, (0,0))
    draw_text("Настройки", font_title, WHITE, SCREEN_WIDTH // 2, 100)
    for i, option in enumerate(settings_options):
        color = WHITE if i == selected_settings_index else GRAY
        draw_text(option, font_menu, color, SCREEN_WIDTH // 2, 250 + i * 60)
    draw_text(f"Сложность: {current_difficulty}", font_menu, WHITE, SCREEN_WIDTH // 2, 370)

def draw_game():
    """Отрисовка игрового процесса."""
    screen.blit(background_img, (0,0)) # Фон игры

    # Отрисовка платформ
    for platform in platforms:
        screen.blit(block_img, platform)

    # Отрисовка чекпоинтов
    for checkpoint in checkpoints:
        screen.blit(checkpoint_img, checkpoint)

    # Отрисовка игрока
    screen.blit(player_img, player_rect)

    # Отображение информации об уровне и сложности
    draw_text(f"Уровень: {current_level_index}", font_game, WHITE, 100, 30)
    draw_text(f"Сложность: {current_difficulty}", font_game, WHITE, SCREEN_WIDTH - 150, 30)

# --- Основной Игровой Цикл ---
# Инициализация первого уровня
create_level(current_level_data)

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # Обработка ввода
        if game_state == "menu":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected_menu_index = (selected_menu_index - 1) % len(menu_options)
                elif event.key == pygame.K_DOWN:
                    selected_menu_index = (selected_menu_index + 1) % len(menu_options)
                elif event.key == pygame.K_RETURN:
                    if menu_options[selected_menu_index] == "Начать Игру":
                        current_level_index = 1
                        current_level_data = levels[current_level_index]
                        create_level(current_level_data)
                        game_state = "playing"
                    elif menu_options[selected_menu_index] == "Настройки":
                        game_state = "settings"
                    elif menu_options[selected_menu_index] == "Выход":
                        running = False

        elif game_state == "settings":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected_settings_index = (selected_settings_index - 1) % len(settings_options)
                elif event.key == pygame.K_DOWN:
                    selected_settings_index = (selected_settings_index + 1) % len(settings_options)
                elif event.key == pygame.K_RETURN:
                    if settings_options[selected_settings_index] == "Сложность":
                        # Переключение сложности (циклически)
                        difficulty_keys = list(difficulty_levels.keys())
                        current_index = difficulty_keys.index(current_difficulty)
                        current_difficulty = difficulty_keys[(current_index + 1) % len(difficulty_keys)]
                    elif settings_options[selected_settings_index] == "Назад":
                        game_state = "menu"

        elif game_state == "playing":
            if event.type == pygame.KEYDOWN:
                # Прыжок
                if event.key == pygame.K_SPACE:
                    player_velocity_y = -difficulty_levels[current_difficulty]["jump_height"]
                    if jump_sound:
                        jump_sound.play()
            # Управление движением влево/вправо
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]:
                player_rect.x -= difficulty_levels[current_difficulty]["speed"]
            if keys[pygame.K_RIGHT]:
                player_rect.x += difficulty_levels[current_difficulty]["speed"]

    # --- Обновление Игрового Состояния ---
    if game_state == "playing":
        update_player()

    # --- Отрисовка ---
    screen.fill(DARK_GRAY) # Фон по умолчанию

    if game_state == "menu":
        draw_menu()
    elif game_state == "settings":
        draw_settings()
    elif game_state == "playing":
        draw_game()

    pygame.display.flip() # Обновление экрана

pygame.quit()
sys.exit()