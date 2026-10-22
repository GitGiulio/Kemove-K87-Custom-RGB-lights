"""Windowless K87 lighting with a Windows notification-area menu."""
import ctypes
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import subprocess
import queue
import tkinter as tk
from tkinter import messagebox
import threading
import winreg

from PIL import Image, ImageDraw
import pystray
from kemove_rgb import main as run_lighting, load_layout
from settings import Settings
from settings_ui import SettingsWindow
from notification_blinker import NotificationService

ROOT = Path(__file__).resolve().parent
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME = 'KEMOVE Screen RGB'


def startup_command():
    return subprocess.list2cmdline([str(ROOT / '.venv/Scripts/pythonw.exe'), str(ROOT / 'kemove_tray.py')])


def startup_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, RUN_NAME)[0] == startup_command()
    except FileNotFoundError:
        return False


def set_startup(enabled):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_NAME)
            except FileNotFoundError:
                pass


def create_icon():
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((2, 10, 62, 54), radius=7, fill='#202830')
    for row in range(3):
        for col, color in enumerate(['#ff6464', '#ffd45e', '#6ee79e', '#6bb5ff']):
            x, y = 8 + col * 13, 17 + row * 10
            draw.rectangle((x, y, x + 8, y + 5), fill=color)
    return image


def main():
    handler = RotatingFileHandler(ROOT / 'kemove-rgb.log', maxBytes=100_000, backupCount=1, encoding='utf-8')
    logging.basicConfig(level=logging.INFO, handlers=[handler], format='%(asctime)s %(levelname)s %(message)s')
    settings = Settings()
    ctypes.windll.user32.SetProcessDPIAware()
    root = tk.Tk()
    root.withdraw()
    stop = threading.Event()
    notifications = NotificationService(settings, stop)
    events = queue.Queue()
    dialog = None

    def quit_app(icon, item):
        stop.set()
        settings.wake_waiters()
        events.put(('quit', None))

    def open_settings(icon, item):
        events.put(('settings', None))

    def toggle_startup(icon, item):
        events.put(('startup', None))

    icon = pystray.Icon('KEMOVE RGB', create_icon(), 'KEMOVE RGB: starting', menu=pystray.Menu(
        pystray.MenuItem('Settings...', open_settings, default=True),
        pystray.MenuItem('Start at sign-in', toggle_startup, checked=lambda item: startup_enabled()),
        pystray.MenuItem('Quit', quit_app)))

    def status(message):
        logging.info(message)
        icon.title = ('KEMOVE RGB: ' + message)[:127]

    def worker():
        try:
            run_lighting(stop_event=stop, status=status, settings=settings, notifications=notifications)
        except Exception as exc:
            logging.exception('Lighting stopped')
            events.put(('error', str(exc)))
        finally:
            stop.set()
            settings.wake_waiters()
            events.put(('quit', None))

    thread = threading.Thread(target=worker, name='K87 lighting')

    def setup(icon):
        icon.visible = True
        thread.start()

    def pump():
        nonlocal dialog
        while not events.empty():
            action, detail = events.get_nowait()
            if action == 'settings' and not stop.is_set():
                if dialog is None or not dialog.winfo_exists():
                    dialog = SettingsWindow(root, settings, load_layout(), startup_enabled, set_startup,
                                            notifications=notifications)
                dialog.deiconify(); dialog.lift(); dialog.focus_force()
            elif action == 'startup':
                try:
                    set_startup(not startup_enabled())
                    if dialog is not None and dialog.winfo_exists():
                        dialog.startup.set(startup_enabled())
                except OSError as exc:
                    messagebox.showerror('Startup setting', str(exc), parent=root)
            elif action == 'error':
                messagebox.showerror('KEMOVE RGB error', detail, parent=root)
            elif action == 'quit':
                if dialog is not None and dialog.winfo_exists():
                    dialog.cancel()
                root.quit()
                return
        root.after(50, pump)

    tray_thread = threading.Thread(target=lambda: icon.run(setup=setup), name='K87 tray')
    tray_thread.start()
    root.after(50, pump)
    try:
        root.mainloop()
    finally:
        stop.set()
        settings.wake_waiters()
        icon.stop()
        if thread.ident is not None:
            thread.join()
        tray_thread.join()
        root.destroy()
        logging.shutdown()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        logging.exception('Could not start KEMOVE RGB')
        ctypes.windll.user32.MessageBoxW(None, str(exc), 'KEMOVE RGB error', 0x10)
