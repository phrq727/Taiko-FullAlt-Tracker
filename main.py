import pygame
from pynput import keyboard
from threading import Thread, Lock
import tkinter as tk
from tkinter import filedialog
import os, sys
import time
import json

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
    
icon_path = resource_path("assets/icon.png")
font_path = resource_path("assets/font.ttf")
sound_path = resource_path("assets/altbreak.wav")

pygame.init()
pygame.mixer.init()

WIDTH, HEIGHT = 330, 520 
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Phrq's FullAlt Tracker v1.1.1")

if os.path.exists(icon_path):
    pygame.display.set_icon(pygame.image.load(icon_path))

# --- ШРИФТЫ ---
FONT_NAME = font_path
def get_font(size):
    if os.path.exists(FONT_NAME):
        return pygame.font.Font(FONT_NAME, size)
    return pygame.font.SysFont(None, size)

font = get_font(32)
small = get_font(20)
tiny = get_font(14)

# --- ЦВЕТА ---
KAT_COLOR = (80, 160, 255)
DON_COLOR = (255, 80, 80)
TOTAL_GRAY = (170, 170, 170)
TEXT_GRAY = (150, 150, 150)
RESET_SETTINGS_COLOR = (153, 153, 153)
P_RED, P_GREEN = (180, 120, 120), (120, 180, 120)
ACC_PURPLE = (197, 138, 249)

# --- ПЕРЕМЕННЫЕ ---
stats_lock = Lock()
random_roll, double_press = 0, 0
total_game_presses = 0 
last_key, last_hand = None, None
pressed_keys = set()
running = True

audio_loaded, audio_active = False, False
audio_name, audio_path = "None", ""
audio_volume = 100
sound = None
error_message = ""
error_timer = 0

reset_key_id, reset_key_obj = None, None
bind_mode = False
confirm_mode = False 
LEFT_KEYS, RIGHT_KEYS = ['s', 'd'], ['k', 'l']
game_bind_mode = False
game_bind_step = 0

CONFIG_FILE = "conf.cfg"

# --- ЛОГИКА ---
def get_key_display(key):
    if key is None: return "NONE"
    special = {keyboard.Key.space: "SPACE", keyboard.Key.shift: "SHIFT", keyboard.Key.ctrl_l: "CTRL", 
               keyboard.Key.alt_l: "ALT", keyboard.Key.enter: "ENTER", keyboard.Key.f13: "F13"}
    if key in special: return special[key]
    try:
        vk = key.vk
        if 65 <= vk <= 90 or 48 <= vk <= 57: return chr(vk)
        return str(key).replace("'", "").upper()
    except: return str(key).replace("Key.", "").upper()

def get_key_id(key):
    try: return key.vk if hasattr(key, 'vk') and key.vk else str(key)
    except: return str(key)

def save_config():
    config = {"left_keys": LEFT_KEYS, "right_keys": RIGHT_KEYS, "reset_key_vk": reset_key_id, 
              "audio_path": audio_path, "audio_active": audio_active, "volume": audio_volume}
    with open(CONFIG_FILE, "w") as f: json.dump(config, f)

def validate_and_load(path, silent=False):
    global audio_loaded, sound, error_message, error_timer, audio_name, audio_path
    if not os.path.exists(path): return False
    try:
        temp_sound = pygame.mixer.Sound(path)
        if temp_sound.get_length() <= 5.0:
            sound = temp_sound
            audio_loaded, audio_path = True, path
            audio_name = os.path.basename(path)
            sound.set_volume(audio_volume / 100.0)
            return True
        elif not silent: 
            error_message = "FILE TOO LONG"; error_timer = time.time()
    except:
        if not silent: 
            error_message = "LOAD ERROR"; error_timer = time.time()
    return False

def load_config():
    global LEFT_KEYS, RIGHT_KEYS, reset_key_id, reset_key_obj, audio_path, audio_active, audio_volume
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                LEFT_KEYS = data.get("left_keys", ['s', 'd'])
                RIGHT_KEYS = data.get("right_keys", ['k', 'l'])
                reset_key_id = data.get("reset_key_vk")
                if reset_key_id:
                    if isinstance(reset_key_id, int): reset_key_obj = keyboard.KeyCode.from_vk(reset_key_id)
                    else: reset_key_obj = keyboard.Key[reset_key_id.replace("Key.", "")]
                audio_path, audio_active, audio_volume = data.get("audio_path", ""), data.get("audio_active", False), data.get("volume", 100)
                if audio_path: validate_and_load(audio_path, silent=True)
        except: pass
    if not audio_loaded:
        if validate_and_load(sound_path, silent=True): return

def reset_everything():
    global LEFT_KEYS, RIGHT_KEYS, audio_path, audio_active, audio_volume, audio_name, audio_loaded, sound, reset_key_obj, reset_key_id
    if os.path.exists(CONFIG_FILE): os.remove(CONFIG_FILE)
    LEFT_KEYS, RIGHT_KEYS, audio_path, audio_active, audio_volume = ['s', 'd'], ['k', 'l'], "", False, 100
    audio_name, audio_loaded, sound, reset_key_obj, reset_key_id = "None", False, None, None, None
    load_config()

