from lib import *
from numpy import array, float32, linalg, cross, dot, reshape
from math import sqrt, pi
from ctypes import windll, byref, Structure, wintypes
from time import time, sleep
from threading import Thread
from requests import get
from subprocess import Popen, PIPE
from os import path
import dearpygui.dearpygui as dpg
from pymem.exception import ProcessError
import sys
import random
import string

pi180 = pi/180

aimbot_enabled = False
esp_enabled = False
esp_ignoreteam = False
esp_ignoredead = False
aimbot_ignoreteam = False
aimbot_ignoredead = False
aimbot_keybind = 2  
aimbot_mode = "Hold"  
aimbot_toggled = False  
waiting_for_keybind = False
injected = False  

VK_CODES = {
    'Left Mouse': 1,
    'Right Mouse': 2,
    'Middle Mouse': 4,
    'X1 Mouse': 5,
    'X2 Mouse': 6,
    'F1': 112, 'F2': 113, 'F3': 114, 'F4': 115, 'F5': 116, 'F6': 117,
    'F7': 118, 'F8': 119, 'F9': 120, 'F10': 121, 'F11': 122, 'F12': 123,
    'A': 65, 'B': 66, 'C': 67, 'D': 68, 'E': 69, 'F': 70, 'G': 71,
    'H': 72, 'I': 73, 'J': 74, 'K': 75, 'L': 76, 'M': 77, 'N': 78,
    'O': 79, 'P': 80, 'Q': 81, 'R': 82, 'S': 83, 'T': 84, 'U': 85,
    'V': 86, 'W': 87, 'X': 88, 'Y': 89, 'Z': 90,
    'Shift': 16, 'Ctrl': 17, 'Alt': 18, 'Space': 32,
    'Enter': 13, 'Tab': 9, 'Caps Lock': 20
}

def get_key_name(vk_code):
    for name, code in VK_CODES.items():
        if code == vk_code:
            return name
    return f"Key {vk_code}"

def generate_random_title():
    """Generate a random title with 24 characters (letters and numbers, mixed case)"""
    characters = string.ascii_letters + string.digits  
    return ''.join(random.choice(characters) for _ in range(24))

def title_changer():
    """Background"""
    while True:
        try:
            new_title = generate_random_title()
            dpg.configure_item("Primary Window", label=new_title)
            dpg.set_viewport_title(new_title)
        except:
            pass  
        sleep(0.0000000000001)

def normalize(vec):
    norm = linalg.norm(vec)
    return vec / norm if norm != 0 else vec

def cframe_look_at(from_pos, to_pos):
    from_pos = array(from_pos, dtype=float32)
    to_pos = array(to_pos, dtype=float32)

    look_vector = normalize(to_pos - from_pos)
    up_vector = array([0, 1, 0], dtype=float32)

    if abs(look_vector[1]) > 0.999:
        up_vector = array([0, 0, -1], dtype=float32)

    right_vector = normalize(cross(up_vector, look_vector))
    recalculated_up = cross(look_vector, right_vector)

    return look_vector, recalculated_up, right_vector

print('Getting offsets...')
offsets = get('https://offsets.ntgetwritewatch.workers.dev/offsets.json').json()

setOffsets(int(offsets['Name'], 16), int(offsets['Children'], 16))

class RECT(Structure):
    _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG), ('right', wintypes.LONG), ('bottom', wintypes.LONG)]

class POINT(Structure):
    _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]

def find_window_by_title(title):
    return windll.user32.FindWindowW(None, title)

def get_client_rect_on_screen(hwnd):
    rect = RECT()
    if windll.user32.GetClientRect(hwnd, byref(rect)) == 0:
        return 0, 0, 0, 0
    top_left = POINT(rect.left, rect.top)
    bottom_right = POINT(rect.right, rect.bottom)
    windll.user32.ClientToScreen(hwnd, byref(top_left))
    windll.user32.ClientToScreen(hwnd, byref(bottom_right))
    return top_left.x, top_left.y, bottom_right.x, bottom_right.y

def world_to_screen_with_matrix(world_pos, matrix, screen_width, screen_height):
    vec = array([*world_pos, 1.0], dtype=float32)
    clip = dot(matrix, vec)
    if clip[3] == 0: return None
    ndc = clip[:3] / clip[3]
    if ndc[2] < 0 or ndc[2] > 1: return None
    x = (ndc[0] + 1) * 0.5 * screen_width
    y = (1 - ndc[1]) * 0.5 * screen_height
    return round(x), round(y)

