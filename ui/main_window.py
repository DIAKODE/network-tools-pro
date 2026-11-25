import csv
import os
import re
import sys
import threading
import time
from datetime import datetime

import customtkinter as ctk
import psutil

from core.config import (
    APP_NAME, APP_VERSION, COLOR_GREEN, COLOR_ORANGE, COLOR_RED,
    CORE_TARGETS, CUSTOM_TARGET_OPTION, DEFAULT_DNS_LIST, THEMES,
    get_app_paths, get_health_color, load_config, save_config,
)
from core.net_engine import fetch_geo_for_ip, fetch_public_ip, get_ping
from core.net_etw import PerAppNetworkMonitor
from core.win_audio import SoundManager, is_admin, relaunch_as_admin, show_os_notification
from ui.graphics import build_pulse_icon, hex_to_rgba, render_aa_icon, render_aa_status_led
from ui.settings_win import open_settings_modal, refresh_settings_targets_ui
from ui.tab_dns import DnsTabView
from ui.tab_lan import LanTabView
from ui.tab_network import NetworkTabView
from ui.tab_ping import PingTabView
from ui.tray_mini import TrayMiniController


class NetworkToolsApp(ctk.CTk):
    def __init__(self, instance_mgr=None):
        super().__init__()
        self.instance_mgr = instance_mgr
        self.app_alive = True

        self.app_dir, self.sfx_dir, self.config_path, self.app_icon_path = get_app_paths()
        self.config_data = load_config(self.config_path)
        self._generate_app_ico()

        self.sound = SoundManager(
            sfx_dir=self.sfx_dir,
            profile=self.config_data.get("sfx_profile", "Soft Glass"),
            volume=float(self.config_data.get("sfx_volume", 0.30)),
            enabled=self.config_data.get("sound_enabled", True),
            custom_lost=self.config_data.get("custom_sfx_lost", ""),
            custom_online=self.config_data.get("custom_sfx_online", ""),
        )
        self._vol_rebuild_job = None

        self.theme_name = self.config_data.get("theme", "Cyberpunk Dark")
        if self.theme_name not in THEMES:
            self.theme_name = "Cyberpunk Dark"
        self.T = THEMES[self.theme_name]
        ctk.set_appearance_mode(self.T["mode"])

        self.title(APP_NAME)
        self.geometry("1000x860")
        self.resizable(False, False)
        self.configure(fg_color=self.T["bg"])
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.center_window(1000, 860)

        self.apply_window_icon()
        self.after(250, self.apply_window_icon)

        self.is_running = False
        self.num_targets = 1
        self.is_pinned = self.config_data.get("is_pinned", False)
        self.ping_interval = float(self.config_data.get("ping_interval", 1.0))
        self.mini_opacity = float(self.config_data.get("mini_opacity", 0.92))
        self.mini_style = self.config_data.get("mini_style", "card")
        self.mini_pos = self.config_data.get("mini_pos", None)
        self.vpn_win_notify = self.config_data.get("vpn_win_notify", False)
        self.high_ping_threshold = int(self.config_data.get("high_ping_threshold", 0))
        self.last_high_ping_alert = 0.0

        self.is_mini = False
        self.current_tab = "ping"
        self.current_my_ip = "Loading..."
        self.current_loc = ""
        self.geo_cache = {}
        self.last_geo_try = 0.0
        self.settings_win = None
        self.settings_targets_box = None

        self.custom_bar_visible = False
        self.custom_bar_for = "t1"
        self.history_log = []
        self.prev_state_1 = True
        self.prev_state_2 = True
        self.pulse_step = 0

        raw_targets = self.config_data.get("targets", list(CORE_TARGETS))
        self.default_targets = list(CORE_TARGETS)
        for t in raw_targets:
            t_clean = str(t).strip()
            if t_clean and t_clean not in self.default_targets and t_clean != CUSTOM_TARGET_OPTION:
                self.default_targets.append(t_clean)

        self.dns_servers = self.config_data.get("dns_servers", [dict(d) for d in DEFAULT_DNS_LIST])
        default_ip2_map = {d["ip"]: d["ip2"] for d in DEFAULT_DNS_LIST}
        for d in self.dns_servers:
            if "ip2" not in d:
                d["ip2"] = default_ip2_map.get(d["ip"], "")

        self.lan_names = dict(self.config_data.get("lan_names", {}))
        self.reset_stats()
        self.start_net = psutil.net_io_counters()

        # موتور مانیتور مصرف شبکه به تفکیک هر برنامه (در حالت Admin کرنل ETW روشن می‌شود)
        self.per_app_monitor = PerAppNetworkMonitor()
        self.is_etw_active = self.per_app_monitor.start() if is_admin() else False

        self.led_live_frames = [
            ctk.CTkImage(
                light_image=render_aa_status_led(COLOR_GREEN, g, 18),
                dark_image=render_aa_status_led(COLOR_GREEN, g, 18),
                size=(18, 18),
            )
            for g in (0.25, 0.45, 0.70, 0.95, 1.0, 0.85, 0.60, 0.35)
        ]
        self.led_idle_img = ctk.CTkImage(
            light_image=render_aa_status_led("#64748B", 0.0, 18),
            dark_image=render_aa_status_led("#64748B", 0.0, 18),
            size=(18, 18),
        )
        self.led_err_img = ctk.CTkImage(
            light_image=render_aa_status_led(COLOR_RED, 0.9, 18),
            dark_image=render_aa_status_led(COLOR_RED, 0.9, 18),
            size=(18, 18),
        )
        self.ui_icons = {}

        self._setup_ui()
        self.tray_mini = TrayMiniController(self)
        self.apply_theme(self.theme_name, save=False)

        if self.is_pinned:
            self.attributes("-topmost", True)

        if "--minimized" in sys.argv:
            self.after(120, self.hide_window)

        if "--tab" in sys.argv:
            try:
                target_tab = sys.argv[sys.argv.index("--tab") + 1]
                if target_tab in ("ping", "net", "dns", "lan"):
                    self.after(120, lambda t=target_tab: self.switch_tab(t))
            except Exception:
                pass

        if self.instance_mgr:
            threading.Thread(target=self._single_instance_listener, daemon=True).start()

        threading.Thread(target=self._update_my_ip_loop, daemon=True).start()
        threading.Thread(target=self._network_monitor_loop, daemon=True).start()
        threading.Thread(target=self.tab_dns_view.refresh_active_dns, daemon=True).start()
        self._animate_status_pill()

    # ================= پنجره، آیکون و تنظیمات =================
    def _generate_app_ico(self):
        try:
            img = build_pulse_icon((0, 210, 255), size=256)
            img.save(
                self.app_icon_path,
                format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
            )
        except Exception:
            pass

    def apply_window_icon(self, target_win=None):
        win = target_win or self
        try:
            if os.path.exists(self.app_icon_path):
                win.iconbitmap(self.app_icon_path)
        except Exception:
            pass

    def center_window(self, width, height):
        self.update_idletasks()
        try:
            scale = self._get_window_scaling()
        except Exception:
            scale = 1.0
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        x = max(0, int((ws - int(width * scale)) / 2))
        y = max(0, int((hs - int(height * scale)) / 2))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def hide_window(self):
        self.withdraw()

    def restore_window(self):
        self.deiconify()
        try:
            self.state("normal")
        except Exception:
            pass
        self.lift()
        self.attributes("-topmost", True)
        self.focus_force()
        self.after(180, lambda: self.attributes("-topmost", True if self.is_mini else self.is_pinned))

    def request_admin_elevation(self):
        """ارتقای اختیاری به حالت Admin و بازگشایی مستقیم در تب Network Usage"""
        try:
            self.per_app_monitor.stop()
        except Exception:
            pass

        # آزادسازی Mutex تک‌اجرایی قبل از اجرای نسخه Admin تا تداخلی پیش نیاید
        mgr = self.instance_mgr
        self.instance_mgr = None
        if mgr:
            try:
                mgr.cleanup()
            except Exception:
                pass

        if relaunch_as_admin(None, extra_args="--tab net"):
            self.quit_window()

    def reset_app_usage_totals(self):
        self.per_app_monitor.reset_totals()
        snap = self.per_app_monitor.get_snapshot(limit=22)
        self.tab_net_view.apps_panel.update_rows(snap)

    def quit_window(self):
        self.app_alive = False
        self.is_running = False
        self.tab_lan_view.auto_scan = False
        try:
            self.per_app_monitor.stop()
        except Exception:
            pass
        self.save_config()
        self.tray_mini.stop_tray()
        if self.instance_mgr:
            try:
                self.instance_mgr.cleanup()
            except Exception:
                pass
            self.instance_mgr = None
        self.destroy()

    def _single_instance_listener(self):
        while self.app_alive and self.instance_mgr:
            try:
                if self.instance_mgr.wait_for_show(500):
                    self.after(0, self.restore_window)
            except Exception:
                break

    def save_config(self):
        save_config(
            self.config_path,
            {
                "theme": self.theme_name,
                "targets": self.default_targets[:20],
                "last_t1": self.target1_var.get(),
                "last_t2": self.target2_var.get(),
                "is_pinned": self.is_pinned,
                "sound_enabled": self.sound.enabled,
                "sfx_volume": self.sound.volume,
                "sfx_profile": self.sound.profile,
                "custom_sfx_lost": self.sound.custom_lost,
                "custom_sfx_online": self.sound.custom_online,
                "ping_interval": self.ping_interval,
                "mini_opacity": self.mini_opacity,
                "mini_style": self.mini_style,
                "mini_pos": self.mini_pos,
                "vpn_win_notify": self.vpn_win_notify,
                "high_ping_threshold": self.high_ping_threshold,
                "dns_servers": self.dns_servers,
                "lan_names": self.lan_names,
            },
        )

    def reset_stats(self):
        self.stats = {
            "t1": {"min": 9999, "max": 0, "sum": 0, "count": 0, "sent": 0, "lost": 0, "last": None, "jit_sum": 0, "jit_cnt": 0},
            "t2": {"min": 9999, "max": 0, "sum": 0, "count": 0, "sent": 0, "lost": 0, "last": None, "jit_sum": 0, "jit_cnt": 0},
        }

    def _dropdown_values(self):
        return self.default_targets + [CUSTOM_TARGET_OPTION]

    def get_formatted_ip_texts(self):
        if self.current_my_ip in ("Loading...", "OFFLINE"):
            return self.current_my_ip, f"IP: {self.current_my_ip}", "--"
        loc = self.current_loc
        cc = loc.split(",")[-1].strip() if loc and "," in loc else loc
        mini_text = f"IP: {self.current_my_ip} [{cc}]" if cc else f"IP: {self.current_my_ip}"
        return self.current_my_ip, mini_text, (cc if cc else "IP")

    # ================= ساخت هدر، نوار کشویی و تب‌ها =================
    def _setup_ui(self):
        T = self.T
        self.main_container = ctk.CTkFrame(self, fg_color=T["bg"], corner_radius=0)
        self.main_container.pack(fill="both", expand=True)

        # --- نوار برند مینیمال + آی‌پی و لوکیشن ---
        self.brand_bar = ctk.CTkFrame(self.main_container, fg_color=T["bg"], corner_radius=0)
        self.brand_bar.pack(pady=(12, 4), padx=22, fill="x")

        self.lbl_brand_icon = ctk.CTkLabel(self.brand_bar, text="", bg_color=T["bg"])
        self.lbl_brand_icon.pack(side="left", padx=(0, 8))

        self.lbl_brand_title = ctk.CTkLabel(self.brand_bar, text="Network Tools", font=("Segoe UI", 14, "bold"), bg_color=T["bg"])
        self.lbl_brand_title.pack(side="left")

        self.lbl_brand_pro = ctk.CTkLabel(self.brand_bar, text="Pro", font=("Segoe UI", 14, "bold"), bg_color=T["bg"])
        self.lbl_brand_pro.pack(side="left", padx=(4, 0))

        self.btn_refresh_ip = ctk.CTkButton(self.brand_bar, text="", width=32, height=32, corner_radius=9, bg_color=T["bg"], command=self.force_refresh_ip)
        self.btn_refresh_ip.pack(side="right", padx=(6, 0))

        self.my_ip_box = ctk.CTkFrame(self.brand_bar, corner_radius=10, border_width=1, bg_color=T["bg"], cursor="hand2")
        self.my_ip_box.pack(side="right")

        self.lbl_ip_icon = ctk.CTkLabel(self.my_ip_box, text="", cursor="hand2")
        self.lbl_ip_icon.pack(side="left", padx=(10, 4), pady=5)

        self.lbl_my_ip = ctk.CTkLabel(self.my_ip_box, text=self.current_my_ip, font=("Consolas", 12, "bold"), cursor="hand2")
        self.lbl_my_ip.pack(side="left", padx=(2, 10), pady=5)

        self.lbl_my_loc = ctk.CTkLabel(self.my_ip_box, text="", font=("Consolas", 11, "bold"), corner_radius=6, height=22, cursor="hand2")

        for w in (self.my_ip_box, self.lbl_ip_icon, self.lbl_my_ip, self.lbl_my_loc):
            w.bind("<Button-1>", self.copy_ip_to_clipboard)

        # --- پنل کنترل اصلی ---
        self.top_frame = ctk.CTkFrame(self.main_container, corner_radius=14, border_width=1, bg_color=T["bg"])
        self.top_frame.pack(pady=(4, 6), padx=20, fill="x")

        init_t1 = self.config_data.get("last_t1", "8.8.8.8")
        if init_t1 == CUSTOM_TARGET_OPTION or not init_t1:
            init_t1 = "8.8.8.8"
        self.target1_var = ctk.StringVar(value=init_t1)
        self._prev_t1 = init_t1

        self.target1_menu = ctk.CTkOptionMenu(
            self.top_frame, variable=self.target1_var, values=self._dropdown_values(),
            width=155, height=34, font=("Consolas", 12), corner_radius=9, command=self._on_t1_selected,
        )
        self.target1_menu.pack(side="left", padx=(12, 4), pady=10)

        self.btn_add_custom_t1 = ctk.CTkButton(self.top_frame, text="", width=34, height=34, corner_radius=9, command=lambda: self.toggle_custom_target_bar("t1"))
        self.btn_add_custom_t1.pack(side="left", padx=(0, 4))

        self.btn_target_action = ctk.CTkButton(self.top_frame, text="", width=32, height=34, corner_radius=9, command=self.on_target_action_click)

        self.btn_toggle_t2 = ctk.CTkButton(self.top_frame, text="+ T2", width=50, height=34, corner_radius=9, font=("Segoe UI", 11, "bold"), command=self.toggle_target2)
        self.btn_toggle_t2.pack(side="left", padx=4)

        init_t2 = self.config_data.get("last_t2", "google.com")
        if init_t2 == CUSTOM_TARGET_OPTION or not init_t2:
            init_t2 = "google.com"
        self.target2_var = ctk.StringVar(value=init_t2)
        self._prev_t2 = init_t2

        self.target2_menu = ctk.CTkOptionMenu(
            self.top_frame, variable=self.target2_var, values=self._dropdown_values(),
            width=152, height=34, font=("Consolas", 12), corner_radius=9, command=self._on_t2_selected,
        )

        self.btn_settings = ctk.CTkButton(self.top_frame, text="SETTINGS", compound="left", width=102, height=34, corner_radius=9, font=("Segoe UI", 11, "bold"), command=lambda: open_settings_modal(self))
        self.btn_settings.pack(side="right", padx=(4, 12))

        self.btn_mini = ctk.CTkButton(self.top_frame, text="MINI", compound="left", width=78, height=34, corner_radius=9, font=("Segoe UI", 11, "bold"), command=lambda: self.tray_mini.enable_mini_mode())
        self.btn_mini.pack(side="right", padx=4)

        self.toggle_btn = ctk.CTkButton(self.top_frame, text="START MONITOR", width=134, height=34, corner_radius=9, font=("Segoe UI", 12, "bold"), command=self.toggle_monitor, fg_color=COLOR_GREEN, text_color="#000000", hover_color="#059669")
        self.toggle_btn.pack(side="right", padx=(6, 6))

        self.status_pill = ctk.CTkFrame(self.top_frame, corner_radius=10, border_width=1, height=32)
        self.status_pill.pack(side="right", padx=(4, 4))
        self.lbl_status_led = ctk.CTkLabel(self.status_pill, text="", image=self.led_idle_img, width=18)
        self.lbl_status_led.pack(side="left", padx=(9, 3), pady=5)
        self.lbl_status_txt = ctk.CTkLabel(self.status_pill, text="IDLE", font=("Consolas", 10, "bold"))
        self.lbl_status_txt.pack(side="left", padx=(0, 10), pady=5)

        # --- نوار کشویی افزودن تارگت دلخواه ---
        self.custom_target_bar = ctk.CTkFrame(self.main_container, corner_radius=12, border_width=1.5, bg_color=T["bg"])
        self.lbl_custom_bar_tag = ctk.CTkLabel(self.custom_target_bar, text="CUSTOM T1", font=("Consolas", 11, "bold"), corner_radius=6, width=82, height=26)
        self.lbl_custom_bar_tag.pack(side="left", padx=(10, 8), pady=8)

        self.entry_custom_target = ctk.CTkEntry(self.custom_target_bar, placeholder_text="Enter IP or Domain  (e.g. 1.1.1.1 or discord.com)", height=30, font=("Consolas", 12), corner_radius=8)
        self.entry_custom_target.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=8)
        self.entry_custom_target.bind("<Return>", lambda e: self.apply_custom_target_bar())
        self.entry_custom_target.bind("<Escape>", lambda e: self.hide_custom_target_bar())

        self.chk_save_target_var = ctk.BooleanVar(value=False)
        self.chk_save_target = ctk.CTkCheckBox(self.custom_target_bar, text="Save to list", variable=self.chk_save_target_var, font=("Segoe UI", 11, "bold"), width=104, checkbox_width=18, checkbox_height=18, corner_radius=5)
        self.chk_save_target.pack(side="left", padx=(0, 10))

        self.btn_apply_target = ctk.CTkButton(self.custom_target_bar, text="APPLY", width=78, height=30, corner_radius=8, font=("Segoe UI", 11, "bold"), command=self.apply_custom_target_bar)
        self.btn_apply_target.pack(side="left", padx=(0, 6))

        self.btn_close_target_bar = ctk.CTkButton(self.custom_target_bar, text="", width=30, height=30, corner_radius=8, command=self.hide_custom_target_bar)
        self.btn_close_target_bar.pack(side="left", padx=(0, 10))

        # --- منوی ۴ تب با نسبت هندسی دقیق (بدون تداخل دکمه با منحنی کادر) ---
        self.custom_tab_menu = ctk.CTkFrame(self.main_container, corner_radius=14, border_width=1, bg_color=T["bg"])
        self.custom_tab_menu.pack(pady=(2, 8))

        self.btn_tab_ping = ctk.CTkButton(self.custom_tab_menu, text=" PING RADAR", compound="left", width=156, height=34, font=("Segoe UI", 12, "bold"), corner_radius=9, command=lambda: self.switch_tab("ping"))
        self.btn_tab_ping.pack(side="left", padx=(7, 3), pady=6)

        self.btn_tab_net = ctk.CTkButton(self.custom_tab_menu, text=" NETWORK USAGE", compound="left", width=162, height=34, font=("Segoe UI", 12, "bold"), corner_radius=9, command=lambda: self.switch_tab("net"))
        self.btn_tab_net.pack(side="left", padx=3, pady=6)

        self.btn_tab_dns = ctk.CTkButton(self.custom_tab_menu, text=" DNS & ROUTES", compound="left", width=156, height=34, font=("Segoe UI", 12, "bold"), corner_radius=9, command=lambda: self.switch_tab("dns"))
        self.btn_tab_dns.pack(side="left", padx=3, pady=6)

        self.btn_tab_lan = ctk.CTkButton(self.custom_tab_menu, text=" LAN DEVICES", compound="left", width=154, height=34, font=("Segoe UI", 12, "bold"), corner_radius=9, command=lambda: self.switch_tab("lan"))
        self.btn_tab_lan.pack(side="left", padx=(3, 7), pady=6)

        # ویوهای ماژولار هر ۴ تب
        self.tab_ping_view = PingTabView(self.main_container, self)
        self.tab_net_view = NetworkTabView(self.main_container, self)
        self.tab_dns_view = DnsTabView(self.main_container, self)
        self.tab_lan_view = LanTabView(self.main_container, self)

        # فوتر
        self.footer = ctk.CTkFrame(self.main_container, fg_color=T["bg"], corner_radius=0)
        self.footer.pack(pady=(6, 12), padx=20, fill="x", side="bottom")
        self.btn_export = ctk.CTkButton(self.footer, text="EXPORT CSV", width=120, height=30, corner_radius=8, bg_color=T["bg"], font=("Segoe UI", 11, "bold"), command=self.export_csv)
        self.btn_export.pack(side="left")
        self.lbl_footer = ctk.CTkLabel(self.footer, text=f"{APP_NAME}  •  by Diako  •  v{APP_VERSION}", font=("Segoe UI", 11, "italic"), bg_color=T["bg"])
        self.lbl_footer.pack(side="right")

    # ================= آیکون‌ها و اعمال تم (با همگام‌سازی کامل bg_color) =================
    def _rebuild_ui_icons(self):
        T = self.T
        btn_fg = "#000000" if T["mode"] == "Dark" else "#FFFFFF"

        def make(kind, color, sz=16):
            im = render_aa_icon(kind, color, size=sz)
            return ctk.CTkImage(light_image=im, dark_image=im, size=(sz, sz))

        self.ui_icons = {
            "brand": ctk.CTkImage(
                light_image=build_pulse_icon(hex_to_rgba(T["accent1"])[:3], size=64),
                dark_image=build_pulse_icon(hex_to_rgba(T["accent1"])[:3], size=64),
                size=(22, 22),
            ),
            "gear": make("gear", T["text"], 16),
            "mini": make("mini", T["text"], 15),
            "globe": make("globe", T["accent1"], 16),
            "refresh": make("refresh", T["accent1"], 15),
            "dl": make("dl", COLOR_GREEN, 26),
            "ul": make("ul", COLOR_ORANGE, 26),
            "bolt": make("bolt", "#000000", 15),
            "plus": make("plus", T["accent1"], 14),
            "close": make("close", T["muted"], 13),
            "bookmark": make("bookmark", T["accent1"], 14),
            "trash": make("trash", COLOR_RED, 14),
            "radar_on": make("radar", btn_fg, 16),
            "radar_off": make("radar", T["muted"], 16),
            "net_on": make("activity", "#000000", 16),
            "net_off": make("activity", T["muted"], 16),
            "dns_on": make("dns", "#FFFFFF", 16),
            "dns_off": make("dns", T["muted"], 16),
            "lan_on": make("lan", "#000000", 16),
            "lan_off": make("lan", T["muted"], 16),
        }

        self.lbl_brand_icon.configure(image=self.ui_icons["brand"])
        self.btn_settings.configure(image=self.ui_icons["gear"])
        self.btn_mini.configure(image=self.ui_icons["mini"])
        self.lbl_ip_icon.configure(image=self.ui_icons["globe"])
        self.btn_refresh_ip.configure(image=self.ui_icons["refresh"])
        self.btn_add_custom_t1.configure(image=self.ui_icons["plus"])
        self.btn_close_target_bar.configure(image=self.ui_icons["close"])
        self._update_target_action_btn()

    def apply_theme(self, theme_name, save=True):
        self.theme_name = theme_name
        self.T = THEMES[theme_name]
        T = self.T
        ctk.set_appearance_mode(T["mode"])

        self.configure(fg_color=T["bg"])
        self.main_container.configure(fg_color=T["bg"])
        self.brand_bar.configure(fg_color=T["bg"])
        self.footer.configure(fg_color=T["bg"])
        self._rebuild_ui_icons()

        self.lbl_brand_icon.configure(bg_color=T["bg"])
        self.lbl_brand_title.configure(text_color=T["text"], bg_color=T["bg"])
        self.lbl_brand_pro.configure(text_color=T["accent1"], bg_color=T["bg"])
        self.my_ip_box.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"])
        self.lbl_ip_icon.configure(bg_color=T["card"])
        self.lbl_my_ip.configure(text_color=T["text"], bg_color=T["card"])
        self.lbl_my_loc.configure(fg_color=T["card_elev"], text_color=T["accent1"], bg_color=T["card"])
        self.btn_refresh_ip.configure(fg_color=T["card"], bg_color=T["bg"], border_width=1, border_color=T["border"], hover_color=T["border"])

        self.top_frame.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"])
        self.status_pill.configure(fg_color=T["inner"], border_color=T["border"], bg_color=T["card"])
        self.lbl_status_led.configure(bg_color=T["inner"])
        self.lbl_status_txt.configure(bg_color=T["inner"])

        self.target1_menu.configure(
            fg_color=T["inner"], bg_color=T["card"], button_color=T["accent1"], button_hover_color=T["accent1"],
            dropdown_fg_color=T["card"], dropdown_hover_color=T["card_elev"],
            text_color=T["text"], dropdown_text_color=T["text"],
        )
        self.target2_menu.configure(
            fg_color=T["inner"], bg_color=T["card"], button_color=T["accent2"], button_hover_color=T["accent2"],
            dropdown_fg_color=T["card"], dropdown_hover_color=T["card_elev"],
            text_color=T["text"], dropdown_text_color=T["text"],
        )
        self.btn_add_custom_t1.configure(fg_color=T["card_elev"], bg_color=T["card"], border_width=1, border_color=T["border"], hover_color=T["border"])
        self.btn_toggle_t2.configure(fg_color=T["card_elev"] if self.num_targets == 1 else "#7F1D1D", bg_color=T["card"], text_color=T["text"], border_width=1, border_color=T["border"])
        self.btn_mini.configure(fg_color=T["card_elev"], bg_color=T["card"], text_color=T["text"], border_width=1, border_color=T["border"], hover_color=T["border"])
        self.btn_settings.configure(fg_color=T["card_elev"], bg_color=T["card"], text_color=T["text"], border_width=1, border_color=T["border"], hover_color=T["border"])
        self.toggle_btn.configure(bg_color=T["card"])

        bar_accent = T["accent1"] if self.custom_bar_for == "t1" else T["accent2"]
        self.custom_target_bar.configure(fg_color=T["card"], border_color=bar_accent, bg_color=T["bg"])
        self.lbl_custom_bar_tag.configure(fg_color=T["card_elev"], text_color=bar_accent, bg_color=T["card"])
        self.entry_custom_target.configure(fg_color=T["inner"], border_color=T["border"], text_color=T["text"], bg_color=T["card"])
        self.chk_save_target.configure(text_color=T["text"], fg_color=T["accent1"], border_color=T["muted"], hover_color=T["accent1"], bg_color=T["card"])
        self.btn_apply_target.configure(fg_color=bar_accent, bg_color=T["card"], text_color="#000000" if (self.custom_bar_for == "t1" and T["mode"] == "Dark") else "#FFFFFF")
        self.btn_close_target_bar.configure(fg_color=T["card_elev"], bg_color=T["card"], hover_color=T["border"])

        self.custom_tab_menu.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"])
        self.btn_export.configure(fg_color=T["card"], bg_color=T["bg"], text_color=T["text"], border_width=1, border_color=T["border"], hover_color=T["border"])
        self.lbl_footer.configure(text_color=T["muted"], bg_color=T["bg"])

        self.tab_ping_view.apply_theme(T)
        self.tab_net_view.apply_theme(T, self.ui_icons)
        self.tab_dns_view.apply_theme(T)
        self.tab_lan_view.apply_theme(T)
        self.tray_mini.apply_theme(T)

        self.switch_tab(self.current_tab)
        if save:
            self.save_config()

    def switch_tab(self, tab_name):
        self.current_tab = tab_name
        T = self.T
        self.btn_tab_ping.configure(fg_color=T["card"], bg_color=T["card"], text_color=T["muted"], hover_color=T["card_elev"], image=self.ui_icons.get("radar_off"))
        self.btn_tab_net.configure(fg_color=T["card"], bg_color=T["card"], text_color=T["muted"], hover_color=T["card_elev"], image=self.ui_icons.get("net_off"))
        self.btn_tab_dns.configure(fg_color=T["card"], bg_color=T["card"], text_color=T["muted"], hover_color=T["card_elev"], image=self.ui_icons.get("dns_off"))
        self.btn_tab_lan.configure(fg_color=T["card"], bg_color=T["card"], text_color=T["muted"], hover_color=T["card_elev"], image=self.ui_icons.get("lan_off"))

        for view in (self.tab_ping_view, self.tab_net_view, self.tab_dns_view, self.tab_lan_view):
            view.pack_forget()

        if tab_name == "ping":
            self.btn_tab_ping.configure(fg_color=T["accent1"], hover_color=T["accent1"], text_color="#000000" if T["mode"] == "Dark" else "#FFFFFF", image=self.ui_icons.get("radar_on"))
            self.tab_ping_view.pack(padx=20, pady=4, fill="both", expand=True)
            self.after(30, lambda: self.tab_ping_view.draw_grid(rebuild_base=True))
        elif tab_name == "net":
            self.btn_tab_net.configure(fg_color=COLOR_GREEN, hover_color=COLOR_GREEN, text_color="#000000", image=self.ui_icons.get("net_on"))
            self.tab_net_view.pack(padx=20, pady=4, fill="both", expand=True)
            self.tab_net_view.on_tab_selected()
        elif tab_name == "dns":
            self.btn_tab_dns.configure(fg_color=T["accent2"], hover_color=T["accent2"], text_color="#FFFFFF", image=self.ui_icons.get("dns_on"))
            self.tab_dns_view.pack(padx=20, pady=4, fill="both", expand=True)
        else:
            self.btn_tab_lan.configure(fg_color=COLOR_ORANGE, hover_color=COLOR_ORANGE, text_color="#000000", image=self.ui_icons.get("lan_on"))
            self.tab_lan_view.pack(padx=20, pady=4, fill="both", expand=True)
            self.tab_lan_view.on_tab_selected()

    # ================= انیمیشن چراغ وضعیت =================
    def _animate_status_pill(self):
        if not self.app_alive:
            return
        if self.is_running:
            if not self.prev_state_1 and (self.num_targets == 1 or not self.prev_state_2):
                self.lbl_status_led.configure(image=self.led_err_img)
                self.lbl_status_txt.configure(text="LOST", text_color=COLOR_RED)
                self.status_pill.configure(border_color=COLOR_RED)
            else:
                self.pulse_step = (self.pulse_step + 1) % len(self.led_live_frames)
                self.lbl_status_led.configure(image=self.led_live_frames[self.pulse_step])
                self.lbl_status_txt.configure(text="LIVE", text_color=COLOR_GREEN)
                self.status_pill.configure(border_color=COLOR_GREEN)
        else:
            self.lbl_status_led.configure(image=self.led_idle_img)
            self.lbl_status_txt.configure(text="IDLE", text_color=self.T["muted"])
            self.status_pill.configure(border_color=self.T["border"])
        self.after(140, self._animate_status_pill)

    # ================= سیستم کشویی انتخاب و مدیریت تارگت =================
    def _on_t1_selected(self, choice):
        if choice == CUSTOM_TARGET_OPTION:
            self.target1_var.set(self._prev_t1)
            self.show_custom_target_bar("t1")
        else:
            self._prev_t1 = choice
            self._update_target_action_btn()

    def _on_t2_selected(self, choice):
        if choice == CUSTOM_TARGET_OPTION:
            self.target2_var.set(self._prev_t2)
            self.show_custom_target_bar("t2")
        else:
            self._prev_t2 = choice

    def toggle_custom_target_bar(self, which="t1"):
        if self.is_running:
            return
        if self.custom_bar_visible and self.custom_bar_for == which:
            self.hide_custom_target_bar()
        else:
            self.show_custom_target_bar(which)

    def show_custom_target_bar(self, which="t1"):
        if self.is_running:
            return
        self.custom_bar_for = which
        self.custom_bar_visible = True
        T = self.T
        accent = T["accent1"] if which == "t1" else T["accent2"]
        self.custom_target_bar.configure(border_color=accent)
        self.lbl_custom_bar_tag.configure(text="CUSTOM T1" if which == "t1" else "CUSTOM T2", text_color=accent)
        self.btn_apply_target.configure(fg_color=accent, text_color="#000000" if (which == "t1" and T["mode"] == "Dark") else "#FFFFFF")
        self.chk_save_target_var.set(False)
        self.entry_custom_target.delete(0, "end")
        self.custom_target_bar.pack(pady=(0, 6), padx=20, fill="x", after=self.top_frame)
        self.after(30, self.entry_custom_target.focus_set)

    def hide_custom_target_bar(self):
        if self.custom_bar_visible:
            self.custom_bar_visible = False
            self.custom_target_bar.pack_forget()

    def apply_custom_target_bar(self):
        raw = self.entry_custom_target.get().strip()
        clean = re.sub(r"^https?://", "", raw, flags=re.IGNORECASE).split("/")[0].split(":")[0].strip()
        if not clean or " " in clean or clean == CUSTOM_TARGET_OPTION:
            self.entry_custom_target.configure(border_color=COLOR_RED)
            self.after(1000, lambda: self.entry_custom_target.configure(border_color=self.T["border"]))
            return

        if self.chk_save_target_var.get():
            self.add_custom_target(clean)

        if self.custom_bar_for == "t1":
            self.target1_var.set(clean)
            self._prev_t1 = clean
            self._update_target_action_btn()
        else:
            self.target2_var.set(clean)
            self._prev_t2 = clean
        self.hide_custom_target_bar()

    def _update_target_action_btn(self):
        if not hasattr(self, "btn_target_action") or not self.ui_icons:
            return
        T = self.T
        val = self.target1_var.get().strip()
        if not val or val in CORE_TARGETS or val == CUSTOM_TARGET_OPTION:
            self.btn_target_action.pack_forget()
            return

        if val in self.default_targets:
            self.btn_target_action.configure(
                image=self.ui_icons["trash"], state="disabled" if self.is_running else "normal",
                fg_color=T["card_elev"], bg_color=T["card"], hover_color="#451A1A",
                border_width=1, border_color=COLOR_RED,
            )
        else:
            self.btn_target_action.configure(
                image=self.ui_icons["bookmark"], state="disabled" if self.is_running else "normal",
                fg_color=T["card_elev"], bg_color=T["card"], hover_color=T["border"],
                border_width=1, border_color=T["accent1"],
            )

        if not self.btn_target_action.winfo_ismapped():
            self.btn_target_action.pack(side="left", padx=(0, 4), after=self.btn_add_custom_t1)

    def on_target_action_click(self):
        if self.is_running:
            return
        val = self.target1_var.get().strip()
        if not val or val in CORE_TARGETS:
            return
        if val in self.default_targets:
            self.remove_custom_target(val)
        else:
            self.add_custom_target(val)

    def add_custom_target(self, target):
        target = target.strip()
        if target and target not in self.default_targets and target != CUSTOM_TARGET_OPTION:
            self.default_targets.append(target)
            vals = self._dropdown_values()
            self.target1_menu.configure(values=vals)
            self.target2_menu.configure(values=vals)
            self.save_config()
        self._update_target_action_btn()
        refresh_settings_targets_ui(self)

    def remove_custom_target(self, target):
        if target in CORE_TARGETS:
            return
        self.default_targets = [t for t in self.default_targets if t != target]
        vals = self._dropdown_values()
        self.target1_menu.configure(values=vals)
        self.target2_menu.configure(values=vals)
        if not self.is_running:
            if self.target1_var.get().strip() == target:
                self.target1_var.set(CORE_TARGETS[0])
                self._prev_t1 = CORE_TARGETS[0]
            if self.target2_var.get().strip() == target:
                self.target2_var.set("google.com")
                self._prev_t2 = "google.com"
        self.save_config()
        self._update_target_action_btn()
        refresh_settings_targets_ui(self)

    def clean_extra_targets(self):
        self.default_targets = list(CORE_TARGETS)
        vals = self._dropdown_values()
        self.target1_menu.configure(values=vals)
        self.target2_menu.configure(values=vals)
        if not self.is_running:
            if self.target1_var.get().strip() not in CORE_TARGETS:
                self.target1_var.set(CORE_TARGETS[0])
                self._prev_t1 = CORE_TARGETS[0]
            if self.target2_var.get().strip() not in CORE_TARGETS:
                self.target2_var.set("google.com")
                self._prev_t2 = "google.com"
        self.save_config()
        self._update_target_action_btn()
        refresh_settings_targets_ui(self)

    def apply_dns_as_t1(self, ip):
        if not self.is_running:
            self.target1_var.set(ip)
            self._prev_t1 = ip
            self._update_target_action_btn()
            self.switch_tab("ping")

    # ================= کنترل‌های پینگ و حلقه مانیتورینگ =================
    def toggle_target2(self):
        if self.is_running:
            return
        if self.num_targets == 1:
            self.num_targets = 2
            self.btn_toggle_t2.configure(text="- T2", fg_color="#7F1D1D", hover_color="#991B1B")
            self.target2_menu.pack(side="left", padx=6, after=self.btn_toggle_t2)
            self.tab_ping_view.set_target2_visible(True)
        else:
            self.num_targets = 1
            self.btn_toggle_t2.configure(text="+ T2", fg_color=self.T["card_elev"])
            self.target2_menu.pack_forget()
            self.tab_ping_view.set_target2_visible(False)
            if self.custom_bar_visible and self.custom_bar_for == "t2":
                self.hide_custom_target_bar()

    def toggle_monitor(self):
        if self.is_running:
            self.is_running = False
            self.toggle_btn.configure(text="START MONITOR", fg_color=COLOR_GREEN, text_color="#000000", hover_color="#059669")
            self.target1_menu.configure(state="normal")
            self.target2_menu.configure(state="normal")
            self.btn_add_custom_t1.configure(state="normal")
            self.btn_toggle_t2.configure(state="normal")
            self._update_target_action_btn()
            self.tray_mini.refresh_tray_menu()
            self.tray_mini.update_tray_tooltip()
        else:
            t1 = self.target1_var.get().strip()
            t2 = self.target2_var.get().strip()
            if not t1 or t1 == CUSTOM_TARGET_OPTION:
                return
            self.hide_custom_target_bar()
            self.is_running = True
            self.target1_menu.configure(state="disabled")
            self.target2_menu.configure(state="disabled")
            self.btn_add_custom_t1.configure(state="disabled")
            self.btn_toggle_t2.configure(state="disabled")
            self._update_target_action_btn()

            self.reset_stats()
            self.save_config()
            self.tab_ping_view.set_target_names(t1, t2)

            self.toggle_btn.configure(text="STOP MONITOR", fg_color=COLOR_RED, text_color="#FFFFFF", hover_color="#DC2626")
            self.tray_mini.refresh_tray_menu()
            self.tray_mini.update_tray_tooltip()
            threading.Thread(target=self._monitor_loop, daemon=True).start()

    def _monitor_loop(self):
        while self.is_running and self.app_alive:
            t1 = self.target1_var.get().strip()
            t2 = self.target2_var.get().strip() if self.num_targets == 2 else None

            p1 = get_ping(t1)
            p2 = get_ping(t2) if t2 else None

            entry = {"Time": datetime.now().strftime("%H:%M:%S"), f"Target_{t1}": "TIMEOUT" if p1 == -1 else p1}
            if t2:
                entry[f"Target_{t2}"] = "TIMEOUT" if p2 == -1 else p2
            self.history_log.append(entry)

            if self.app_alive:
                self.after(0, self._update_dashboard, p1, p2, t1, t2)
            time.sleep(self.ping_interval)

    def _update_stats(self, p, t_key):
        s = self.stats[t_key]
        s["sent"] += 1
        if p == -1:
            s["lost"] += 1
            avg = int(s["sum"] / (s["count"] if s["count"] > 0 else 1))
        else:
            if s["last"] is not None:
                s["jit_sum"] += abs(p - s["last"])
                s["jit_cnt"] += 1
            s["last"] = p
            s["count"] += 1
            s["sum"] += p
            if p < s["min"]:
                s["min"] = p
            if p > s["max"]:
                s["max"] = p
            avg = int(s["sum"] / s["count"])

        loss_pct = int((s["lost"] / s["sent"]) * 100)
        disp_min = s["min"] if s["min"] != 9999 else 0
        jit = int(s["jit_sum"] / s["jit_cnt"]) if s["jit_cnt"] > 0 else 0
        return f"Min:{disp_min}  |  Avg:{avg}  |  Max:{s['max']}  |  Jit:{jit}ms  |  Loss:{loss_pct}%", loss_pct

    def _update_dashboard(self, p1, p2, t1, t2):
        time_str = datetime.now().strftime("%H:%M:%S")
        is_connected = (p1 != -1) or (self.num_targets == 2 and p2 != -1)
        self.tray_mini.set_tray_status(is_connected)

        c1 = get_health_color(p1)
        stats1_txt, loss1 = self._update_stats(p1, "t1")
        self.tab_ping_view.update_card(1, p1, stats1_txt, loss1)

        if p1 != -1:
            if not self.prev_state_1:
                show_os_notification("Restored", f"{t1} is back online.")
                self.sound.play("restored")
            elif self.high_ping_threshold > 0 and p1 >= self.high_ping_threshold:
                now_ts = time.time()
                if now_ts - self.last_high_ping_alert >= 15.0:
                    self.last_high_ping_alert = now_ts
                    show_os_notification("High Ping Alert", f"{t1} latency spiked to {p1} ms!")
                    self.sound.play("warn")
            self.prev_state_1 = True
        else:
            if self.prev_state_1:
                show_os_notification("Connection Lost", f"Timeout on {t1}.")
                self.sound.play("lost")
            self.prev_state_1 = False

        c2 = None
        if self.num_targets == 2:
            c2 = get_health_color(p2)
            stats2_txt, loss2 = self._update_stats(p2, "t2")
            self.tab_ping_view.update_card(2, p2, stats2_txt, loss2)
            if p2 != -1:
                if not self.prev_state_2:
                    show_os_notification("Restored", f"{t2} is back online.")
                    self.sound.play("restored")
                self.prev_state_2 = True
            else:
                if self.prev_state_2:
                    show_os_notification("Connection Lost", f"Timeout on {t2}.")
                    self.sound.play("lost")
                self.prev_state_2 = False

        self.tray_mini.update_ping_values(p1, c1, p2, c2)
        self.tab_ping_view.append_ping_log(time_str, t1, p1, t2, p2, self.num_targets)
        self.tab_ping_view.push_graph_point(p1, p2, time_str, self.num_targets)

    # ================= مانیتور شبکه و استعلام آی‌پی/لوکیشن =================
    def _network_monitor_loop(self):
        last_net = psutil.net_io_counters()
        while self.app_alive:
            time.sleep(1)
            cur = psutil.net_io_counters()
            dl = max(0.0, (cur.bytes_recv - last_net.bytes_recv) / 1024.0)
            ul = max(0.0, (cur.bytes_sent - last_net.bytes_sent) / 1024.0)
            last_net = cur

            total_dl = max(0, cur.bytes_recv - self.start_net.bytes_recv)
            total_ul = max(0, cur.bytes_sent - self.start_net.bytes_sent)
            apps = self.per_app_monitor.get_snapshot(limit=22)

            if self.app_alive:
                self.after(0, self._on_network_tick, dl, ul, total_dl, total_ul, apps)

    def _on_network_tick(self, dl, ul, total_dl, total_ul, apps):
        self.tab_net_view.update_network(dl, ul, total_dl, total_ul, apps, is_active_tab=(self.current_tab == "net"))
        self.tray_mini.update_network_speed(dl, ul)

    def copy_ip_to_clipboard(self, event=None):
        if self.current_my_ip in ("Loading...", "OFFLINE"):
            return
        self.clipboard_clear()
        self.clipboard_append(self.current_my_ip)
        self.lbl_my_ip.configure(text=f"COPIED: {self.current_my_ip}", text_color=self.T["accent1"])
        self.my_ip_box.configure(border_color=self.T["accent1"])
        self.after(1200, self._restore_ip_label)

    def _restore_ip_label(self):
        ip_text, _, _ = self.get_formatted_ip_texts()
        self.lbl_my_ip.configure(text=ip_text, text_color=self.T["text"])
        self.my_ip_box.configure(border_color=self.T["border"])
        if self.current_loc and self.current_my_ip not in ("Loading...", "OFFLINE"):
            self.lbl_my_ip.pack_configure(padx=(2, 6))
            self.lbl_my_loc.configure(text=f" {self.current_loc} ", fg_color=self.T["card_elev"], text_color=self.T["accent1"], bg_color=self.T["card"])
            self.lbl_my_loc.pack(side="left", padx=(0, 8), pady=5)
        else:
            self.lbl_my_ip.pack_configure(padx=(2, 10))
            self.lbl_my_loc.pack_forget()

    def force_refresh_ip(self):
        self.lbl_my_ip.configure(text="Checking IP...", text_color=self.T["accent1"])
        self.lbl_my_ip.pack_configure(padx=(2, 10))
        self.lbl_my_loc.pack_forget()

        def _worker():
            new_ip = fetch_public_ip()
            if new_ip:
                self.geo_cache.pop(new_ip, None)
                self.last_geo_try = time.time()
                loc = fetch_geo_for_ip(new_ip, self.geo_cache)
                old_ip = self.current_my_ip
                self.current_my_ip = new_ip
                self.current_loc = loc
                self.after(0, self._on_ip_updated, old_ip, new_ip, loc)
            else:
                self.current_my_ip = "OFFLINE"
                self.current_loc = ""
                self.after(0, self._on_ip_offline)

        threading.Thread(target=_worker, daemon=True).start()

    def _update_my_ip_loop(self):
        while self.app_alive:
            new_ip = fetch_public_ip()
            if not self.app_alive:
                break

            if new_ip:
                ip_changed = new_ip != self.current_my_ip
                need_loc = (not self.current_loc) and (time.time() - self.last_geo_try >= 8.0)

                if ip_changed:
                    old_ip = self.current_my_ip
                    self.last_geo_try = time.time()
                    loc = fetch_geo_for_ip(new_ip, self.geo_cache)
                    self.current_my_ip = new_ip
                    self.current_loc = loc
                    self.after(0, self._on_ip_updated, old_ip, new_ip, loc)
                elif need_loc:
                    self.last_geo_try = time.time()
                    loc = fetch_geo_for_ip(new_ip, self.geo_cache)
                    if loc:
                        self.current_loc = loc
                        self.after(0, self._blink_ip_label, loc)
            elif self.current_my_ip not in ("OFFLINE", "Loading..."):
                self.current_my_ip = "OFFLINE"
                self.current_loc = ""
                self.after(0, self._on_ip_offline)

            time.sleep(5)

    def _on_ip_updated(self, old_ip, new_ip, new_loc):
        self._blink_ip_label(new_loc)
        if old_ip not in ("Loading...", "OFFLINE") and old_ip != new_ip:
            time_str = datetime.now().strftime("%H:%M:%S")
            loc_str = f" ({new_loc})" if new_loc else ""
            self.tab_ping_view.append_info_log(time_str, f"IP CHANGED -> {new_ip}{loc_str}")
            if self.vpn_win_notify:
                title = "VPN Disconnected (IR IP!)" if new_loc.endswith("IR") else "IP / VPN Changed"
                show_os_notification(title, f"New IP: {new_ip}{loc_str}")
                self.sound.play("warn")

    def _blink_ip_label(self, loc):
        ip_text, mini_text, cc_short = self.get_formatted_ip_texts()
        self.lbl_my_ip.configure(text=ip_text, text_color=COLOR_GREEN)
        self.my_ip_box.configure(border_color=COLOR_GREEN)
        if loc:
            self.lbl_my_ip.pack_configure(padx=(2, 6))
            self.lbl_my_loc.configure(text=f" {loc} ", fg_color=self.T["card_elev"], text_color=COLOR_GREEN, bg_color=self.T["card"])
            self.lbl_my_loc.pack(side="left", padx=(0, 8), pady=5)
        else:
            self.lbl_my_ip.pack_configure(padx=(2, 10))
            self.lbl_my_loc.pack_forget()

        self.tray_mini.update_ip_display(mini_text, cc_short, highlight=True, offline=False)
        self.after(1000, lambda: self.lbl_my_ip.configure(text_color=self.T["text"]))
        self.after(1000, lambda: self.lbl_my_loc.configure(text_color=self.T["accent1"]))
        self.after(1000, lambda: self.my_ip_box.configure(border_color=self.T["border"]))

    def _on_ip_offline(self):
        self.lbl_my_ip.configure(text="OFFLINE", text_color=COLOR_RED)
        self.lbl_my_ip.pack_configure(padx=(2, 10))
        self.lbl_my_loc.pack_forget()
        self.tray_mini.update_ip_display("IP: OFFLINE", "OFF", offline=True)

    # ================= خروجی CSV =================
    def export_csv(self):
        if not self.history_log:
            return
        filename = f"NetworkToolsPro_Log_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        with open(filename, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.history_log[0].keys())
            writer.writeheader()
            writer.writerows(self.history_log)
        show_os_notification("Exported", f"Saved as {filename}")