def on_press(key):
    global bind_mode, reset_key_obj, reset_key_id, game_bind_mode, game_bind_step, random_roll, double_press, total_game_presses, last_key, last_hand
    k_name = get_key_display(key).lower()
    if bind_mode: reset_key_obj, reset_key_id = key, get_key_id(key); bind_mode = False; return
    if game_bind_mode:
        if game_bind_step == 0: LEFT_KEYS[0] = k_name
        elif game_bind_step == 1: LEFT_KEYS[1] = k_name
        elif game_bind_step == 2: RIGHT_KEYS[0] = k_name
        elif game_bind_step == 3: RIGHT_KEYS[1] = k_name
        game_bind_step += 1
        if game_bind_step >= 4: game_bind_mode = False
        return
    if key == keyboard.Key.f13 or (reset_key_obj and key == reset_key_obj):
        with stats_lock: random_roll, double_press, total_game_presses, last_key, last_hand = 0, 0, 0, None, None; pressed_keys.clear()
        return
    if k_name in pressed_keys: return
    pressed_keys.add(k_name)
    if k_name not in LEFT_KEYS and k_name not in RIGHT_KEYS: return
    curr_hand = 'L' if k_name in LEFT_KEYS else 'R'
    with stats_lock:
        total_game_presses += 1 
        if last_key is not None:
            if k_name == last_key: 
                double_press += 1
                if audio_active and audio_loaded and sound: sound.play()
            elif curr_hand == last_hand: 
                random_roll += 1
                if audio_active and audio_loaded and sound: sound.play()
        last_key, last_hand = k_name, curr_hand

def on_release(key):
    k_name = get_key_display(key).lower()
    if k_name in pressed_keys: pressed_keys.remove(k_name)