baseAddr = 0
camAddr = 0
dataModel = 0
wsAddr = 0
camCFrameRotAddr = 0
plrsAddr = 0
lpAddr = 0
matrixAddr = 0
camPosAddr = 0
esp = None
target = 0

def background_process_monitor():
    global baseAddr
    while True:
        if is_process_dead():
            while not yield_for_program("RobloxPlayerBeta.exe"):
                sleep(0.5)
            baseAddr = get_base_addr()
        sleep(0.1)

Thread(target=background_process_monitor, daemon=True).start()

def show_main_features():
    """Show main features after injection delay and hide injector"""

    dpg.hide_item("injector_text")
    dpg.hide_item("injector_text2")
    dpg.hide_item("injector_text3")


    dpg.show_item("main_features_text")
    dpg.show_item("aimbot_checkbox")
    dpg.show_item("esp_checkbox")
    dpg.show_item("spacer1")
    dpg.show_item("separator1")
    dpg.show_item("spacer2")


def init():
    global dataModel, wsAddr, camAddr, camCFrameRotAddr, plrsAddr, lpAddr, matrixAddr, camPosAddr, injected
    try:
        fakeDatamodel = pm.read_longlong(baseAddr + int(offsets['FakeDataModelPointer'], 16))
        print(f'Fake datamodel: {fakeDatamodel:x}')

        dataModel = pm.read_longlong(fakeDatamodel + int(offsets['FakeDataModelToDataModel'], 16))
        print(f'Real datamodel: {dataModel:x}')

        wsAddr = pm.read_longlong(dataModel + int(offsets['Workspace'], 16))
        print(f'Workspace: {wsAddr:x}')

        camAddr = pm.read_longlong(wsAddr + int(offsets['Camera'], 16))
        camCFrameRotAddr = camAddr + int(offsets['CameraRotation'], 16)
        camPosAddr = camAddr + int(offsets['CameraPos'], 16)

        visualEngine = pm.read_longlong(baseAddr + int(offsets['VisualEnginePointer'], 16))
        matrixAddr = visualEngine + int(offsets['viewmatrix'], 16)
        print(f'Matrix: {matrixAddr:x}')

        plrsAddr = FindFirstChildOfClass(dataModel, 'Players')
        print(f'Players: {plrsAddr:x}')

        lpAddr = pm.read_longlong(plrsAddr + int(offsets['LocalPlayer'], 16))
        print(f'Local player: {lpAddr:x}')
    except ProcessError:
        print('You forget to open Roblox!')
        return

    esp.stdin.write(f'addrs{lpAddr},{matrixAddr},{plrsAddr}\n')
    esp.stdin.flush()

    print('External has Injected successfully\n-------------------------------')

    injected = True
    def delayed_show():
        sleep(1)
        show_main_features()

    Thread(target=delayed_show, daemon=True).start()

def toogleEsp():
    esp.stdin.write('toogle1\n')
    esp.stdin.flush()

def toogleIgnoreTeamEsp():
    esp.stdin.write('toogle2\n')
    esp.stdin.flush()

def toogleIgnoreDeadEsp():
    esp.stdin.write('toogle3\n')
    esp.stdin.flush()

if hasattr(sys, '_MEIPASS'):
    esp = Popen([
        path.abspath(path.join(sys._MEIPASS, '..', 'esp.exe')),
        str(int(offsets['ModelInstance'], 16)),
        str(int(offsets['Primitive'], 16)),
        str(int(offsets['Position'], 16)),
        str(int(offsets['Team'], 16)),
        str(int(offsets['TeamColor'], 16)),
        str(int(offsets['Health'], 16)),
        str(int(offsets['Name'], 16)),
        str(int(offsets['Children'], 16))
    ], stdin=PIPE, text=True)
else:
    esp = Popen([
        'python', 'tracers.py',
        str(int(offsets['ModelInstance'], 16)),
        str(int(offsets['Primitive'], 16)),
        str(int(offsets['Position'], 16)),
        str(int(offsets['Team'], 16)),
        str(int(offsets['TeamColor'], 16)),
        str(int(offsets['Health'], 16)),
        str(int(offsets['Name'], 16)),
        str(int(offsets['Children'], 16))
    ], stdin=PIPE, text=True)

