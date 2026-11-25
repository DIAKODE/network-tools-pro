from tkinter import filedialog
import customtkinter as ctk

from core.config import (
    APP_NAME, COLOR_GREEN, COLOR_ORANGE, COLOR_RED,
    CORE_TARGETS, SFX_PROFILES, THEMES,
)
from core.win_audio import is_autostart_enabled, set_autostart


def refresh_settings_targets_ui(app):
    box = app.settings_targets_box
    if box is None or not box.winfo_exists():
        return
    for w in box.winfo_children():
        w.destroy()

    T = app.T
    extras = [t for t in app.default_targets if t not in CORE_TARGETS]
    if not extras:
        ctk.CTkLabel(
            box, text="Target list is clean (5 core defaults only).",
            font=("Consolas", 11), text_color=COLOR_GREEN, bg_color=T["card"],
        ).pack(anchor="w", padx=8, pady=6)
        return

    for t in extras:
        row = ctk.CTkFrame(box, fg_color=T["inner"], bg_color=T["card"], corner_radius=8, border_width=1, border_color=T["border"])
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=t, font=("Consolas", 11, "bold"), text_color=T["text"], bg_color=T["inner"]).pack(side="left", padx=10, pady=5)
        ctk.CTkButton(
            row, text="X", width=26, height=22, corner_radius=6, bg_color=T["inner"],
            font=("Segoe UI", 10, "bold"), fg_color="#7F1D1D", hover_color=COLOR_RED,
            command=lambda val=t: app.remove_custom_target(val),
        ).pack(side="right", padx=6, pady=4)

    ctk.CTkButton(
        box, text=f"Clean All Extra Targets ({len(extras)})", height=28, corner_radius=8, bg_color=T["card"],
        font=("Segoe UI", 11, "bold"), fg_color="#7F1D1D", hover_color=COLOR_RED, text_color="#FFFFFF",
        command=app.clean_extra_targets,
    ).pack(fill="x", pady=(6, 2))