# --- UI ---
def draw_button(rect, text, base_color, hover_color, t_font=small):
    mouse_pos = pygame.mouse.get_pos()
    color = hover_color if rect.collidepoint(mouse_pos) else base_color
    pygame.draw.rect(screen, color, rect, border_radius=5)
    txt_surf = t_font.render(text, True, (255, 255, 255))
    screen.blit(txt_surf, (rect.centerx - txt_surf.get_width()//2, rect.centery - txt_surf.get_height()//2 - 2))

def draw_overlay_base(text, subtext="", subtext_color=(255, 200, 0)):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 215))
    screen.blit(overlay, (0,0))
    rect = pygame.Rect((WIDTH-280)//2, (HEIGHT-130)//2, 280, 130)
    pygame.draw.rect(screen, (5, 5, 5), rect, border_radius=15)
    pygame.draw.rect(screen, (60, 60, 60), rect, 2, border_radius=15)
    t1 = small.render(text, True, (255, 255, 255))
    screen.blit(t1, (rect.centerx - t1.get_width()//2, rect.y + 20))
    if subtext:
        t2 = small.render(subtext, True, subtext_color)
        screen.blit(t2, (rect.centerx - t2.get_width()//2, rect.y + 55))
    return rect

# --- ЗАПУСК ---
load_config()
Thread(target=lambda: keyboard.Listener(on_press=on_press, on_release=on_release).start(), daemon=True).start()

btn_toggle = pygame.Rect(20, 310, 80, 40)
slider_rect = pygame.Rect(110, 310, 200, 40)
btn_clear = pygame.Rect(20, 360, 80, 40)
btn_select = pygame.Rect(110, 360, 150, 40)
btn_del_audio = pygame.Rect(270, 360, 40, 40)
btn_keybinds = pygame.Rect(20, 410, 115, 40)
btn_clear_key = pygame.Rect(145, 410, 115, 40)
btn_del_bind = pygame.Rect(270, 410, 40, 40)
btn_reset_all = pygame.Rect(WIDTH//2 - 120, 470, 240, 20)

btn_yes = pygame.Rect(WIDTH//2 - 90, (HEIGHT//2) + 10, 80, 35)
btn_no = pygame.Rect(WIDTH//2 + 10, (HEIGHT//2) + 10, 80, 35)

GRAY, GRAY_H = (60, 60, 60), (90, 90, 90)
RED_H, GREEN_H = (200, 140, 140), (140, 200, 140)
BLUE, BLUE_H = (40, 80, 120), (60, 110, 170)
PURPLE, PURPLE_H = (70, 50, 100), (100, 80, 140)

dragging, clock = False, pygame.time.Clock()

while running:
    mouse = pygame.mouse.get_pos()
    for event in pygame.event.get():
        if event.type == pygame.QUIT: save_config(); running = False
        if event.type == pygame.MOUSEBUTTONDOWN:
            if confirm_mode:
                if btn_yes.collidepoint(event.pos): reset_everything(); confirm_mode = False
                elif btn_no.collidepoint(event.pos): confirm_mode = False
            elif not (bind_mode or game_bind_mode):
                if btn_toggle.collidepoint(event.pos) and audio_loaded: audio_active = not audio_active
                elif btn_clear.collidepoint(event.pos):
                    with stats_lock: random_roll, double_press, total_game_presses = 0, 0, 0
                elif btn_select.collidepoint(event.pos):
                    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
                    p = filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.wav")]); root.destroy()
                    if p: validate_and_load(p)
                elif btn_del_audio.collidepoint(event.pos):
                    audio_loaded, sound, audio_name, audio_path = False, None, "None", ""
                    if validate_and_load(sound_path, silent=True): pass
                elif btn_keybinds.collidepoint(event.pos): game_bind_mode, game_bind_step = True, 0
                elif btn_clear_key.collidepoint(event.pos): bind_mode = True
                elif btn_del_bind.collidepoint(event.pos): reset_key_obj, reset_key_id = None, None
                elif btn_reset_all.collidepoint(event.pos): confirm_mode = True
                if slider_rect.collidepoint(event.pos): dragging = True
        if event.type == pygame.MOUSEBUTTONUP: dragging = False

    if dragging:
        audio_volume = int((max(0, min(mouse[0] - slider_rect.x, slider_rect.width)) / slider_rect.width) * 100)
        if sound: sound.set_volume(audio_volume / 100.0)

    screen.fill((20, 20, 20))
    with stats_lock:
        # Позиция x=33
        screen.blit(font.render(f"Rolls: {random_roll}", True, (255, 255, 255)), (33, 20))
        screen.blit(font.render(f"Doubles: {double_press}", True, (255, 255, 255)), (33, 60))
        screen.blit(font.render(f"Total: {random_roll + double_press}", True, TOTAL_GRAY), (33, 100))
        
        acc = 100.0
        if total_game_presses > 0:
            # Штраф: Роллы + Даблы*2
            penalty = random_roll + (double_press * 2)
            err_percent = (penalty / total_game_presses) * 100
            acc = max(0.0, 100.0 - err_percent)
            
        # Формат xx.xx% fullalt
        screen.blit(font.render(f"{acc:.2f}% fullalt", True, ACC_PURPLE), (33, 140))

    ty = 210
    screen.blit(small.render(f"Clear Key: {get_key_display(reset_key_obj)}", True, TEXT_GRAY), (30, ty))
    label = small.render("Keybinds: ", True, (180, 180, 180))
    screen.blit(label, (30, ty + 22))
    curr_x = 30 + label.get_width()
    for i, b in enumerate([LEFT_KEYS[0], LEFT_KEYS[1], RIGHT_KEYS[0], RIGHT_KEYS[1]]):
        char_surf = small.render(b.upper(), True, [KAT_COLOR, DON_COLOR, DON_COLOR, KAT_COLOR][i])
        screen.blit(char_surf, (curr_x, ty + 22)); curr_x += char_surf.get_width()

    acol = P_GREEN if audio_active else P_RED
    screen.blit(small.render(f"Audio: {'ON' if audio_active else 'OFF'} ({audio_name})", True, acol), (30, ty + 44))

    draw_button(btn_toggle, "Toggle", (P_GREEN if audio_active else P_RED), (P_GREEN if audio_active else P_RED))
    pygame.draw.rect(screen, (40, 40, 40), slider_rect, border_radius=5)
    fw = int((audio_volume / 100) * slider_rect.width)
    if fw > 0: pygame.draw.rect(screen, (80, 80, 150), (slider_rect.x, slider_rect.y, fw, slider_rect.height), border_radius=5)
    vt = small.render(f"Volume: {audio_volume}%", True, (255, 255, 255))
    screen.blit(vt, (slider_rect.centerx - vt.get_width()//2, slider_rect.centery - vt.get_height()//2 - 2))

    draw_button(btn_clear, "Clear", GRAY, GRAY_H)
    draw_button(btn_select, "Select Audio", BLUE, BLUE_H)
    draw_button(btn_del_audio, "X", (120, 40, 40), (170, 60, 60))
    draw_button(btn_keybinds, "Keybinds", PURPLE, PURPLE_H)
    draw_button(btn_clear_key, "Clear Key", PURPLE, PURPLE_H)
    draw_button(btn_del_bind, "X", (120, 40, 40), (170, 60, 60))
    draw_button(btn_reset_all, "Reset All Settings", RESET_SETTINGS_COLOR, (180, 180, 180), tiny)

    if error_message:
        if time.time() - error_timer < 3: draw_overlay_base("ERROR", error_message, (255, 50, 50))
        else: error_message = ""
    if bind_mode: draw_overlay_base("SET CLEAR KEY", "Press any key...")
    if game_bind_mode:
        steps = [("Bind Left KAT", KAT_COLOR), ("Bind Left DON", DON_COLOR), ("Bind Right DON", DON_COLOR), ("Bind Right KAT", KAT_COLOR)]
        l, c = steps[game_bind_step]; draw_overlay_base(l.upper(), "Waiting for key...", c)
    
    if confirm_mode:
        draw_overlay_base("Reset All Settings?", "")
        draw_button(btn_yes, "YES", P_GREEN, GREEN_H)
        draw_button(btn_no, "NO", P_RED, RED_H)

    pygame.display.flip(); clock.tick(60)
pygame.quit()