def keybind_listener():
    global waiting_for_keybind, aimbot_keybind
    while True:
        if waiting_for_keybind:

            sleep(0.3)

            for vk_code in range(1, 256):
                windll.user32.GetAsyncKeyState(vk_code)

            key_found = False
            while waiting_for_keybind and not key_found:
                for vk_code in range(1, 256):
                    if windll.user32.GetAsyncKeyState(vk_code) & 0x8000:

                        if vk_code == 27:  
                            waiting_for_keybind = False
                            dpg.configure_item("keybind_button", label=f"Keybind: {get_key_name(aimbot_keybind)}")
                            break

                        aimbot_keybind = vk_code
                        waiting_for_keybind = False
                        dpg.configure_item("keybind_button", label=f"Keybind: {get_key_name(vk_code)}")
                        key_found = True
                        break
                sleep(0.01)
        else:
            sleep(0.1)

Thread(target=keybind_listener, daemon=True).start()

def aimbotLoop():
    global target, aimbot_toggled
    key_pressed_last_frame = False

    while True:
        if aimbot_enabled:
            key_pressed_this_frame = windll.user32.GetAsyncKeyState(aimbot_keybind) & 0x8000 != 0

            if aimbot_mode == "Toggle":
                if key_pressed_this_frame and not key_pressed_last_frame:  
                    aimbot_toggled = not aimbot_toggled
                key_pressed_last_frame = key_pressed_this_frame
                should_aim = aimbot_toggled
            else:  
                should_aim = key_pressed_this_frame

            if should_aim:
                if target > 0 and matrixAddr > 0:
                    from_pos = [pm.read_float(camPosAddr), pm.read_float(camPosAddr+4), pm.read_float(camPosAddr+8)]
                    to_pos = [pm.read_float(target), pm.read_float(target+4), pm.read_float(target+8)]

                    look, up, right = cframe_look_at(from_pos, to_pos)

                    pm.write_float(camCFrameRotAddr, float(-right[0]))
                    pm.write_float(camCFrameRotAddr+4, float(up[0]))
                    pm.write_float(camCFrameRotAddr+8, float(-look[0]))

                    pm.write_float(camCFrameRotAddr+12, float(-right[1]))
                    pm.write_float(camCFrameRotAddr+16, float(up[1]))
                    pm.write_float(camCFrameRotAddr+20, float(-look[1]))

                    pm.write_float(camCFrameRotAddr+24, float(-right[2]))
                    pm.write_float(camCFrameRotAddr+28, float(up[2]))
                    pm.write_float(camCFrameRotAddr+32, float(-look[2]))
                else:
                    target = 0
                    hwnd_roblox = find_window_by_title("Roblox")
                    if hwnd_roblox and matrixAddr > 0:
                        left, top, right, bottom = get_client_rect_on_screen(hwnd_roblox)
                        matrix_flat = [pm.read_float(matrixAddr + i * 4) for i in range(16)]
                        view_proj_matrix = reshape(array(matrix_flat, dtype=float32), (4, 4))
                        lpTeam = pm.read_longlong(lpAddr + int(offsets['Team'], 16))
                        width = right - left
                        height = bottom - top
                        widthCenter = width/2
                        heightCenter = height/2
                        minDistance = float('inf')
                        for v in GetChildren(plrsAddr):
                            if v != lpAddr:
                                if not aimbot_ignoreteam or pm.read_longlong(v + int(offsets['Team'], 16)) != lpTeam:
                                    char = pm.read_longlong(v + int(offsets['ModelInstance'], 16))
                                    head = FindFirstChild(char, 'Head')
                                    hum = FindFirstChildOfClass(char, 'Humanoid')
                                    if head and hum:
                                        health = pm.read_float(hum + int(offsets['Health'], 16))
                                        if aimbot_ignoredead and health <= 0:
                                            continue
                                        primitive = pm.read_longlong(head + int(offsets['Primitive'], 16))
                                        targetPos = primitive + int(offsets['Position'], 16)
                                        obj_pos = array([
                                            pm.read_float(targetPos),
                                            pm.read_float(targetPos + 4),
                                            pm.read_float(targetPos + 8)
                                        ], dtype=float32)
                                        screen_coords = world_to_screen_with_matrix(obj_pos, view_proj_matrix, width, height)
                                        if screen_coords is not None:
                                            distance = sqrt((widthCenter - screen_coords[0])**2 + (heightCenter - screen_coords[1])**2)
                                            if distance < minDistance:
                                                minDistance = distance
                                                target = targetPos
            else:
                target = 0
        else:
            aimbot_toggled = False  
            sleep(0.1)

def aimbot_callback(sender, app_data):
    global aimbot_enabled, aimbot_toggled
    if not injected:
        return
    aimbot_enabled = app_data
    if app_data:
        dpg.show_item("aimbot_settings_popup")
    else:
        dpg.hide_item("aimbot_settings_popup")
        aimbot_toggled = False  

