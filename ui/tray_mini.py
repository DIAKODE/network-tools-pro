import threading
import customtkinter as ctk
import pystray

from core.config import APP_NAME, COLOR_GREEN, COLOR_ORANGE, COLOR_RED
from core.win_audio import is_unlock_hotkey_pressed, set_window_click_through
from ui.graphics import build_pulse_icon, render_aa_icon


class TrayMiniController:
    def __init__(self, app):
        self.app = app
        self.tray_icon = None
        self.current_tray_color = "green"
        self.is_click_through = False
        self._os_passthrough_active = False
        self._poll_active = False
        self.click_x = 0
        self.click_y = 0

        self.live_ping_t1 = "--"
        self.live_ping_t2 = "--"
        self.live_dl = "0K"
        self.live_ul = "0K"
        self.live_cc = "--"

        self.icon_green = build_pulse_icon((16, 185, 129), size=64)
        self.icon_red = build_pulse_icon((239, 68, 68), size=64)
        self.icon_lock_on = None
        self.icon_lock_off = None

        self._build_lock_icons(app.T)
        self._build_mini_ui()
        self._setup_tray()

    def _build_lock_icons(self, T):
        im_on = render_aa_icon("lock", COLOR_ORANGE, size=13)
        im_off = render_aa_icon("unlock", T["muted"], size=13)
        self.icon_lock_on = ctk.CTkImage(light_image=im_on, dark_image=im_on, size=(13, 13))
        self.icon_lock_off = ctk.CTkImage(light_image=im_off, dark_image=im_off, size=(13, 13))

    def _format_slim_ip(self, offline=False):
        if offline or self.app.current_my_ip == "OFFLINE":
            return "| OFFLINE"
        ip = self.app.current_my_ip
        if ip == "Loading...":
            return "| IP:..."
        loc = self.app.current_loc
        cc = loc.split(",")[-1].strip() if loc and "," in loc else loc
        if cc and cc != "Local Network":
            return f"| {ip} [{cc}]"
        return f"| {ip}"

    def _fixed_slim_width(self):
        return 485 if self.app.num_targets == 2 else 415

    # ================= آیکون هوشمند کنار ساعت =================
    def _setup_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Show App", self.show_window_from_tray, default=True),
            pystray.MenuItem(
                lambda item: "Stop Monitor" if self.app.is_running else "Start Monitor",
                self._tray_toggle_monitor,
            ),
            pystray.MenuItem(
                lambda item: "Exit Mini Mode (Center)" if self.app.is_mini else "Switch to Mini Mode",
                self._tray_toggle_mini,
            ),
            pystray.MenuItem(
                lambda item: "Unlock Overlay (Ctrl+Shift+L)" if self.is_click_through else "Lock Overlay on Game",
                self._tray_toggle_lock,
                visible=lambda item: self.app.is_mini,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._tray_quit),
        )
        self.tray_icon = pystray.Icon("network_tools_pro", self.icon_green, APP_NAME, menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def set_tray_status(self, connected):
        new_color = "green" if connected else "red"
        if new_color != self.current_tray_color and self.tray_icon:
            self.current_tray_color = new_color
            self.tray_icon.icon = self.icon_green if connected else self.icon_red

    def update_tray_tooltip(self):
        if not self.tray_icon:
            return
        state = "LIVE" if self.app.is_running else "IDLE"
        if self.app.num_targets == 2:
            ping_part = f"T1:{self.live_ping_t1} T2:{self.live_ping_t2}"
        else:
            ping_part = f"Ping:{self.live_ping_t1}"
        lock_tag = " [LOCKED]" if self.is_click_through else ""
        tip = f"{APP_NAME} ({state}){lock_tag}\n{ping_part} | DL:{self.live_dl} UL:{self.live_ul} | {self.live_cc}"
        try:
            self.tray_icon.title = tip[:124]
        except Exception:
            pass

    def refresh_tray_menu(self):
        if self.tray_icon:
            try:
                self.tray_icon.update_menu()
            except Exception:
                pass

    def show_window_from_tray(self, icon=None, item=None):
        self.app.after(0, self.app.restore_window)

    def _tray_toggle_monitor(self, icon=None, item=None):
        self.app.after(0, self.app.toggle_monitor)

    def _tray_toggle_mini(self, icon=None, item=None):
        def _do():
            if self.app.is_mini:
                self.disable_mini_mode()
            else:
                self.app.restore_window()
                self.enable_mini_mode()
        self.app.after(0, _do)

    def _tray_toggle_lock(self, icon=None, item=None):
        self.app.after(0, self.toggle_click_through)

    def _tray_quit(self, icon=None, item=None):
        self.app.after(0, self.app.quit_window)

    def stop_tray(self):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

    # ================= رابط کاربری مینی‌مود =================
    def _build_mini_ui(self):
        app = self.app
        T = app.T
        self.mini_container = ctk.CTkFrame(app, corner_radius=0, border_width=1, fg_color=T["card"])

        # --- نمای کارت مینی ---
        self.mini_card_view = ctk.CTkFrame(self.mini_container, fg_color=T["card"], corner_radius=0)
        self.mini_header = ctk.CTkFrame(self.mini_card_view, height=28, corner_radius=6, bg_color=T["card"])
        self.mini_header.pack(fill="x", padx=6, pady=(6, 2))
        self.mini_header.pack_propagate(False)

        self.lbl_mini_drag = ctk.CTkLabel(self.mini_header, text="  DRAG / DBL-CLICK", font=("Consolas", 9, "bold"))
        self.lbl_mini_drag.pack(side="left", pady=2)

        self.btn_lock_card = ctk.CTkButton(
            self.mini_header, text="", image=self.icon_lock_off, width=26, height=20, corner_radius=5,
            command=self.toggle_click_through, fg_color="transparent", hover_color="#475569",
        )
        self.btn_mini_max = ctk.CTkButton(
            self.mini_header, text="MAX", width=36, height=20, corner_radius=5,
            font=("Segoe UI", 9, "bold"), command=self.disable_mini_mode,
            fg_color="transparent", hover_color="#475569",
        )
        self.btn_to_slim = ctk.CTkButton(
            self.mini_header, text="SLIM", width=38, height=20, corner_radius=5,
            font=("Segoe UI", 9, "bold"), command=self.toggle_mini_style,
            fg_color="transparent", hover_color="#475569",
        )

        self.lbl_mini_t1 = ctk.CTkLabel(self.mini_card_view, text="T1: -- ms", font=("Segoe UI", 19, "bold"))
        self.lbl_mini_t2 = ctk.CTkLabel(self.mini_card_view, text="T2: -- ms", font=("Segoe UI", 19, "bold"))
        self.lbl_mini_net = ctk.CTkLabel(self.mini_card_view, text="DL: 0K | UL: 0K", font=("Consolas", 11))
        self.lbl_mini_ip = ctk.CTkLabel(self.mini_card_view, text=f"IP: {app.current_my_ip}", font=("Consolas", 11, "bold"))

        # --- نمای افقی با ابعاد ثابت و مینیمال ---
        self.mini_slim_view = ctk.CTkFrame(self.mini_container, fg_color=T["card"], corner_radius=0)
        self.lbl_slim_t1 = ctk.CTkLabel(self.mini_slim_view, text="T1:--ms", font=("Consolas", 11, "bold"))
        self.lbl_slim_t2 = ctk.CTkLabel(self.mini_slim_view, text="| T2:--ms", font=("Consolas", 11, "bold"))
        self.lbl_slim_net = ctk.CTkLabel(self.mini_slim_view, text="| ↓0K ↑0K", font=("Consolas", 10))
        self.lbl_slim_ip = ctk.CTkLabel(self.mini_slim_view, text=self._format_slim_ip(), font=("Consolas", 10, "bold"))

        self.btn_slim_lock = ctk.CTkButton(
            self.mini_slim_view, text="", image=self.icon_lock_off, width=22, height=20, corner_radius=4,
            command=self.toggle_click_through, fg_color="transparent", hover_color="#475569",
        )
        self.btn_slim_max = ctk.CTkButton(
            self.mini_slim_view, text="MAX", width=30, height=20, corner_radius=4,
            font=("Segoe UI", 8, "bold"), command=self.disable_mini_mode,
            fg_color="transparent", hover_color="#475569",
        )
        self.btn_slim_card = ctk.CTkButton(
            self.mini_slim_view, text="CARD", width=34, height=20, corner_radius=4,
            font=("Segoe UI", 8, "bold"), command=self.toggle_mini_style,
            fg_color="transparent", hover_color="#475569",
        )

        drag_widgets = (
            self.mini_container, self.mini_card_view, self.mini_header, self.lbl_mini_drag,
            self.lbl_mini_t1, self.lbl_mini_t2, self.lbl_mini_ip, self.lbl_mini_net,
            self.mini_slim_view, self.lbl_slim_t1, self.lbl_slim_t2, self.lbl_slim_net, self.lbl_slim_ip,
        )
        for widget in drag_widgets:
            widget.bind("<ButtonPress-1>", self._start_move)
            widget.bind("<B1-Motion>", self._do_move)
            widget.bind("<ButtonRelease-1>", self._end_move)
            widget.bind("<Double-Button-1>", lambda e: self.disable_mini_mode())

    def apply_theme(self, T):
        self._build_lock_icons(T)
        cur_lock_img = self.icon_lock_on if self.is_click_through else self.icon_lock_off

        border_c = COLOR_ORANGE if self.is_click_through else T["border"]
        self.mini_container.configure(fg_color=T["card"], border_color=border_c)
        self.mini_card_view.configure(fg_color=T["card"])
        self.mini_slim_view.configure(fg_color=T["card"])
        self.mini_header.configure(fg_color=T["card_elev"], bg_color=T["card"])

        self.btn_mini_max.configure(bg_color=T["card_elev"], text_color=T["text"], hover_color=T["border"])
        self.btn_to_slim.configure(bg_color=T["card_elev"], text_color=T["text"], hover_color=T["border"])
        self.btn_lock_card.configure(bg_color=T["card_elev"], hover_color=T["border"], image=cur_lock_img)

        self.btn_slim_max.configure(bg_color=T["card"], text_color=T["text"], hover_color=T["card_elev"])
        self.btn_slim_card.configure(bg_color=T["card"], text_color=T["text"], hover_color=T["card_elev"])
        self.btn_slim_lock.configure(bg_color=T["card"], hover_color=T["card_elev"], image=cur_lock_img)

        if not self.is_click_through:
            self.lbl_mini_drag.configure(text_color=T["muted"], bg_color=T["card_elev"])
        else:
            self.lbl_mini_drag.configure(bg_color=T["card_elev"])

        self.lbl_mini_net.configure(text_color=T["muted"], bg_color=T["card"])
        self.lbl_mini_ip.configure(text_color=T["text"], bg_color=T["card"])
        self.lbl_slim_net.configure(text_color=T["muted"], bg_color=T["card"])
        self.lbl_slim_ip.configure(text_color=T["accent1"], bg_color=T["card"])

        if not self.app.is_running:
            self.lbl_mini_t1.configure(text_color=T["text"], bg_color=T["card"])
            self.lbl_mini_t2.configure(text_color=T["text"], bg_color=T["card"])
            self.lbl_slim_t1.configure(text_color=T["text"], bg_color=T["card"])
            self.lbl_slim_t2.configure(text_color=T["text"], bg_color=T["card"])
        else:
            self.lbl_mini_t1.configure(bg_color=T["card"])
            self.lbl_mini_t2.configure(bg_color=T["card"])
            self.lbl_slim_t1.configure(bg_color=T["card"])
            self.lbl_slim_t2.configure(bg_color=T["card"])

    # ================= قفل هوشمند Click-Through (بدون تغییر سایز پنجره) =================
    def toggle_click_through(self):
        self.set_click_through(not self.is_click_through)

    def _is_pointer_over_lock_btn(self):
        btn = self.btn_slim_lock if self.app.mini_style == "slim" else self.btn_lock_card
        if not btn.winfo_ismapped():
            return False
        try:
            px, py = self.app.winfo_pointerx(), self.app.winfo_pointery()
            bx = btn.winfo_rootx() - 3
            by = btn.winfo_rooty() - 3
            bw = btn.winfo_width() + 6
            bh = btn.winfo_height() + 6
            return (bx <= px <= bx + bw) and (by <= py <= by + bh)
        except Exception:
            return False

    def _sync_control_buttons(self):
        """مخفی یا نمایش دادن دکمه‌های CARD/MAX بدون کوچک یا بزرگ شدن کادر"""
        if self.app.mini_style == "slim":
            for w in (self.btn_slim_lock, self.btn_slim_max, self.btn_slim_card):
                w.pack_forget()
            self.btn_slim_lock.pack(side="right", padx=(2, 0))
            if not self.is_click_through:
                self.btn_slim_max.pack(side="right", padx=1)
                self.btn_slim_card.pack(side="right", padx=1)
        else:
            for w in (self.btn_lock_card, self.btn_mini_max, self.btn_to_slim):
                w.pack_forget()
            self.btn_lock_card.pack(side="right", padx=(2, 4), pady=4)
            if not self.is_click_through:
                self.btn_mini_max.pack(side="right", padx=1, pady=4)
                self.btn_to_slim.pack(side="right", padx=1, pady=4)

    def set_click_through(self, enable):
        if not self.app.is_mini:
            enable = False
        self.is_click_through = bool(enable)

        if self.is_click_through:
            self.mini_container.configure(border_color=COLOR_ORANGE)
            self.lbl_mini_drag.configure(text="  LOCKED", text_color=COLOR_ORANGE)
            self.btn_slim_lock.configure(image=self.icon_lock_on, fg_color="transparent")
            self.btn_lock_card.configure(image=self.icon_lock_on, fg_color="transparent")
            if self.app.is_mini:
                self._sync_control_buttons()

            self.app.update_idletasks()
            if self._is_pointer_over_lock_btn():
                set_window_click_through(self.app, False)
                self._os_passthrough_active = False
            else:
                set_window_click_through(self.app, True)
                self._os_passthrough_active = True

            self._poll_active = True
            self._poll_locked_state()
        else:
            self._poll_active = False
            self._os_passthrough_active = False
            set_window_click_through(self.app, False)
            self.mini_container.configure(border_color=self.app.T["border"])
            self.lbl_mini_drag.configure(text="  DRAG / DBL-CLICK", text_color=self.app.T["muted"])
            self.btn_slim_lock.configure(image=self.icon_lock_off, fg_color="transparent")
            self.btn_lock_card.configure(image=self.icon_lock_off, fg_color="transparent")
            if self.app.is_mini:
                self._sync_control_buttons()

        self.refresh_tray_menu()
        self.update_tray_tooltip()

    def _poll_locked_state(self):
        if not self.app.app_alive or not self.is_click_through or not self._poll_active:
            return

        if is_unlock_hotkey_pressed():
            self.set_click_through(False)
            self.app.sound.play("restored")
            return

        over_lock = self._is_pointer_over_lock_btn()
        btn = self.btn_slim_lock if self.app.mini_style == "slim" else self.btn_lock_card

        if over_lock and self._os_passthrough_active:
            set_window_click_through(self.app, False)
            self._os_passthrough_active = False
            btn.configure(fg_color=self.app.T["card_elev"])
        elif not over_lock and not self._os_passthrough_active:
            set_window_click_through(self.app, True)
            self._os_passthrough_active = True
            btn.configure(fg_color="transparent")

        self.app.after(70, self._poll_locked_state)

    # ================= جابجایی، ورود و خروج تمیز مینی‌مود =================
    def _start_move(self, event):
        if self.is_click_through:
            return
        self.click_x = event.x
        self.click_y = event.y

    def _do_move(self, event):
        if self.is_click_through:
            return
        x = self.app.winfo_x() - self.click_x + event.x
        y = self.app.winfo_y() - self.click_y + event.y
        self.app.geometry(f"+{x}+{y}")

    def _end_move(self, event):
        if self.app.is_mini and not self.is_click_through:
            self.app.mini_pos = [self.app.winfo_x(), self.app.winfo_y()]
            self.app.save_config()

    def toggle_mini_style(self):
        self.app.mini_style = "slim" if self.app.mini_style == "card" else "card"
        self.app.save_config()
        if self.app.is_mini:
            self.layout_mini_mode()

    def layout_mini_mode(self):
        self.mini_card_view.pack_forget()
        self.mini_slim_view.pack_forget()

        if self.app.mini_style == "slim":
            self.mini_slim_view.pack(fill="both", expand=True, padx=6, pady=2)
            for w in (self.lbl_slim_t1, self.lbl_slim_t2, self.lbl_slim_net, self.lbl_slim_ip):
                w.pack_forget()

            self.lbl_slim_ip.configure(text=self._format_slim_ip(offline=(self.app.current_my_ip == "OFFLINE")))
            self.lbl_slim_t1.pack(side="left", padx=(2, 3))
            if self.app.num_targets == 2:
                self.lbl_slim_t2.pack(side="left", padx=(0, 3))
            self.lbl_slim_net.pack(side="left", padx=(1, 4))
            self.lbl_slim_ip.pack(side="left", padx=(0, 4))

            self._sync_control_buttons()
            size_str = f"{self._fixed_slim_width()}x28"
        else:
            self.mini_card_view.pack(fill="both", expand=True)
            self._sync_control_buttons()

            self.lbl_mini_t1.pack_forget()
            self.lbl_mini_t2.pack_forget()
            self.lbl_mini_net.pack_forget()
            self.lbl_mini_ip.pack_forget()

            self.lbl_mini_t1.pack(pady=(10, 4))
            if self.app.num_targets == 2:
                self.lbl_mini_t2.pack(pady=(0, 8))
                size_str = "270x174"
            else:
                size_str = "270x138"
            self.lbl_mini_net.pack(side="bottom", pady=(0, 6))
            self.lbl_mini_ip.pack(side="bottom", pady=(0, 2))

        pos_suffix = ""
        if self.app.mini_pos and len(self.app.mini_pos) == 2:
            sw = self.app.winfo_screenwidth()
            sh = self.app.winfo_screenheight()
            mx = max(0, min(int(self.app.mini_pos[0]), sw - 160))
            my = max(0, min(int(self.app.mini_pos[1]), sh - 60))
            pos_suffix = f"+{mx}+{my}"

        self.app.geometry(f"{size_str}{pos_suffix}")
        self.update_idle_labels()

    def enable_mini_mode(self):
        app = self.app
        app.is_mini = True
        app.main_container.pack_forget()
        self.mini_container.pack(fill="both", expand=True)
        app.overrideredirect(True)
        app.attributes("-topmost", True)
        app.attributes("-alpha", app.mini_opacity)
        self.layout_mini_mode()
        self.refresh_tray_menu()

    def disable_mini_mode(self):
        app = self.app
        if not app.is_mini:
            return

        try:
            app.mini_pos = [app.winfo_x(), app.winfo_y()]
            app.save_config()
        except Exception:
            pass

        if self.is_click_through:
            self.set_click_through(False)

        app.is_mini = False
        app.withdraw()
        self.mini_container.pack_forget()
        app.main_container.pack(fill="both", expand=True)
        app.overrideredirect(False)
        app.attributes("-alpha", 1.0)
        app.attributes("-topmost", app.is_pinned)
        app.update_idletasks()
        app.center_window(1000, 860)
        app.deiconify()
        app.lift()
        app.focus_force()
        app.after(20, lambda: app.center_window(1000, 860))
        self.refresh_tray_menu()

    # ================= آپدیت لیبل‌های زنده مینی‌مود و Tooltip =================
    def update_idle_labels(self):
        if not self.app.is_running:
            t1_txt = self.app.tab_ping_view.lbl_t1_ping.cget("text").replace(" ", "")
            t2_txt = self.app.tab_ping_view.lbl_t2_ping.cget("text").replace(" ", "")
            self.lbl_mini_t1.configure(text=f"T1: {self.app.tab_ping_view.lbl_t1_ping.cget('text')}")
            self.lbl_slim_t1.configure(text=f"T1:{t1_txt}")
            if self.app.num_targets == 2:
                self.lbl_mini_t2.configure(text=f"T2: {self.app.tab_ping_view.lbl_t2_ping.cget('text')}")
                self.lbl_slim_t2.configure(text=f"| T2:{t2_txt}")

    def update_ping_values(self, p1, c1, p2=None, c2=None):
        if p1 != -1:
            self.live_ping_t1 = f"{p1}ms"
            self.lbl_mini_t1.configure(text=f"T1: {p1} ms", text_color=c1)
            self.lbl_slim_t1.configure(text=f"T1:{p1}ms", text_color=c1)
        else:
            self.live_ping_t1 = "ERR"
            self.lbl_mini_t1.configure(text="T1: TIMEOUT", text_color=c1)
            self.lbl_slim_t1.configure(text="T1:ERR", text_color=c1)

        if self.app.num_targets == 2 and p2 is not None:
            if p2 != -1:
                self.live_ping_t2 = f"{p2}ms"
                self.lbl_mini_t2.configure(text=f"T2: {p2} ms", text_color=c2)
                self.lbl_slim_t2.configure(text=f"| T2:{p2}ms", text_color=c2)
            else:
                self.live_ping_t2 = "ERR"
                self.lbl_mini_t2.configure(text="T2: TIMEOUT", text_color=c2)
                self.lbl_slim_t2.configure(text="| T2:ERR", text_color=c2)

        self.update_tray_tooltip()

    def update_network_speed(self, dl, ul):
        self.live_dl = f"{dl:.0f}K" if dl < 1024 else f"{dl / 1024:.1f}M"
        self.live_ul = f"{ul:.0f}K" if ul < 1024 else f"{ul / 1024:.1f}M"
        self.lbl_mini_net.configure(text=f"DL:{self.live_dl} | UL:{self.live_ul}")
        self.lbl_slim_net.configure(text=f"| ↓{self.live_dl} ↑{self.live_ul}")
        self.update_tray_tooltip()

    def update_ip_display(self, mini_text, cc_short, highlight=False, offline=False):
        self.live_cc = "OFF" if offline else cc_short
        slim_txt = self._format_slim_ip(offline=offline)

        if offline:
            self.lbl_mini_ip.configure(text="IP: OFFLINE", text_color=COLOR_RED)
            self.lbl_slim_ip.configure(text=slim_txt, text_color=COLOR_RED)
        else:
            clr_ip = COLOR_GREEN if highlight else self.app.T["text"]
            clr_slim = COLOR_GREEN if highlight else self.app.T["accent1"]
            self.lbl_mini_ip.configure(text=mini_text, text_color=clr_ip)
            self.lbl_slim_ip.configure(text=slim_txt, text_color=clr_slim)
            if highlight:
                self.app.after(1000, lambda: self.lbl_mini_ip.configure(text_color=self.app.T["text"]))
                self.app.after(1000, lambda: self.lbl_slim_ip.configure(text_color=self.app.T["accent1"]))

        self.update_tray_tooltip()