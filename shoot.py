# shoot.py
import pygame, sys, random, math, time, os, cv2, mediapipe as mp
from datetime import datetime

# ---------- Init ----------
pygame.init()
pygame.mixer.init()

# ---------- Config ----------
WIDTH, HEIGHT = 900, 600
FPS = 60

ASSETS = {
    "background": "assets/background.jpg",
    "cannon": "assets/cannon.png",
    "bullet": "assets/bullet.png",
    "alien_small": "assets/alien_small.png",
    "alien_med": "assets/alien_medium.png",
    "alien_big": "assets/alien_big.png",
    "alien_bullet": "assets/alien_bullet.png",
    "alien_life": "assets/alien_life.png",          # <-- put your extra-life alien PNG here
    "explosion": "assets/explosion.png",
    "powerup_ammo": "assets/powerup_ammo.png",
    "powerup_shield": "assets/powerup_shield.png",
    "shoot_sfx": "assets/shoot.mp3",
    "explosion_sfx": "assets/explosion.mp3",
    "hit_sfx": "assets/hit.mp3",
    "powerup_sfx": "assets/powerup.mp3",
    "bg_music": "assets/background_music.mp3"
}

HIGH_SCORE_FILE = "high_score.txt"

# ---------- Audio Control ----------
is_muted = False

# ---------- Window ----------
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Space Invaders - Gesture + Keyboard")
clock = pygame.time.Clock()

# ---------- Colors & Fonts ----------
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 200, 0)
YELLOW = (255, 220, 0)
BLUE = (0, 120, 255)
STRONG_COLOR = (255, 100, 100)

FONT = pygame.font.Font(None, 28)
BIG_FONT = pygame.font.Font(None, 64)
SMALL_FONT = pygame.font.Font(None, 20)

# ---------- Utility loaders (safe) ----------
def load_image(path, size=None):
    try:
        img = pygame.image.load(path).convert_alpha()
        if size:
            img = pygame.transform.scale(img, size)
        return img
    except Exception:
        surf = pygame.Surface(size if size else (50, 50), pygame.SRCALPHA)
        surf.fill((120, 120, 120, 255))
        return surf

def load_sound(path):
    try:
        return pygame.mixer.Sound(path)
    except Exception:
        return None

# Preload simple assets (sizes chosen to look good)
background = load_image(ASSETS["background"], (WIDTH, HEIGHT))
cannon_img = load_image(ASSETS["cannon"], (72, 48))
bullet_img = load_image(ASSETS["bullet"], (10, 18))
alien_imgs = {
    "small": load_image(ASSETS["alien_small"], (36, 32)),
    "medium": load_image(ASSETS["alien_med"], (52, 40)),
    "big": load_image(ASSETS["alien_big"], (68, 54))
}
alien_life_img = load_image(ASSETS.get("alien_life", ""), (60, 50))
alien_bullet_img = load_image(ASSETS["alien_bullet"], (12, 22))
explosion_img = load_image(ASSETS["explosion"], (48, 48))
powerup_imgs = {
    "ammo": load_image(ASSETS["powerup_ammo"], (30, 30)),
    "shield": load_image(ASSETS["powerup_shield"], (36, 36))
}

# Load sounds
shoot_sfx = load_sound(ASSETS["shoot_sfx"])
explosion_sfx = load_sound(ASSETS["explosion_sfx"])
hit_sfx = load_sound(ASSETS["hit_sfx"])
powerup_sfx = load_sound(ASSETS["powerup_sfx"])

# Background music (optional)
try:
    pygame.mixer.music.load(ASSETS["bg_music"])
    pygame.mixer.music.play(-1)
except Exception:
    pass

# ---------- Icons (must be loaded before game loop runs) ----------
mute_icon = load_image("assets/mute.png", (32, 32))
unmute_icon = load_image("assets/unmute.png", (32, 32))

def set_audio_volume(vol: float):
    """Set volume for music and sfx safely (0.0 - 1.0)."""
    try:
        pygame.mixer.music.set_volume(vol)
    except:
        pass
    for s in (shoot_sfx, explosion_sfx, hit_sfx, powerup_sfx):
        try:
            if s:
                s.set_volume(vol)
        except:
            pass