def esp_callback(sender, app_data):
    global esp_enabled
    if not injected:
        return
    esp_enabled = app_data
    toogleEsp()
    if app_data:
        dpg.show_item("esp_settings_popup")
    else:
        dpg.hide_item("esp_settings_popup")

def esp_ignoreteam_callback(sender, app_data):
    global esp_ignoreteam
    esp_ignoreteam = app_data
    toogleIgnoreTeamEsp()

def esp_ignoredead_callback(sender, app_data):
    global esp_ignoredead
    esp_ignoredead = app_data
    toogleIgnoreDeadEsp()

def aimbot_ignoreteam_callback(sender, app_data):
    global aimbot_ignoreteam
    aimbot_ignoreteam = app_data

def aimbot_ignoredead_callback(sender, app_data):
    global aimbot_ignoredead
    aimbot_ignoredead = app_data

def aimbot_mode_callback(sender, app_data):
    global aimbot_mode, aimbot_toggled
    aimbot_mode = app_data
    if aimbot_mode == "Hold":
        aimbot_toggled = False  

def keybind_callback():
    global waiting_for_keybind
    if not waiting_for_keybind:
        waiting_for_keybind = True
        dpg.configure_item("keybind_button", label="... (ESC to cancel)")

def inject_callback():
    init()

Thread(target=aimbotLoop, daemon=True).start()

dpg.create_context()

with dpg.window(label="Discord", tag="Primary Window"):

    dpg.add_text("Credit to that guy who made it", color=(183, 0, 0), tag="Title")
    dpg.add_spacer(tag="titlespacer1", show=False)
    dpg.add_separator(tag="titleseparator1", show=False)
    dpg.add_spacer(tag="titlespacer2", show=False) 

    dpg.add_text("More cheats are upcoming", color=(183, 0, 0), tag="main_features_text", show=False)

    dpg.add_checkbox(label="Aimbot", default_value=aimbot_enabled, callback=aimbot_callback, tag="aimbot_checkbox", show=False)
    dpg.add_checkbox(label="ESP", default_value=esp_enabled, callback=esp_callback, tag="esp_checkbox", show=False)
    
    dpg.add_button(label="Inject", callback=inject_callback, tag="inject_button")

    dpg.add_spacer(tag="spacer1", show=False)
    dpg.add_separator(tag="separator1", show=False)
    dpg.add_spacer(tag="spacer2", show=False) 



    
    dpg.add_text("Features:", color=(183, 0, 0), tag="injector_text")
    dpg.add_text("Aimbot , tracers, anti recording capture", color=(183, 0, 0), tag="injector_text2")
    dpg.add_text("Remember to have the latest version of roblox.", color=(183, 0, 0), tag="injector_text3")

 

with dpg.window(label="Aimbot Settings", tag="aimbot_settings_popup", width=300, height=200, show=False, modal=True):
    dpg.add_text("Aimbot Configuration", color=(183, 0, 0))
    dpg.add_spacer()

    dpg.add_button(label=f"Keybind: {get_key_name(aimbot_keybind)}", tag="keybind_button", callback=keybind_callback)
    dpg.add_combo(["Hold", "Toggle"], default_value=aimbot_mode, tag="aimbot_mode_combo", callback=aimbot_mode_callback, width=100)

    dpg.add_spacer()
    dpg.add_separator()
    dpg.add_spacer()

    dpg.add_checkbox(label="Ignore Team", default_value=aimbot_ignoreteam, callback=aimbot_ignoreteam_callback)
    dpg.add_checkbox(label="Ignore Dead", default_value=aimbot_ignoredead, callback=aimbot_ignoredead_callback)

    dpg.add_spacer()
    dpg.add_button(label="Close", callback=lambda: dpg.hide_item("aimbot_settings_popup"))

with dpg.window(label="ESP Settings", tag="esp_settings_popup", width=300, height=150, show=False, modal=True):
    dpg.add_text("ESP Configuration", color=(183, 0, 0))
    dpg.add_spacer()

    dpg.add_checkbox(label="Ignore Team", default_value=esp_ignoreteam, callback=esp_ignoreteam_callback)
    dpg.add_checkbox(label="Ignore Dead", default_value=esp_ignoredead, callback=esp_ignoredead_callback)

    dpg.add_spacer()
    dpg.add_button(label="Close", callback=lambda: dpg.hide_item("esp_settings_popup"))

dpg.create_viewport(title="Discord", width=350, height=350)
dpg.setup_dearpygui()

dpg.set_primary_window("Primary Window", True)

Thread(target=title_changer, daemon=True).start()

dpg.show_viewport()

dpg.start_dearpygui()

dpg.destroy_context()
esp.terminate()
