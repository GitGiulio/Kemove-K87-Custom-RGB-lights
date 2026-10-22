"""Small Tk settings editor and HSV color wheel for the tray application."""
import colorsys
import math
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from settings import FPS_STEPS
from notification_blinker import APP_CATALOG


def hex_color(rgb):
    return '#%02x%02x%02x' % tuple(rgb)


class ColorWheel(tk.Toplevel):
    def __init__(self, parent, color, accept):
        super().__init__(parent)
        self.title('Choose color')
        self.resizable(False, False)
        self.transient(parent)
        self.accept = accept
        self.hue, self.saturation, value = colorsys.rgb_to_hsv(*(v / 255 for v in color))
        self.canvas = tk.Canvas(self, width=220, height=220, highlightthickness=0)
        self.canvas.pack(padx=15, pady=15)
        wheel = Image.new('RGB', (220, 220), '#f0f0f0')
        for y in range(220):
            for x in range(220):
                dx, dy = x - 110, y - 110
                radius = math.hypot(dx, dy) / 105
                if radius <= 1:
                    hue = math.atan2(dy, dx) / (2 * math.pi) % 1
                    wheel.putpixel((x, y), tuple(round(v * 255) for v in colorsys.hsv_to_rgb(hue, radius, 1)))
        self.photo = ImageTk.PhotoImage(wheel)
        self.canvas.create_image(0, 0, image=self.photo, anchor='nw')
        self.marker = self.canvas.create_oval(0, 0, 8, 8, outline='black', width=2)
        self.canvas.bind('<Button-1>', self.pick)
        self.canvas.bind('<B1-Motion>', self.pick)
        self.value = tk.Scale(self, from_=0, to=100, orient='horizontal', label='Color value', command=lambda _: self.update_color())
        self.value.set(round(value * 100)); self.value.pack(fill='x', padx=15)
        self.swatch = tk.Label(self, height=2)
        self.swatch.pack(fill='x', padx=15, pady=8)
        buttons = ttk.Frame(self); buttons.pack(pady=(0, 15))
        ttk.Button(buttons, text='Use color', command=self.choose).pack(side='left', padx=5)
        ttk.Button(buttons, text='Cancel', command=self.destroy).pack(side='left', padx=5)
        self.update_color()
        self.grab_set()

    def pick(self, event):
        dx, dy = event.x - 110, event.y - 110
        self.hue = math.atan2(dy, dx) / (2 * math.pi) % 1
        self.saturation = min(1, math.hypot(dx, dy) / 105)
        self.update_color()

    def update_color(self):
        if not hasattr(self, 'swatch'): return
        self.rgb = tuple(round(v * 255) for v in colorsys.hsv_to_rgb(self.hue, self.saturation, self.value.get() / 100))
        self.swatch.configure(bg=hex_color(self.rgb), text=hex_color(self.rgb).upper(), fg='black' if sum(self.rgb) > 380 else 'white')
        angle = self.hue * 2 * math.pi
        x, y = 110 + 105 * self.saturation * math.cos(angle), 110 + 105 * self.saturation * math.sin(angle)
        self.canvas.coords(self.marker, x-4, y-4, x+4, y+4)

    def choose(self):
        self.accept(list(self.rgb))
        self.destroy()