def toggle_mute():
    global is_muted
    is_muted = not is_muted
    set_audio_volume(0.0 if is_muted else 1.0)

# ---------- Game constants ----------
BULLET_SPEED = -12
ALIEN_BULLET_SPEED = 4
CANNON_KEY_SPEED = 8
CANNON_SMOOTH = 0.25
MAX_AMMO = 10
START_LIVES = 3
POWERUP_SPEED = 6      # falling powerups speed
STRONG_ALIEN_HP = 4    # strong alien needs 4 hits
MAX_ALIENS = 5         # cap

# Ensure high score file exists
if not os.path.exists(HIGH_SCORE_FILE):
    open(HIGH_SCORE_FILE, "w").close()

def save_score_record(name, score, level, played_seconds):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts}|{name}|{score}|{level}|{played_seconds}\n"
    try:
        with open(HIGH_SCORE_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

def load_top_scores(n=5):
    entries = []
    try:
        with open(HIGH_SCORE_FILE, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                parts = ln.split("|")
                if len(parts) != 5:
                    continue
                ts, name, score_s, level_s, played_s = parts
                try:
                    score = int(score_s)
                except:
                    score = 0
                try:
                    played = int(played_s)
                except:
                    played = 9999
                entries.append((name, score, ts, level_s, played))
    except Exception:
        pass

    # Sort by score DESC, time ASC (shorter is better), date DESC (recent first)
    entries.sort(key=lambda e: (-e[1], e[4], -int(datetime.strptime(e[2], "%Y-%m-%d %H:%M:%S").timestamp()) if e[2] else 0))
    return entries[:n]

# ---------- Sprites ----------
class Cannon(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = cannon_img
        self.rect = self.image.get_rect(midbottom=(WIDTH // 2, HEIGHT - 12))
        self.shield = False
        self.shield_timer = 0

    def update(self, finger_x=None, key_dx=0):
        # keyboard move
        if key_dx != 0:
            self.rect.x += key_dx
        # finger movement smoothing (finger_x normalized 0..1)
        if finger_x is not None:
            target = int(finger_x * WIDTH)
            self.rect.centerx += int((target - self.rect.centerx) * CANNON_SMOOTH)
        # clamp
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > WIDTH:
            self.rect.right = WIDTH
        # shield timeout
        if self.shield and pygame.time.get_ticks() - self.shield_timer > 5000:
            self.shield = False

class PlayerBullet(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = bullet_img
        self.rect = self.image.get_rect(midbottom=(x, y))
        self.vy = BULLET_SPEED

    def update(self):
        self.rect.y += self.vy
        if self.rect.bottom < 0:
            self.kill()

class AlienBullet(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = alien_bullet_img
        self.rect = self.image.get_rect(midtop=(x, y))
        self.vy = ALIEN_BULLET_SPEED

    def update(self):
        self.rect.y += self.vy
        if self.rect.top > HEIGHT:
            self.kill()

class Alien(pygame.sprite.Sprite):
    def __init__(self, x, y, typ="small", fire_enabled=False, strong=False):
        super().__init__()
        self.typ = typ
        self.strong = strong
        if strong:
            self.image = alien_life_img if alien_life_img else pygame.Surface((60, 50), pygame.SRCALPHA)
            if not alien_life_img:
                self.image.fill(STRONG_COLOR)
        else:
            self.image = alien_imgs.get(typ, alien_imgs["small"])
        self.rect = self.image.get_rect(topleft=(x, y))
        # hp mapping
        self.max_hp = STRONG_ALIEN_HP if strong else {"small": 1, "medium": 2, "big": 3}.get(typ, 1)
        self.hp = self.max_hp
        self.t = 0.0
        self.path = random.choice(["sine", "zigzag", "random"])
        self.fire_enabled = fire_enabled
        self.shoot_delay = random.randint(1800, 3800)
        self.last_shot = pygame.time.get_ticks()

    def update(self):
        self.t += 0.08
        if not self.strong:
            if self.path == "sine":
                self.rect.x += int(3 * math.sin(self.t * 3))
                self.rect.y += 0.06
            elif self.path == "zigzag":
                self.rect.x += int(3 * math.sin(self.t * 5))
                self.rect.y += 0.06
            else:
                self.rect.x += random.choice([-2, 0, 2])
                self.rect.y += 0.06
        # clamp
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > WIDTH:
            self.rect.right = WIDTH
        # shooting only if enabled (allowed only after level 5)
        if self.fire_enabled and len(alien_bullets) < 6 and not self.strong:
            now = pygame.time.get_ticks()
            if now - self.last_shot > self.shoot_delay:
                ab = AlienBullet(self.rect.centerx, self.rect.bottom)
                all_sprites.add(ab); alien_bullets.add(ab)
                self.last_shot = now

    def draw_health(self, surf):
        w = self.rect.width
        h = 6
        fill = int((self.hp / max(1, self.max_hp)) * w)
        pygame.draw.rect(surf, (40, 40, 40), (self.rect.x, self.rect.y - 10, w, h))
        pygame.draw.rect(surf, RED, (self.rect.x, self.rect.y - 10, w, h))
        pygame.draw.rect(surf, GREEN, (self.rect.x, self.rect.y - 10, fill, h))

class StrongAlien(Alien):
    def __init__(self, y=80, speed=4):
        super().__init__(0, y, typ="big", fire_enabled=False, strong=True)
        # set image rect again if we used a different image
        if alien_life_img:
            self.image = alien_life_img
            self.rect = self.image.get_rect(topleft=(0, y))
        self.vx = speed if random.choice([True, False]) else -speed
        # start off-screen accordingly
        if self.vx > 0:
            self.rect.left = -self.rect.width
        else:
            self.rect.right = WIDTH + self.rect.width

        # lifespan (ms)
        self.spawn_time = pygame.time.get_ticks()
        self.lifespan = 15000  # 15 seconds

    def update(self):
        # horizontal sweep and bounce at edges
        self.rect.x += self.vx
        if self.rect.left <= 0:
            self.rect.left = 0
            self.vx = -self.vx
        if self.rect.right >= WIDTH:
            self.rect.right = WIDTH
            self.vx = -self.vx

        # remove after lifespan
        if pygame.time.get_ticks() - self.spawn_time > self.lifespan:
            self.kill()

class Explosion(pygame.sprite.Sprite):
    def __init__(self, pos):
        super().__init__()
        self.image = explosion_img
        self.rect = self.image.get_rect(center=pos)
        self.start = pygame.time.get_ticks()
        self.duration = 300

    def update(self):
        if pygame.time.get_ticks() - self.start > self.duration:
            self.kill()

class PowerUp(pygame.sprite.Sprite):
    def __init__(self, kind, x, y):
        super().__init__()
        self.kind = kind
        self.image = powerup_imgs.get(kind, powerup_imgs["ammo"])
        self.rect = self.image.get_rect(center=(x, y))

    def update(self):
        self.rect.y += POWERUP_SPEED
        if self.rect.top > HEIGHT:
            self.kill()

# ---------- Groups ----------
all_sprites = pygame.sprite.Group()
player_bullets = pygame.sprite.Group()
aliens = pygame.sprite.Group()
alien_bullets = pygame.sprite.Group()
powerups = pygame.sprite.Group()
explosions = pygame.sprite.Group()

# ---------- Helpers ----------
def create_aliens(level):
    n = min(1 + level, MAX_ALIENS)
    new_aliens = []
    for i in range(n):
        x = random.randint(40, WIDTH - 140)
        y = random.randint(40, 140)
        typ = random.choice(["small", "medium", "big"])
        fire = (level > 5)
        a = Alien(x, y, typ, fire_enabled=fire, strong=False)
        aliens.add(a); all_sprites.add(a)
        new_aliens.append(a)
    # spawn extra-life strong alien every 2 stages
    if level % 2 == 0:
        sa = StrongAlien(y=random.randint(50, 120), speed=4)
        aliens.add(sa); all_sprites.add(sa)
        new_aliens.append(sa)
    return new_aliens

def draw_hud(name, score, level, lives, ammo, start_time, elapsed_pause_time=0):
    # Player name and Score
    screen.blit(FONT.render(f"Player: {name}", True, WHITE), (12, 8))
    screen.blit(FONT.render(f"Score: {score}", True, WHITE), (12, 36))
    screen.blit(FONT.render(f"Level: {level}", True, WHITE), (WIDTH - 150, 8))

    # Lives and Ammo horizontally side by side
    lives_text = FONT.render(f"Lives: {lives}", True, RED)
    ammo_text = FONT.render(f"Ammo: {ammo}", True, GREEN)

    # Positions
    lives_x = WIDTH // 2 - lives_text.get_width() - 10
    ammo_x = WIDTH // 2 + 10
    top_y = 8

    screen.blit(lives_text, (lives_x, top_y))
    screen.blit(ammo_text, (ammo_x, top_y))

    # Time below lives and ammo
    played = int(time.time() - start_time - elapsed_pause_time)
    time_text = FONT.render(f"Time: {time.strftime('%M:%S', time.gmtime(played))}", True, WHITE)
    time_x = WIDTH // 2 - time_text.get_width() // 2
    time_y = top_y + lives_text.get_height() + 4
    screen.blit(time_text, (time_x, time_y))

def get_player_name_screen():
    name = ""
    active = True
    blink = True
    blink_timer = 0
    blink_interval = 500  # milliseconds

    while active:
        dt = clock.tick(FPS)
        blink_timer += dt
        if blink_timer >= blink_interval:
            blink_timer = 0
            blink = not blink  # toggle cursor visibility

        screen.fill(BLACK)
        prompt = BIG_FONT.render("Enter your name", True, YELLOW)
        screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, HEIGHT // 2 - 120))

        box = pygame.Rect(WIDTH // 2 - 220, HEIGHT // 2 - 20, 440, 48)
        pygame.draw.rect(screen, WHITE, box, 2)

        txt = FONT.render(name, True, WHITE)
        screen.blit(txt, (box.x + 8, box.y + 10))

        # Draw blinking cursor
        if blink:
            cursor_x = box.x + 8 + txt.get_width() + 2
            cursor_y = box.y + 8
            cursor_h = txt.get_height()
            pygame.draw.line(screen, WHITE, (cursor_x, cursor_y), (cursor_x, cursor_y + cursor_h), 2)

        hint = SMALL_FONT.render("Max 12 chars. Press Enter to continue.", True, WHITE)
        screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, box.y + 60))

        pygame.display.flip()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                cleanup_and_quit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN:
                    active = False
                elif ev.key == pygame.K_BACKSPACE:
                    name = name[:-1]
                else:
                    if len(name) < 12 and ev.unicode.isprintable():
                        name += ev.unicode

    return name.strip() or "Player"


def cleanup_and_quit():
    try:
        if 'hands' in globals() and hands:
            hands.close()
    except:
        pass
    try:
        if 'cap' in globals() and cap and cap.isOpened():
            cap.release()
        cv2.destroyAllWindows()
    except:
        pass
    try:
        pygame.mixer.music.stop()
    except:
        pass
    pygame.quit()
    sys.exit()

# ---------- MediaPipe (gesture) ----------
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.5, min_tracking_confidence=0.5)

# Initialize webcam safely
cap = None
try:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap.release()
        cap = None
except Exception:
    cap = None

# ---------- Game Over UI ----------
def show_game_over(player_name, score, level, played_seconds):
    top = load_top_scores(5)
    showing = True
    star_surf = FONT.render(" * ", True, YELLOW)

    # Adjusted layout
    box_w, box_h = 800, 300
    box_x, box_y = WIDTH // 2 - box_w // 2, 160
    row_height = 36
    padding_x = 20

    col_x = {
        "rank": box_x + padding_x,
        "name": box_x + 70,
        "score": box_x + 300,
        "level": box_x + 400,
        "time": box_x + 480,
        "date": box_x + 570
    }

    header_titles = ["Rank", "Name", "Score", "Level", "Time", "Date"]

    while showing:
        clock.tick(FPS)
        screen.fill(BLACK)

        title_surf = BIG_FONT.render("GAME OVER", True, RED)
        screen.blit(title_surf, (WIDTH // 2 - title_surf.get_width() // 2, 40))

        summary = FONT.render(
            f"{player_name}  —  Score: {score}   Level: {level}   Time: {played_seconds}s",
            True, WHITE
        )
        screen.blit(summary, (WIDTH // 2 - summary.get_width() // 2, 120))

        pygame.draw.rect(screen, (40, 40, 40), (box_x, box_y, box_w, box_h))
        pygame.draw.rect(screen, WHITE, (box_x, box_y, box_w, box_h), 2)

        for i, key in enumerate(col_x.keys()):
            screen.blit(FONT.render(header_titles[i], True, YELLOW), (col_x[key], box_y + 12))

        y = box_y + 50
        for idx, rec in enumerate(top, start=1):
            name, sc, ts, lvl_rec, played = rec
            is_current = (name == player_name and sc == score and int(played) == played_seconds)

            if is_current:
                highlight_rect = pygame.Surface((box_w - 2 * padding_x, row_height - 4), pygame.SRCALPHA)
                highlight_rect.fill((255, 255, 0, 50))
                screen.blit(highlight_rect, (box_x + padding_x, y - 2))

            color = YELLOW if is_current else WHITE
            screen.blit(FONT.render(f"{idx}", True, color), (col_x["rank"], y))
            screen.blit(FONT.render(name[:12], True, color), (col_x["name"], y))
            screen.blit(FONT.render(f"{sc}", True, color), (col_x["score"], y))
            screen.blit(FONT.render(f"{lvl_rec}", True, color), (col_x["level"], y))
            screen.blit(FONT.render(f"{played}", True, color), (col_x["time"], y))
            screen.blit(FONT.render(ts, True, color), (col_x["date"], y))

            if is_current:
                screen.blit(star_surf, (col_x["name"] - 25, y))

            y += row_height
            if y > box_y + box_h - 28:
                break

        instr = FONT.render("Press R to Restart or ESC to Quit", True, WHITE)
        screen.blit(instr, (WIDTH // 2 - instr.get_width() // 2, box_y + box_h + 12))

        pygame.display.flip()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                cleanup_and_quit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    if confirm_quit():
                        cleanup_and_quit()

                if ev.key == pygame.K_r:
                    showing = False
                    return

# ---------- Main game loop ----------
def run_game(player_name):
    global is_muted
    # reset groups
    all_sprites.empty(); player_bullets.empty(); aliens.empty(); alien_bullets.empty(); powerups.empty(); explosions.empty()

    cannon = Cannon()
    all_sprites.add(cannon)

    level = 1
    score = 0
    lives = START_LIVES
    ammo = MAX_AMMO
    start_time = time.time()
    # ---------- NEW: Initialize pause tracking ----------
    paused = False
    elapsed_pause_time = 0
    # spawn aliens
    create_aliens(level)

    key_dx = 0
    shot_locked = False   # prevents repeated shots while fingers remain open

    running = True
    while running:
        clock.tick(FPS)
        now = time.time()

        # ---------- Webcam + gesture detection ----------
        finger_x = None
        index_open = False
        middle_open = False
        if cap is not None:
            ret, frame = cap.read()
            if ret and frame is not None:
                frame = cv2.flip(frame, 1)
                try:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    res = hands.process(rgb)
                    if res.multi_hand_landmarks:
                        hl = res.multi_hand_landmarks[0]
                        idx_tip = hl.landmark[8]; idx_pip = hl.landmark[6]
                        mid_tip = hl.landmark[12]; mid_pip = hl.landmark[10]
                        finger_x = idx_tip.x
                        index_open = (idx_tip.y < idx_pip.y - 0.02)
                        middle_open = (mid_tip.y < mid_pip.y - 0.02)
                except Exception:
                    finger_x = None
                    index_open = False
                    middle_open = False

        # ---------- Event processing ----------
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                cleanup_and_quit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    # ---------- FULL PAUSE ----------
                    paused = True
                    pause_start = time.time()
                    # show pause/confirm window and act on the user's choice
                    wants_quit = confirm_quit()
                    if wants_quit:
                        cleanup_and_quit()
                    # resume
                    paused = False
                    elapsed_pause_time += time.time() - pause_start

                if not paused:  # only movement/shooting when not paused
                    if ev.key == pygame.K_LEFT:
                        key_dx = -CANNON_KEY_SPEED
                    if ev.key == pygame.K_RIGHT:
                        key_dx = CANNON_KEY_SPEED
                    if ev.key == pygame.K_SPACE:
                        if ammo > 0 and len(player_bullets) == 0:
                            b = PlayerBullet(cannon.rect.centerx, cannon.rect.top)
                            all_sprites.add(b)
                            player_bullets.add(b)
                            ammo -= 1
                            try:
                                if shoot_sfx and not is_muted:
                                    shoot_sfx.play()
                            except:
                                pass
                    if ev.key == pygame.K_m:
                        toggle_mute()

            if ev.type == pygame.KEYUP:
                if not paused:
                    if ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        key_dx = 0

        # ---------- Gesture shooting logic ----------
        if not paused:  # freeze gestures while paused
            if index_open and middle_open and not shot_locked:
                if ammo > 0 and len(player_bullets) == 0:
                    b = PlayerBullet(cannon.rect.centerx, cannon.rect.top)
                    all_sprites.add(b); player_bullets.add(b)
                    ammo -= 1
                    try:
                        if shoot_sfx and not is_muted:
                            shoot_sfx.play()
                    except:
                        pass
                shot_locked = True
            if not index_open and not middle_open:
                shot_locked = False

            # ---------- Update sprites ----------
            for spr in list(all_sprites):
                if isinstance(spr, Cannon):
                    continue
                spr.update()
            cannon.update(finger_x=finger_x, key_dx=key_dx)

            player_bullets.update()
            alien_bullets.update()
            explosions.update()
            powerups.update()

            # ---------- Collisions ----------
            hits = pygame.sprite.groupcollide(player_bullets, aliens, True, False)
            for pb, alist in hits.items():
                for a in alist:
                    a.hp -= 1
                    if a.hp <= 0:
                        exp = Explosion(a.rect.center)
                        all_sprites.add(exp); explosions.add(exp)
                        try:
                            if explosion_sfx and not is_muted:
                                explosion_sfx.play()
                        except:
                            pass
                        if getattr(a, "strong", False):
                            score += 50
                            lives += 1
                        else:
                            score += 10 * (1 if a.typ == "small" else 2)
                        if random.random() < 0.25:
                            kind = random.choice(["ammo", "shield"]) if (level > 5) else "ammo"
                            pu = PowerUp(kind, a.rect.centerx, a.rect.centery)
                            all_sprites.add(pu); powerups.add(pu)
                        a.kill()

            hits2 = pygame.sprite.spritecollide(cannon, alien_bullets, True)
            if hits2:
                if not cannon.shield:
                    lives -= 1
                    exp = Explosion(cannon.rect.center)
                    all_sprites.add(exp); explosions.add(exp)
                    try:
                        if hit_sfx and not is_muted:
                            hit_sfx.play()
                    except:
                        pass
                else:
                    cannon.shield = False

            p_hits = pygame.sprite.spritecollide(cannon, powerups, True)
            for pu in p_hits:
                try:
                    if powerup_sfx and not is_muted:
                        powerup_sfx.play()
                except:
                    pass
                if pu.kind == "ammo":
                    ammo += 5
                elif pu.kind == "shield":
                    if level > 5:
                        cannon.shield = True
                        cannon.shield_timer = pygame.time.get_ticks()

            # ---------- Level progression ----------
            if len(aliens) == 0:
                level += 1
                ammo = MAX_AMMO
                create_aliens(level)
                for a in list(aliens):
                    if not getattr(a, "strong", False):
                        a.fire_enabled = (level > 5)

        # ---------- Draw ----------
        screen.blit(background, (0, 0))
        for s in all_sprites:
            screen.blit(s.image, s.rect)
        for a in aliens:
            a.draw_health(screen)
        draw_hud(player_name, score, level, lives, ammo, start_time, elapsed_pause_time)
        if cannon.shield:
            pygame.draw.circle(screen, BLUE, cannon.rect.center, 42, 3)

        # Draw mute/unmute icon
        icon = mute_icon if is_muted else unmute_icon
        screen.blit(icon, (WIDTH - icon.get_width() - 12, 12))

        pygame.display.flip()

        # ---------- End conditions ----------
        if lives <= 0 or (ammo <= 0 and len(player_bullets) == 0):
            played_seconds = int(time.time() - start_time)
            save_score_record(player_name, score, level, played_seconds)
            show_game_over(player_name, score, level, played_seconds)
            return

# ---------- Instruction Screen ----------
def show_instructions():
    showing = True
    lines = [
        "Controls:",
        " - Move Cannon: Arrow Keys or Hand Gestures",
        " - Shoot: SPACE or Open Index + Middle fingers",
        "",
        "Tips:",
        " - Collect power-ups for extra ammo or shield",
        " - Kill strong aliens to gain +1 life",
        " - Game ends if lives = 0 or ammo runs out"
    ]
    while showing:
        clock.tick(FPS)
        screen.fill(BLACK)
        title = BIG_FONT.render("HOW TO PLAY", True, YELLOW)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 60))

        y = 160
        for ln in lines:
            txt = FONT.render(ln, True, WHITE)
            screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, y))
            y += 40

        hint = FONT.render("Press ENTER to Start", True, GREEN)
        screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT - 80))

        pygame.display.flip()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                cleanup_and_quit()
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN:
                showing = False
                return

# ---------- Quit Confirmation ----------
def confirm_quit():
    """Return True if player confirms quit, False to continue."""
    options = ["YES", "NO"]
    selected = 1  # default on NO
    running = True
    blink_interval = 500  # milliseconds for blinking text

    while running:
        clock.tick(FPS)
        screen.fill(BLACK)

        # --- Blinking GAME PAUSED ---
        now = pygame.time.get_ticks()
        if (now // blink_interval) % 2 == 0:  # toggle visibility
            paused_txt = BIG_FONT.render("GAME PAUSED", True, YELLOW)
            screen.blit(paused_txt, (WIDTH // 2 - paused_txt.get_width() // 2, HEIGHT // 2 - 160))

        # Quit confirmation text
        title = BIG_FONT.render("Are you sure you want to quit?", True, RED)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 100))

        for i, opt in enumerate(options):
            color = GREEN if i == selected else WHITE
            txt = BIG_FONT.render(opt, True, color)
            screen.blit(txt, (WIDTH // 2 - 120 + i * 180, HEIGHT // 2))

        instr = FONT.render("Use <=/=> keys to select, ENTER to confirm", True, WHITE)
        screen.blit(instr, (WIDTH // 2 - instr.get_width() // 2, HEIGHT // 2 + 100))

        pygame.display.flip()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return True
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_LEFT:
                    selected = max(0, selected - 1)
                elif ev.key == pygame.K_RIGHT:
                    selected = min(len(options) - 1, selected + 1)
                elif ev.key == pygame.K_RETURN:
                    running = False

    return selected == 0  # YES = 0

# ---------- Countdown ----------
def show_countdown():
    for num in ["3", "2", "1", "START!"]:
        clock.tick(FPS)
        screen.fill(BLACK)
        txt = BIG_FONT.render(num, True, RED if num != "START!" else GREEN)
        screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2 - txt.get_height() // 2))
        pygame.display.flip()
        pygame.time.delay(1000)

# ---------- Main ----------
def main():
    global player_name
    player_name = get_player_name_screen()
    show_instructions()
    try:
        while True:
            show_countdown()
            run_game(player_name)
    finally:
        try:
            if hands:
                hands.close()
        except:
            pass
        try:
            if cap and cap.isOpened():
                cap.release()
            cv2.destroyAllWindows()
        except:
            pass
        pygame.quit()

if __name__ == "__main__":
    main()