def open_settings_modal(app):
    if app.settings_win and app.settings_win.winfo_exists():
        app.settings_win.focus_force()
        return

    T = app.T
    win = ctk.CTkToplevel(app)
    app.settings_win = win
    win.title(f"Settings — {APP_NAME}")
    win.geometry("460x680")
    win.resizable(False, False)
    win.configure(fg_color=T["bg"])
    win.attributes("-topmost", True)
    win.after(250, lambda: app.apply_window_icon(win))

    x = app.winfo_x() + 270
    y = max(25, app.winfo_y() + 65)
    win.geometry(f"460x680+{x}+{y}")

    ctk.CTkLabel(win, text="SETTINGS & PREFERENCES", font=("Segoe UI", 15, "bold"), text_color=T["accent1"], bg_color=T["bg"]).pack(pady=(14, 8))

    card = ctk.CTkScrollableFrame(
        win, fg_color=T["card"], bg_color=T["bg"], corner_radius=12,
        border_width=1, border_color=T["border"],
        scrollbar_button_color=T["border"], scrollbar_button_hover_color=T["muted"],
    )
    card.pack(fill="both", expand=True, padx=16, pady=(0, 10))

    # --- بخش ۱: تم ---
    ctk.CTkLabel(card, text="Color Theme", font=("Segoe UI", 12, "bold"), text_color=T["text"], bg_color=T["card"]).pack(anchor="w", padx=12, pady=(8, 3))
    theme_var = ctk.StringVar(value=app.theme_name)

    def on_theme_change(val):
        app.apply_theme(val)
        win.destroy()
        open_settings_modal(app)

    ctk.CTkOptionMenu(
        card, values=list(THEMES.keys()), variable=theme_var,
        fg_color=T["inner"], bg_color=T["card"], button_color=T["accent1"], text_color=T["text"],
        command=on_theme_change,
    ).pack(fill="x", padx=12, pady=(0, 10))

    # --- بخش ۲: پاک‌سازی تارگت‌های سفارشی ---
    ctk.CTkLabel(card, text="Saved Custom Targets (Cleanup)", font=("Segoe UI", 12, "bold"), text_color=T["text"], bg_color=T["card"]).pack(anchor="w", padx=12, pady=(4, 3))
    app.settings_targets_box = ctk.CTkFrame(card, fg_color=T["card"], corner_radius=0)
    app.settings_targets_box.pack(fill="x", padx=12, pady=(0, 10))
    refresh_settings_targets_ui(app)

    # --- بخش ۳: سرعت پینگ ---
    ctk.CTkLabel(card, text="Ping Interval (Speed)", font=("Segoe UI", 12, "bold"), text_color=T["text"], bg_color=T["card"]).pack(anchor="w", padx=12, pady=(4, 3))
    interval_map = {"0.5s (Fast / Gaming)": 0.5, "1.0s (Balanced)": 1.0, "2.0s (Eco)": 2.0}
    rev_map = {v: k for k, v in interval_map.items()}
    int_var = ctk.StringVar(value=rev_map.get(app.ping_interval, "1.0s (Balanced)"))

    def set_interval(val):
        app.ping_interval = interval_map[val]
        app.save_config()

    ctk.CTkOptionMenu(
        card, values=list(interval_map.keys()), variable=int_var,
        fg_color=T["inner"], bg_color=T["card"], button_color=T["accent2"], text_color=T["text"],
        command=set_interval,
    ).pack(fill="x", padx=12, pady=(0, 10))

    # --- بخش ۴: مینی‌مود و شفافیت ---
    ctk.CTkLabel(card, text="Mini Mode Layout", font=("Segoe UI", 12, "bold"), text_color=T["text"], bg_color=T["card"]).pack(anchor="w", padx=12, pady=(4, 3))
    style_map = {"Compact Card": "card", "Slim Gaming Bar": "slim"}
    style_var = ctk.StringVar(value="Slim Gaming Bar" if app.mini_style == "slim" else "Compact Card")

    def set_mini_style(val):
        app.mini_style = style_map[val]
        app.save_config()
        if app.is_mini:
            app.tray_mini.layout_mini_mode()

    ctk.CTkOptionMenu(
        card, values=list(style_map.keys()), variable=style_var,
        fg_color=T["inner"], bg_color=T["card"], button_color=T["accent1"], text_color=T["text"],
        command=set_mini_style,
    ).pack(fill="x", padx=12, pady=(0, 8))

    op_lbl = ctk.CTkLabel(card, text=f"Mini Mode Opacity: {int(app.mini_opacity * 100)}%", font=("Segoe UI", 12, "bold"), text_color=T["text"], bg_color=T["card"])
    op_lbl.pack(anchor="w", padx=12, pady=(4, 2))

    def set_mini_opacity(v):
        app.mini_opacity = round(float(v), 2)
        op_lbl.configure(text=f"Mini Mode Opacity: {int(app.mini_opacity * 100)}%")
        if app.is_mini:
            app.attributes("-alpha", app.mini_opacity)
        app.save_config()

    op_slider = ctk.CTkSlider(
        card, from_=0.40, to=1.0, number_of_steps=12, bg_color=T["card"],
        progress_color=T["accent1"], button_color=T["accent1"], command=set_mini_opacity,
    )
    op_slider.set(app.mini_opacity)
    op_slider.pack(fill="x", padx=12, pady=(0, 12))

    # --- بخش ۵: هشدار پینگ بالا و نوتیفیکیشن تغییر IP ---
    ctk.CTkLabel(card, text="High Ping Alert Threshold", font=("Segoe UI", 12, "bold"), text_color=T["text"], bg_color=T["card"]).pack(anchor="w", padx=12, pady=(4, 3))
    hp_map = {"Off": 0, "Above 120 ms": 120, "Above 150 ms": 150, "Above 180 ms": 180, "Above 220 ms": 220, "Above 250 ms": 250}
    hp_rev = {v: k for k, v in hp_map.items()}
    hp_var = ctk.StringVar(value=hp_rev.get(app.high_ping_threshold, "Off"))

    def set_hp(val):
        app.high_ping_threshold = hp_map[val]
        app.save_config()

    ctk.CTkOptionMenu(
        card, values=list(hp_map.keys()), variable=hp_var,
        fg_color=T["inner"], bg_color=T["card"], button_color=COLOR_ORANGE, text_color=T["text"], command=set_hp,
    ).pack(fill="x", padx=12, pady=(0, 10))

    vpn_var = ctk.BooleanVar(value=app.vpn_win_notify)

    def set_vpn():
        app.vpn_win_notify = vpn_var.get()
        app.save_config()

    ctk.CTkSwitch(
        card, text="Windows Notification on IP / VPN Change", variable=vpn_var, bg_color=T["card"],
        font=("Segoe UI", 12), text_color=T["text"], progress_color=COLOR_ORANGE, command=set_vpn,
    ).pack(anchor="w", padx=12, pady=6)

    # --- بخش ۶: صدا و ولوم ---
    ctk.CTkLabel(card, text="Alert Sound Profile", font=("Segoe UI", 12, "bold"), text_color=T["text"], bg_color=T["card"]).pack(anchor="w", padx=12, pady=(10, 3))
    sfx_prof_var = ctk.StringVar(value=app.sound.profile)

    def set_sfx_profile(val):
        app.sound.profile = val
        app.sound.rebuild_files()
        app.save_config()
        app.sound.play("restored", force=True)

    ctk.CTkOptionMenu(
        card, values=list(SFX_PROFILES.keys()), variable=sfx_prof_var,
        fg_color=T["inner"], bg_color=T["card"], button_color=COLOR_GREEN, text_color=T["text"], command=set_sfx_profile,
    ).pack(fill="x", padx=12, pady=(0, 8))

    vol_lbl = ctk.CTkLabel(card, text=f"Alert Volume: {int(app.sound.volume * 100)}%", font=("Segoe UI", 12, "bold"), text_color=T["text"], bg_color=T["card"])
    vol_lbl.pack(anchor="w", padx=12, pady=(4, 2))

    def on_vol_slide(v):
        app.sound.volume = round(float(v), 2)
        vol_lbl.configure(text=f"Alert Volume: {int(app.sound.volume * 100)}%")
        if app._vol_rebuild_job is not None:
            try:
                app.after_cancel(app._vol_rebuild_job)
            except Exception:
                pass
        app._vol_rebuild_job = app.after(180, apply_vol_change)

    def apply_vol_change():
        app._vol_rebuild_job = None
        app.sound.rebuild_files()
        app.save_config()
        app.sound.play("restored", force=True)

    vol_slider = ctk.CTkSlider(
        card, from_=0.05, to=1.0, number_of_steps=19, bg_color=T["card"],
        progress_color=COLOR_GREEN, button_color=COLOR_GREEN, command=on_vol_slide,
    )
    vol_slider.set(max(0.05, app.sound.volume))
    vol_slider.pack(fill="x", padx=12, pady=(0, 8))

    sfx_var = ctk.BooleanVar(value=app.sound.enabled)

    def toggle_sfx():
        app.sound.enabled = sfx_var.get()
        app.save_config()

    ctk.CTkSwitch(
        card, text="Enable Audio Alerts", variable=sfx_var, bg_color=T["card"],
        font=("Segoe UI", 12), text_color=T["text"], progress_color=COLOR_GREEN, command=toggle_sfx,
    ).pack(anchor="w", padx=12, pady=6)

    sfx_test_row = ctk.CTkFrame(card, fg_color=T["card"], corner_radius=0)
    sfx_test_row.pack(fill="x", padx=12, pady=(4, 6))
    ctk.CTkButton(sfx_test_row, text="Test Lost", width=98, height=26, corner_radius=7, bg_color=T["card"], font=("Segoe UI", 10, "bold"), fg_color=T["inner"], border_width=1, border_color=COLOR_RED, text_color=COLOR_RED, hover_color=T["border"], command=lambda: app.sound.play("lost", force=True)).pack(side="left", padx=(0, 6))
    ctk.CTkButton(sfx_test_row, text="Test Online", width=98, height=26, corner_radius=7, bg_color=T["card"], font=("Segoe UI", 10, "bold"), fg_color=T["inner"], border_width=1, border_color=COLOR_GREEN, text_color=COLOR_GREEN, hover_color=T["border"], command=lambda: app.sound.play("restored", force=True)).pack(side="left", padx=(0, 6))
    ctk.CTkButton(sfx_test_row, text="Test Warn", width=98, height=26, corner_radius=7, bg_color=T["card"], font=("Segoe UI", 10, "bold"), fg_color=T["inner"], border_width=1, border_color=COLOR_ORANGE, text_color=COLOR_ORANGE, hover_color=T["border"], command=lambda: app.sound.play("warn", force=True)).pack(side="left")

    def pick_wav(which):
        path = filedialog.askopenfilename(title=f"Select {which.title()} WAV File", filetypes=[("WAV Audio", "*.wav")])
        if not path:
            return
        if which == "lost":
            app.sound.custom_lost = path
        else:
            app.sound.custom_online = path
        app.sound.rebuild_files()
        app.save_config()
        app.sound.play("lost" if which == "lost" else "restored", force=True)

    def reset_wavs():
        app.sound.custom_lost = ""
        app.sound.custom_online = ""
        app.sound.rebuild_files()
        app.save_config()
        app.sound.play("restored", force=True)

    custom_wav_row = ctk.CTkFrame(card, fg_color=T["card"], corner_radius=0)
    custom_wav_row.pack(fill="x", padx=12, pady=(2, 10))
    ctk.CTkButton(custom_wav_row, text="Custom Lost .wav", width=120, height=24, corner_radius=6, bg_color=T["card"], font=("Segoe UI", 10), fg_color=T["border"], text_color=T["text"], command=lambda: pick_wav("lost")).pack(side="left", padx=(0, 6))
    ctk.CTkButton(custom_wav_row, text="Custom Online .wav", width=126, height=24, corner_radius=6, bg_color=T["card"], font=("Segoe UI", 10), fg_color=T["border"], text_color=T["text"], command=lambda: pick_wav("online")).pack(side="left", padx=(0, 6))
    ctk.CTkButton(custom_wav_row, text="Reset", width=55, height=24, corner_radius=6, bg_color=T["card"], font=("Segoe UI", 10), fg_color="#7F1D1D", text_color="#FFFFFF", command=reset_wavs).pack(side="left")

    # --- بخش ۷: عمومی ---
    pin_var = ctk.BooleanVar(value=app.is_pinned)

    def set_pin():
        app.is_pinned = pin_var.get()
        if not app.is_mini:
            app.attributes("-topmost", app.is_pinned)
        app.save_config()

    ctk.CTkSwitch(
        card, text="Always on Top (Pin Window)", variable=pin_var, bg_color=T["card"],
        font=("Segoe UI", 12), text_color=T["text"], progress_color=T["accent1"], command=set_pin,
    ).pack(anchor="w", padx=12, pady=6)

    auto_var = ctk.BooleanVar(value=is_autostart_enabled())
    ctk.CTkSwitch(
        card, text="Start Minimized with Windows", variable=auto_var, bg_color=T["card"],
        font=("Segoe UI", 12), text_color=T["text"], progress_color=T["accent2"],
        command=lambda: set_autostart(auto_var.get()),
    ).pack(anchor="w", padx=12, pady=(6, 12))

    ctk.CTkButton(win, text="CLOSE", width=130, height=34, corner_radius=9, bg_color=T["bg"], font=("Segoe UI", 12, "bold"), fg_color=T["border"], text_color=T["text"], command=win.destroy).pack(pady=(0, 14))


