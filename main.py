"""A small Pygame dungeon game using PNG assets.

Controls
--------
Move: W A S D
Shoot: Arrow keys
Start / restart: SPACE or R
Quit: ESC
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pygame


WIDTH, HEIGHT = 800, 600
FPS = 60
WALL_THICK = 40
DOOR_SIZE = 90

COLOR_BG = (26, 22, 20)
COLOR_FLOOR_A = (74, 68, 62)
COLOR_FLOOR_B = (68, 62, 56)
COLOR_WALL = (40, 36, 33)
COLOR_WALL_EDGE = (20, 18, 16)
COLOR_DOOR_LOCKED = (40, 36, 33)
COLOR_DOOR_OPEN = (92, 58, 30)
COLOR_HEART_FULL = (200, 40, 40)
COLOR_HEART_EMPTY = (60, 40, 40)
COLOR_TEXT = (225, 220, 205)
COLOR_TEXT_DIM = (150, 145, 135)


def clamp(value, low, high):
    return max(low, min(high, value))


def load_image(path: Path, size: tuple[int, int]) -> pygame.Surface:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required image: {path}")
    return pygame.transform.scale(pygame.image.load(path).convert_alpha(), size)


def flash_image(image: pygame.Surface, color: tuple[int, int, int]) -> pygame.Surface:
    flashed = image.copy()
    blend = pygame.BLEND_RGB_ADD if color == (255, 255, 255) else pygame.BLEND_RGB_MULT
    flashed.fill(color, special_flags=blend)
    return flashed


class Projectile(pygame.sprite.Sprite):
    def __init__(self, x, y, dx, dy, speed, size, damage, image):
        super().__init__()
        self.rect = pygame.FRect(0, 0, size, size)
        self.rect.center = (x, y)
        direction = pygame.Vector2(dx, dy)
        if direction.length_squared() == 0:
            direction = pygame.Vector2(0, -1)
        self.direction = direction.normalize()
        self.vx = self.direction.x * speed
        self.vy = self.direction.y * speed
        self.damage = damage

        # Asset art should point upward by default. Rotate it to travel direction.
        angle = self.direction.angle_to(pygame.Vector2(0, -1))
        self.image = pygame.transform.rotate(image, angle)

    def update(self, dt, bounds):
        self.rect.x += self.vx * dt
        self.rect.y += self.vy * dt
        if not bounds.contains(self.rect):
            self.kill()

    def draw(self, screen):
        screen.blit(self.image, self.image.get_rect(center=self.rect.center))


class Player(pygame.sprite.Sprite):
    SIZE = 68
    SPEED = 230
    SHOT_COOLDOWN = 0.28
    HURT_COOLDOWN = 0.9

    def __init__(self, x, y, images):
        super().__init__()
        self.rect = pygame.FRect(0, 0, self.SIZE, self.SIZE)
        self.rect.center = (x, y)
        self.image = images["player"]
        self.arrow_image = images["arrow"]
        self.max_hp = 5
        self.hp = self.max_hp
        self.facing = pygame.Vector2(0, -1)
        self.shot_timer = 0.0
        self.hurt_timer = 0.0
        self.arrows = pygame.sprite.Group()

    def handle_input(self, dt, keys):
        move = pygame.Vector2(keys[pygame.K_d] - keys[pygame.K_a],
                              keys[pygame.K_s] - keys[pygame.K_w])
        if move.length_squared() > 0:
            move = move.normalize()
            self.rect.x += move.x * self.SPEED * dt
            self.rect.y += move.y * self.SPEED * dt

        aim = pygame.Vector2(keys[pygame.K_RIGHT] - keys[pygame.K_LEFT],
                             keys[pygame.K_DOWN] - keys[pygame.K_UP])
        if aim.length_squared() > 0:
            self.facing = aim.normalize()
            if self.shot_timer <= 0:
                self.shoot()

    def shoot(self):
        self.arrows.add(Projectile(self.rect.centerx, self.rect.centery,
                                   self.facing.x, self.facing.y, 460, 10, 1,
                                   self.arrow_image))
        self.shot_timer = self.SHOT_COOLDOWN

    def take_damage(self, amount):
        if self.hurt_timer <= 0:
            self.hp = clamp(self.hp - amount, 0, self.max_hp)
            self.hurt_timer = self.HURT_COOLDOWN

    def update(self, dt, keys, bounds):
        self.shot_timer = max(0.0, self.shot_timer - dt)
        self.hurt_timer = max(0.0, self.hurt_timer - dt)
        self.handle_input(dt, keys)
        self.arrows.update(dt, bounds.inflate(200, 200))

    def draw(self, screen):
        flashing = self.hurt_timer > 0 and int(self.hurt_timer * 12) % 2 == 0
        image = flash_image(self.image, (255, 130, 130)) if flashing else self.image
        screen.blit(image, image.get_rect(center=self.rect.center))
        for arrow in self.arrows:
            arrow.draw(screen)


class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y, size, hp, speed, contact_damage, image):
        super().__init__()
        self.rect = pygame.FRect(0, 0, size, size)
        self.rect.center = (x, y)
        self.hp = self.max_hp = hp
        self.speed = speed
        self.contact_damage = contact_damage
        self.image = image
        self.hit_flash = 0.0

    def chase(self, dt, target_pos, bounds):
        direction = pygame.Vector2(target_pos) - pygame.Vector2(self.rect.center)
        if direction.length_squared() > 1:
            direction = direction.normalize()
            self.rect.x += direction.x * self.speed * dt
            self.rect.y += direction.y * self.speed * dt
            self.rect.clamp_ip(bounds)

    def take_damage(self, amount):
        self.hp -= amount
        self.hit_flash = 0.12
        if self.hp <= 0:
            self.kill()

    def update(self, dt, player_pos, bounds):
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.chase(dt, player_pos, bounds)

    def draw(self, screen):
        image = flash_image(self.image, (255, 255, 255)) if self.hit_flash > 0 else self.image
        screen.blit(image, image.get_rect(center=self.rect.center))
        self.draw_hp_bar(screen)

    def draw_hp_bar(self, screen):
        if self.hp >= self.max_hp:
            return
        back = pygame.Rect(int(self.rect.left), int(self.rect.top) - 8, int(self.rect.width), 4)
        pygame.draw.rect(screen, (20, 20, 20), back)
        front = pygame.Rect(back.left, back.top, int(back.width * self.hp / self.max_hp), 4)
        pygame.draw.rect(screen, (200, 40, 40), front)


class Goblin(Enemy):
    def __init__(self, x, y, images):
        super().__init__(x, y, 56, 2, 150, 1, images["goblin"])


class Skeleton(Enemy):
    def __init__(self, x, y, images):
        super().__init__(x, y, 60, 4, 105, 1, images["skeleton"])


class Boss(Enemy):
    def __init__(self, x, y, images):
        super().__init__(x, y, 128, 26, 95, 2, images["boss"])
        self.bolt_image = images["bolt"]
        self.bolt_timer = 1.5
        self.bolts = pygame.sprite.Group()

    def update(self, dt, player_pos, bounds):
        super().update(dt, player_pos, bounds)
        self.bolt_timer -= dt
        if self.bolt_timer <= 0:
            self.bolt_timer = 1.6
            direction = pygame.Vector2(player_pos) - pygame.Vector2(self.rect.center)
            self.bolts.add(Projectile(self.rect.centerx, self.rect.centery,
                                      direction.x, direction.y, 240, 14, 1,
                                      self.bolt_image))
        self.bolts.update(dt, bounds.inflate(200, 200))

    def draw(self, screen):
        super().draw(screen)
        for bolt in self.bolts:
            bolt.draw(screen)


class Room:
    def __init__(self, name, enemy_specs, has_left_door, has_right_door, images):
        self.name = name
        self.has_left_door = has_left_door
        self.has_right_door = has_right_door
        self.bounds = pygame.FRect(WALL_THICK, WALL_THICK, WIDTH - 2 * WALL_THICK,
                                   HEIGHT - 2 * WALL_THICK)
        self.enemies = pygame.sprite.Group(*(enemy_type(x, y, images)
                                             for enemy_type, x, y in enemy_specs))
        self.cleared = not self.enemies
        self.entered = False

    @property
    def right_door_rect(self):
        return pygame.Rect(WIDTH - WALL_THICK, HEIGHT // 2 - DOOR_SIZE // 2,
                           WALL_THICK, DOOR_SIZE)

    @property
    def left_door_rect(self):
        return pygame.Rect(0, HEIGHT // 2 - DOOR_SIZE // 2, WALL_THICK, DOOR_SIZE)

    def update_cleared(self):
        self.cleared = not self.enemies

    def draw(self, screen):
        tile = 40
        for ty in range(int(self.bounds.top), int(self.bounds.bottom), tile):
            for tx in range(int(self.bounds.left), int(self.bounds.right), tile):
                color = COLOR_FLOOR_A if (tx // tile + ty // tile) % 2 == 0 else COLOR_FLOOR_B
                pygame.draw.rect(screen, color, (tx, ty, tile, tile))
        pygame.draw.rect(screen, COLOR_WALL, (0, 0, WIDTH, WALL_THICK))
        pygame.draw.rect(screen, COLOR_WALL, (0, HEIGHT - WALL_THICK, WIDTH, WALL_THICK))
        pygame.draw.rect(screen, COLOR_WALL, (0, 0, WALL_THICK, HEIGHT))
        pygame.draw.rect(screen, COLOR_WALL, (WIDTH - WALL_THICK, 0, WALL_THICK, HEIGHT))
        pygame.draw.rect(screen, COLOR_WALL_EDGE, (0, 0, WIDTH, HEIGHT), 4)
        if self.has_left_door:
            pygame.draw.rect(screen, COLOR_DOOR_OPEN, self.left_door_rect)
        if self.has_right_door:
            pygame.draw.rect(screen, COLOR_DOOR_OPEN if self.cleared else COLOR_DOOR_LOCKED,
                             self.right_door_rect)


def build_rooms(images):
    return [
        Room("Room 1", [], False, True, images),
        Room("Room 2", [(Goblin, random.randint(400, 650), random.randint(150, 450))
                         for _ in range(random.randint(2, 5))], True, True, images),
        Room("Room 3", [(random.choice((Skeleton, Goblin)), random.randint(400, 650),
                          random.randint(150, 450)) for _ in range(random.randint(3, 6))],
             True, True, images),
        Room("Boss Room", [(Boss, WIDTH // 2 + 60, HEIGHT // 2)], True, False, images),
    ]


class GameState:
    TITLE = "title"
    PLAYING = "playing"
    GAME_OVER = "game_over"
    WIN = "win"


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Game")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.SysFont("georgia", 52, bold=True)
        self.font_mid = pygame.font.SysFont("georgia", 28, bold=True)
        self.font_small = pygame.font.SysFont("georgia", 18)

        asset_dir = Path(__file__).resolve().parent / "assets"
        self.images = {
            "player": load_image(asset_dir / "player.png", (68, 68)),
            "goblin": load_image(asset_dir / "goblin.png", (56, 56)),
            "skeleton": load_image(asset_dir / "skeleton.png", (60, 60)),
            "boss": load_image(asset_dir / "boss.png", (128, 128)),
            "arrow": load_image(asset_dir / "arrow.png", (10, 10)),
            "bolt": load_image(asset_dir / "bolt.png", (14, 14)),
        }
        self.menu_image = load_image(asset_dir / "menu_background.png", (WIDTH, HEIGHT))
        self.state = GameState.TITLE
        self.reset()

    def reset(self):
        self.rooms = build_rooms(self.images)
        self.room_index = 0
        self.player = Player(WIDTH // 2, HEIGHT // 2, self.images)
        self.rooms[0].entered = True

    @property
    def room(self):
        return self.rooms[self.room_index]

    def update_playing(self, dt, keys):
        room = self.room
        self.player.update(dt, keys, room.bounds)
        self.clamp_player_to_room(room)
        room.enemies.update(dt, self.player.rect.center, room.bounds)
        room.update_cleared()

        for arrow in list(self.player.arrows):
            enemy = pygame.sprite.spritecollideany(arrow, room.enemies)
            if enemy:
                enemy.take_damage(arrow.damage)
                arrow.kill()

        for enemy in room.enemies:
            if self.player.rect.colliderect(enemy.rect):
                self.player.take_damage(enemy.contact_damage)
            if isinstance(enemy, Boss):
                for bolt in list(enemy.bolts):
                    if bolt.rect.colliderect(self.player.rect):
                        self.player.take_damage(bolt.damage)
                        bolt.kill()

        if self.player.hp <= 0:
            self.state = GameState.GAME_OVER
        elif room.cleared and room.has_right_door and self.player.rect.colliderect(room.right_door_rect):
            self.go_to_next_room()
        elif room.name == "Boss Room" and room.cleared and room.entered:
            self.state = GameState.WIN

    def clamp_player_to_room(self, room):
        player = self.player.rect
        bounds = room.bounds
        player.top = max(player.top, bounds.top)
        player.bottom = min(player.bottom, bounds.bottom)
        in_left_door = room.has_left_door and room.left_door_rect.top < player.centery < room.left_door_rect.bottom
        player.left = max(player.left, 4 if in_left_door else bounds.left)
        in_right_door = (room.cleared and room.has_right_door
                         and room.right_door_rect.top < player.centery < room.right_door_rect.bottom)
        player.right = min(player.right, WIDTH - 4 if in_right_door else bounds.right)

    def go_to_next_room(self):
        if self.room_index + 1 >= len(self.rooms):
            self.state = GameState.WIN
            return
        self.room_index += 1
        self.room.entered = True
        self.player.rect.midleft = (WALL_THICK + 4, HEIGHT // 2)

    def draw_hud(self, screen, room):
        for index in range(self.player.max_hp):
            color = COLOR_HEART_FULL if index < self.player.hp else COLOR_HEART_EMPTY
            pygame.draw.rect(screen, color, (16 + index * 26, 16, 20, 20), border_radius=5)
        label = self.font_small.render(f"{room.name}  ({self.room_index + 1}/{len(self.rooms)})",
                                       True, COLOR_TEXT_DIM)
        screen.blit(label, (WIDTH - label.get_width() - 16, 16))
        if not room.cleared and room.enemies:
            hint = self.font_small.render("Defeat all enemies to open the door!", True, COLOR_TEXT_DIM)
            screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, 16))

    def draw_playing(self, screen):
        self.room.draw(screen)
        for enemy in self.room.enemies:
            enemy.draw(screen)
        self.player.draw(screen)
        self.draw_hud(screen, self.room)

    def draw_overlay(self, screen, headline, subline, color):
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        screen.blit(shade, (0, 0))
        title = self.font_big.render(headline, True, color)
        subtitle = self.font_small.render(subline, True, COLOR_TEXT)
        screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 20)))
        screen.blit(subtitle, subtitle.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 32)))

    def draw_title(self, screen):
        screen.blit(self.menu_image, (0, 0))
        panel = pygame.Surface((510, 210), pygame.SRCALPHA)
        panel.fill((12, 10, 9, 185))
        panel_rect = panel.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 8))
        screen.blit(panel, panel_rect)

        title = self.font_big.render("Game", True, COLOR_TEXT)
        prompt = self.font_mid.render("Press SPACE to start", True, (245, 210, 100))
        controls = self.font_small.render("Move: WASD     Shoot: Arrow Keys", True, COLOR_TEXT)
        screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 70)))
        screen.blit(prompt, prompt.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
        screen.blit(controls, controls.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 50)))

    def draw(self):
        self.screen.fill(COLOR_BG)
        if self.state == GameState.TITLE:
            self.draw_title(self.screen)
        else:
            self.draw_playing(self.screen)
            if self.state == GameState.GAME_OVER:
                self.draw_overlay(self.screen, "YOU HAVE DIED", "Press R to try again", (150, 30, 30))
            elif self.state == GameState.WIN:
                self.draw_overlay(self.screen, "GG You Won!",
                                  "Game by Sameer, Hussein, Hesham, Arav - Press R to play again",
                                  (30, 100, 60))
        pygame.display.flip()

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        pygame.quit()
                        sys.exit()
                    if event.key == pygame.K_SPACE and self.state == GameState.TITLE:
                        self.state = GameState.PLAYING
                    if event.key == pygame.K_r and self.state in (GameState.GAME_OVER, GameState.WIN):
                        self.reset()
                        self.state = GameState.PLAYING
            if self.state == GameState.PLAYING:
                self.update_playing(dt, pygame.key.get_pressed())
            self.draw()


if __name__ == "__main__":
    try:
        Game().run()
    except FileNotFoundError as error:
        print(error)
        pygame.quit()