class SettingsWindow(tk.Toplevel):
    def __init__(self, root, store, layout, get_startup, set_startup, notifications=None):
        super().__init__(root)
        self.title('KEMOVE RGB settings')
        self.resizable(False, False)
        self.store, self.layout = store, layout
        self.get_startup, self.set_startup = get_startup, set_startup
        self.notifications = notifications
        self.notification_after = None
        self.draft = store.get()
        self.selected = layout[0]['index']
        self.loading = True
        self.protocol('WM_DELETE_WINDOW', self.cancel)
        shell = ttk.Frame(self, padding=16); shell.pack(fill='both', expand=True)
        self.tabs = ttk.Notebook(shell); self.tabs.pack(fill='both', expand=True)
        body = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(body, text='Lighting')
        ttk.Label(body, text='Screen lighting', font=('Segoe UI', 15, 'bold')).pack(anchor='w')
        sliders = ttk.Frame(body); sliders.pack(fill='x', pady=8)
        self.brightness = self.slider(sliders, 'Brightness (%)', 0, 100, round(self.draft['brightness'] * 100), 0)
        fps_position = min(range(len(FPS_STEPS)), key=lambda i: abs(FPS_STEPS[i] - self.draft['fps']))
        self.fps = self.slider(sliders, 'Screen refresh rate', 0, len(FPS_STEPS)-1, fps_position, 1, showvalue=False)
        self.smoothing = self.slider(sliders, 'Smoothing (ms)', 0, 2000, round(self.draft['smoothing'] * 1000), 2)
        self.rate_label = ttk.Label(body); self.rate_label.pack(anchor='w')
        modes = ttk.Frame(body); modes.pack(fill='x', pady=8)
        self.mode = tk.StringVar(value=self.draft['mode'])
        ttk.Label(modes, text='Screen mode:').pack(side='left', padx=(0,8))
        for label, value in [('Spatial', 'spatial'), ('Average', 'average')]:
            ttk.Radiobutton(modes, text=label, variable=self.mode, value=value, command=self.changed).pack(side='left', padx=5)
        self.startup = tk.BooleanVar(value=get_startup())
        ttk.Checkbutton(modes, text='Start at sign-in (applied on Save)', variable=self.startup).pack(side='right')
        press = ttk.LabelFrame(body, text='Press-to-light overlay', padding=8); press.pack(fill='x', pady=(0,10))
        self.press_enabled = tk.BooleanVar(value=self.draft['press_enabled'])
        ttk.Checkbutton(press, text='Light pressed keys at full brightness', variable=self.press_enabled, command=self.changed).pack(side='left')
        self.press_button = tk.Button(press, text='Choose press color', command=self.pick_press)
        self.press_button.pack(side='right')
        ttk.Label(body, text='Key exceptions', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(body, text='Click a key below. Blue-gray = follow screen, color = fixed, dark = OFF.').pack(anchor='w', pady=(3,6))
        self.canvas = tk.Canvas(body, width=848, height=286, background='#e5e9ee', highlightthickness=0)
        self.canvas.pack()
        self.rectangles = {}
        self.labels = {}
        for key in layout:
            x,y,w,h = key['rect']; x+=6; y+=6
            index = key['index']
            tag = f'key{index}'
            self.rectangles[index] = self.canvas.create_rectangle(x,y,x+w,y+h, tags=tag)
            self.labels[index] = self.canvas.create_text(x+w/2,y+h/2,text=key['name'],font=('Segoe UI',9),tags=tag)
            self.canvas.tag_bind(tag, '<Button-1>', lambda event, i=index: self.select_key(i))
        editor = ttk.Frame(body); editor.pack(fill='x', pady=9)
        self.key_title = ttk.Label(editor, width=15); self.key_title.pack(side='left')
        self.key_mode = tk.StringVar()
        for label, value in [('Follow screen','screen'), ('Fixed color','fixed'), ('OFF','off')]:
            ttk.Radiobutton(editor, text=label, variable=self.key_mode, value=value, command=self.key_changed).pack(side='left', padx=6)
        self.key_button = tk.Button(editor, text='Choose key color', command=self.pick_key)
        self.key_button.pack(side='right')
        ttk.Label(body, text='Press color overrides exceptions while active. Fn presses are unavailable to Windows.\nChanges preview live. Save remembers them; Cancel or closing restores the last saved settings.').pack(anchor='w', pady=(0,10))
        self.build_notifications_tab()
        buttons = ttk.Frame(shell); buttons.pack(fill='x', pady=(10,0))
        ttk.Button(buttons, text='Save', command=self.save).pack(side='right', padx=(8,0))
        ttk.Button(buttons, text='Cancel', command=self.cancel).pack(side='right')
        self.loading = False
        self.select_key(self.selected)
        self.changed()
        self.refresh_notification_status()

    def build_notifications_tab(self):
        body = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(body, text='Notifications')
        self.notifications_enabled = tk.BooleanVar(value=self.draft['notifications_enabled'])
        ttk.Checkbutton(body, text='Enable notification blinkers', variable=self.notifications_enabled,
                        command=self.notification_changed).pack(anchor='w')
        ttk.Label(body, text='Blinks until the application is brought to the foreground.\n'
                  'Dismissing its notification does not stop blinking.\n'
                  'Checks for notifications every 10 seconds and foreground every 1 second.').pack(anchor='w', pady=10)
        access = ttk.Frame(body); access.pack(fill='x', pady=(0,12))
        self.notification_status = ttk.Label(access, text='Disabled', wraplength=570)
        self.notification_status.pack(side='left', fill='x', expand=True)
        ttk.Button(access, text='Allow access / Retry', command=self.request_notification_access,
                   state='normal' if self.notifications else 'disabled').pack(side='right')
        table = ttk.Frame(body); table.pack(fill='x')
        for column, text in enumerate(['Application', 'Enabled', 'Key', 'Color']):
            ttk.Label(table, text=text).grid(row=0, column=column, sticky='w', padx=8, pady=6)
        self.notification_rows = {}
        names = [key['name'] for key in self.layout]
        for row, (app, info) in enumerate(APP_CATALOG.items(), 1):
            rule = self.draft['notification_apps'][app]
            ttk.Label(table, text=info['name']).grid(row=row, column=0, sticky='w', padx=8)
            enabled = tk.BooleanVar(value=rule['enabled'])
            toggle = ttk.Checkbutton(table, variable=enabled, command=self.notification_changed)
            toggle.grid(row=row, column=1, sticky='w', padx=8)
            key = ttk.Combobox(table, values=names, state='readonly', width=16)
            key.current(next(i for i, item in enumerate(self.layout) if item['index'] == rule['key_index']))
            key.grid(row=row, column=2, sticky='w', padx=8)
            key.bind('<<ComboboxSelected>>', lambda _: self.notification_changed())
            color = tk.Button(table, text=hex_color(rule['color']).upper(), bg=hex_color(rule['color']),
                              command=lambda app=app: self.pick_notification_color(app), width=12)
            color.grid(row=row, column=3, sticky='w', padx=8, pady=6)
            self.notification_rows[app] = dict(enabled=enabled, toggle=toggle, key=key, color=color)
        ttk.Label(body, text='Notification colors use their selected intensity and override other key effects.\n'
                  'Windows access covers notifications from all apps; only supported app metadata is used.\n'
                  'Save remembers settings. Cancel restores saved settings, but cannot restore cleared alerts.',
                  wraplength=790).pack(anchor='w', pady=16)
        self.update_notification_controls()

    def update_notification_controls(self):
        master = self.notifications_enabled.get()
        for app, widgets in self.notification_rows.items():
            active = master and widgets['enabled'].get()
            widgets['toggle'].configure(state='normal' if master else 'disabled')
            widgets['key'].configure(state='readonly' if active else 'disabled')
            rule = self.draft['notification_apps'][app]
            color = hex_color(rule['color'])
            widgets['color'].configure(state='normal' if active else 'disabled', bg=color,
                                       text=color.upper(), fg='black' if sum(rule['color']) > 380 else 'white')

    def notification_changed(self):
        self.draft['notifications_enabled'] = self.notifications_enabled.get()
        for app, widgets in self.notification_rows.items():
            self.draft['notification_apps'][app].update(enabled=widgets['enabled'].get(),
                key_index=self.layout[widgets['key'].current()]['index'])
        self.update_notification_controls()
        self.changed()

    def pick_notification_color(self, app):
        def accept(color):
            self.draft['notification_apps'][app]['color'] = list(color)
            self.notification_changed()
        ColorWheel(self, self.draft['notification_apps'][app]['color'], accept)

    def request_notification_access(self):
        if self.notifications:
            self.notifications.request_access()
            self.notification_status.configure(text=self.notifications.status())

    def refresh_notification_status(self):
        self.notification_status.configure(text=self.notifications.status() if self.notifications else
                                            'Notification service unavailable')
        self.notification_after = self.after(1000, self.refresh_notification_status)

    def destroy(self):
        if self.notification_after is not None:
            self.after_cancel(self.notification_after)
            self.notification_after = None
        super().destroy()

    def slider(self, parent, label, low, high, value, column, showvalue=True):
        widget = tk.Scale(parent, from_=low, to=high, orient='horizontal', length=260, label=label,
                          showvalue=showvalue, command=lambda _: self.changed())
        widget.set(value); widget.grid(row=0, column=column, padx=8)
        return widget

    def changed(self):
        if self.loading: return
        self.draft.update(brightness=self.brightness.get()/100, fps=FPS_STEPS[self.fps.get()],
                          smoothing=self.smoothing.get()/1000, mode=self.mode.get(), press_enabled=self.press_enabled.get())
        fps = self.draft['fps']
        self.rate_label.configure(text=f'{fps:g} FPS  |  one screen sample every {1/fps:g} seconds. Key effects remain responsive.')
        self.press_button.configure(bg=hex_color(self.draft['press_color']))
        self.store.preview(self.draft)
        self.redraw()

    def redraw(self):
        for key in self.layout:
            index = key['index']; rule = self.draft['exceptions'].get(str(index), {'mode':'screen'})
            color = '#647c98' if rule['mode']=='screen' else '#202830' if rule['mode']=='off' else hex_color(rule['color'])
            self.canvas.itemconfigure(self.rectangles[index], fill=color, outline='#ffac24' if index==self.selected else '#e5e9ee', width=3 if index==self.selected else 1)
            rgb = self.winfo_rgb(color)
            self.canvas.itemconfigure(self.labels[index], fill='black' if sum(rgb)>100000 else 'white')

    def select_key(self, index):
        self.selected = index
        key = next(k for k in self.layout if k['index']==index)
        self.key_title.configure(text=f"Selected: {key['name']}")
        rule = self.draft['exceptions'].get(str(index), {'mode':'screen','color':[255,255,255]})
        self.key_mode.set(rule['mode']); self.key_color = list(rule['color'])
        self.key_button.configure(bg=hex_color(self.key_color), state='normal' if rule['mode']=='fixed' else 'disabled')
        self.redraw()

    def key_changed(self):
        self.draft['exceptions'][str(self.selected)] = dict(mode=self.key_mode.get(), color=list(self.key_color))
        self.key_button.configure(bg=hex_color(self.key_color), state='normal' if self.key_mode.get()=='fixed' else 'disabled')
        self.changed()

    def pick_key(self):
        def accept(color):
            self.key_color = color
            self.key_changed()
        ColorWheel(self, self.key_color, accept)

    def pick_press(self):
        def accept(color):
            self.draft['press_color'] = color
            self.changed()
        ColorWheel(self, self.draft['press_color'], accept)

    def save(self):
        original_startup = self.get_startup()
        changed_startup = False
        try:
            if self.startup.get() != original_startup:
                self.set_startup(self.startup.get())
                changed_startup = True
            self.store.save()
        except OSError as exc:
            detail = str(exc)
            if changed_startup:
                try:
                    self.set_startup(original_startup)
                except OSError as rollback_error:
                    detail += f'\nCould not restore startup setting: {rollback_error}'
            messagebox.showerror('Could not save settings', detail, parent=self)
            return
        self.destroy()

    def cancel(self):
        self.store.cancel()
        self.destroy()