def open_rename_device_modal(app, dev, on_saved_cb):
    T = app.T
    win = ctk.CTkToplevel(app)
    win.title("Label Device")
    win.geometry("360x195")
    win.resizable(False, False)
    win.configure(fg_color=T["bg"])
    win.attributes("-topmost", True)
    win.after(200, lambda: app.apply_window_icon(win))

    x = app.winfo_x() + 320
    y = app.winfo_y() + 280
    win.geometry(f"360x195+{x}+{y}")

    ctk.CTkLabel(win, text=f"Label Device  ({dev['ip']})", font=("Segoe UI", 13, "bold"), text_color=T["accent1"], bg_color=T["bg"]).pack(pady=(16, 2))
    ctk.CTkLabel(win, text=f"MAC: {dev['mac']}  •  {dev['vendor']}", font=("Consolas", 10), text_color=T["muted"], bg_color=T["bg"]).pack(pady=(0, 10))

    entry = ctk.CTkEntry(
        win, width=300, height=34, corner_radius=8,
        fg_color=T["inner"], bg_color=T["bg"], border_color=T["accent1"], text_color=T["text"],
        placeholder_text="e.g. My Phone, Living Room TV, PS4",
    )
    entry.pack(pady=(0, 14))
    if dev["custom_name"]:
        entry.insert(0, dev["custom_name"])
    win.after(60, entry.focus_set)

    def save_name(event=None):
        new_nm = entry.get().strip()
        if new_nm:
            app.lan_names[dev["mac"]] = new_nm
        else:
            app.lan_names.pop(dev["mac"], None)
        app.save_config()
        on_saved_cb(dev["mac"], new_nm)
        win.destroy()

    entry.bind("<Return>", save_name)
    entry.bind("<Escape>", lambda e: win.destroy())

    btn_row = ctk.CTkFrame(win, fg_color=T["bg"], corner_radius=0)
    btn_row.pack()
    ctk.CTkButton(btn_row, text="SAVE", width=105, height=32, corner_radius=8, bg_color=T["bg"], font=("Segoe UI", 11, "bold"), fg_color=COLOR_GREEN, text_color="#000000", hover_color="#059669", command=save_name).pack(side="left", padx=6)
    ctk.CTkButton(btn_row, text="CANCEL", width=95, height=32, corner_radius=8, bg_color=T["bg"], font=("Segoe UI", 11, "bold"), fg_color=T["border"], text_color=T["text"], command=win.destroy).pack(side="left", padx=6)