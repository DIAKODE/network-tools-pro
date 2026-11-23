import threading
from datetime import datetime
import customtkinter as ctk

from core.config import COLOR_GREEN, COLOR_ORANGE, COLOR_RED
from core.net_engine import scan_lan_devices
from core.win_audio import show_os_notification
from ui.settings_win import open_rename_device_modal


class LanTabView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=app.T["bg"], corner_radius=0)
        self.app = app

        self.scanning = False
        self.auto_scan = False
        self.known_macs = set()
        self.last_devices = []
        self.subnet_str = "--"
        self.last_scan_time = "--"
        self.initialized = False

        self._build_ui()

    def _build_ui(self):
        T = self.app.T
        self.lan_top_bar = ctk.CTkFrame(self, corner_radius=12, border_width=1, bg_color=T["bg"])
        self.lan_top_bar.pack(fill="x", pady=(0, 8))

        self.lbl_lan_info = ctk.CTkLabel(self.lan_top_bar, text="LOCAL NETWORK (LAN)  •  Click 'SCAN NETWORK' to list connected Wi-Fi / LAN devices", font=("Consolas", 11, "bold"))
        self.lbl_lan_info.pack(side="left", padx=14, pady=12)

        self.btn_scan_lan = ctk.CTkButton(
            self.lan_top_bar, text="SCAN NETWORK", width=132, height=32, corner_radius=8,
            font=("Segoe UI", 11, "bold"), fg_color=COLOR_ORANGE, text_color="#000000",
            hover_color="#EA580C", command=self.start_scan,
        )
        self.btn_scan_lan.pack(side="right", padx=(6, 12), pady=9)

        self.lan_auto_var = ctk.BooleanVar(value=False)
        self.sw_lan_auto = ctk.CTkSwitch(
            self.lan_top_bar, text="Auto (30s)", variable=self.lan_auto_var,
            font=("Segoe UI", 11, "bold"), progress_color=COLOR_ORANGE, command=self.toggle_auto_scan,
        )
        self.sw_lan_auto.pack(side="right", padx=8, pady=9)

        self.lan_col_header = ctk.CTkFrame(self, corner_radius=9, border_width=1, height=32, bg_color=T["bg"])
        self.lan_col_header.pack(fill="x", pady=(0, 6))
        self.lan_col_header.pack_propagate(False)

        self.header_labels = []
        cols = [("STATUS", 76, (14, 4)), ("IP ADDRESS", 124, 4), ("DEVICE NAME / HOST", 205, 4), ("VENDOR / TYPE", 155, 4), ("MAC ADDRESS", 142, 4)]
        for text, width, padx in cols:
            lbl = ctk.CTkLabel(self.lan_col_header, text=text, width=width, anchor="w", font=("Consolas", 10, "bold"))
            lbl.pack(side="left", padx=padx)
            self.header_labels.append(lbl)

        self.lan_scroll = ctk.CTkScrollableFrame(self, corner_radius=12, border_width=1, bg_color=T["bg"])
        self.lan_scroll.pack(fill="both", expand=True)
        self.render_placeholder("Click 'SCAN NETWORK' to discover all phones, PCs, TVs & consoles on your Wi-Fi / LAN.")

    def apply_theme(self, T):
        self.configure(fg_color=T["bg"])
        self.lan_top_bar.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"])
        self.lbl_lan_info.configure(text_color=T["accent1"], bg_color=T["card"])
        self.btn_scan_lan.configure(bg_color=T["card"])
        self.sw_lan_auto.configure(text_color=T["text"], bg_color=T["card"])
        self.lan_col_header.configure(fg_color=T["card_elev"], border_color=T["border"], bg_color=T["bg"])
        for lbl in self.header_labels:
            lbl.configure(text_color=T["muted"], bg_color=T["card_elev"])
        self.lan_scroll.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"], scrollbar_button_color=T["border"], scrollbar_button_hover_color=T["muted"])
        if not self.scanning:
            if self.last_devices:
                self.render_devices(self.last_devices)
            else:
                self.render_placeholder("Click 'SCAN NETWORK' to discover all phones, PCs, TVs & consoles on your Wi-Fi / LAN.")

    def render_placeholder(self, text):
        for w in self.lan_scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.lan_scroll, text=text, font=("Consolas", 12), text_color=self.app.T["muted"], bg_color=self.app.T["card"]).pack(pady=45)

    def on_tab_selected(self):
        if not self.initialized and not self.scanning:
            self.app.after(100, self.start_scan)

    def toggle_auto_scan(self):
        self.auto_scan = self.lan_auto_var.get()
        if self.auto_scan:
            self._schedule_auto_scan()

    def _schedule_auto_scan(self):
        if not self.app.app_alive or not self.auto_scan:
            return
        if not self.scanning:
            self.start_scan(silent=True)
        self.app.after(30000, self._schedule_auto_scan)

    def start_scan(self, silent=False):
        if self.scanning:
            return
        self.scanning = True
        self.btn_scan_lan.configure(state="disabled", text="SCANNING...")
        if not silent and not self.last_devices:
            self.render_placeholder("Scanning local Wi-Fi / LAN subnet... (takes ~2-3 seconds)")
        self.lbl_lan_info.configure(text="LOCAL NETWORK (LAN)  •  Scanning active devices on your router...")
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        res = scan_lan_devices(self.app.lan_names, self.known_macs, is_first_scan=not self.initialized)
        self.subnet_str = res["subnet"]
        self.known_macs.update(res["found_macs"])
        self.initialized = True
        self.last_scan_time = datetime.now().strftime("%H:%M:%S")
        self.last_devices = res["devices"]

        if self.app.app_alive:
            self.app.after(0, self._finish_scan, res["devices"], res["new_unknown"])

    def _finish_scan(self, devices, new_unknown):
        self.scanning = False
        self.btn_scan_lan.configure(state="normal", text="SCAN NETWORK")
        self.lbl_lan_info.configure(
            text=f"SUBNET: {self.subnet_str}   •   CONNECTED: {len(devices)} DEVICES   •   LAST SCAN: {self.last_scan_time}"
        )
        self.render_devices(devices)

        if new_unknown:
            ip, _, vnd = new_unknown[0]
            extra = f" (+{len(new_unknown) - 1} more)" if len(new_unknown) > 1 else ""
            show_os_notification("New Wi-Fi / LAN Device", f"{ip} ({vnd}){extra} joined your network!")
            self.app.sound.play("warn")

    def render_devices(self, devices):
        for w in self.lan_scroll.winfo_children():
            w.destroy()
        if not devices:
            self.render_placeholder("No devices found. Check your Wi-Fi / Ethernet connection and scan again.")
            return

        T = self.app.T
        for dev in devices:
            tag = dev["tag"]
            if tag == "ROUTER":
                badge_bg, badge_fg, row_border = T["accent1"], ("#000000" if T["mode"] == "Dark" else "#FFFFFF"), T["accent1"]
            elif tag == "THIS PC":
                badge_bg, badge_fg, row_border = COLOR_GREEN, "#000000", COLOR_GREEN
            elif tag == "NEW":
                badge_bg, badge_fg, row_border = COLOR_RED, "#FFFFFF", COLOR_RED
            elif tag == "KNOWN":
                badge_bg, badge_fg, row_border = T["accent2"], "#FFFFFF", T["border"]
            else:
                badge_bg, badge_fg, row_border = T["card_elev"], T["text"], T["border"]

            row = ctk.CTkFrame(self.lan_scroll, fg_color=T["inner"], bg_color=T["card"], corner_radius=9, border_width=1.2 if tag in ("ROUTER", "THIS PC", "NEW") else 1, border_color=row_border)
            row.pack(fill="x", padx=6, pady=4)

            ctk.CTkLabel(row, text=tag, width=68, height=22, corner_radius=6, fg_color=badge_bg, bg_color=T["inner"], text_color=badge_fg, font=("Consolas", 10, "bold")).pack(side="left", padx=(10, 8), pady=8)
            ctk.CTkLabel(row, text=dev["ip"], width=124, anchor="w", font=("Consolas", 12, "bold"), text_color=T["text"], bg_color=T["inner"]).pack(side="left", padx=4)

            name_disp = dev["name"][:24] + ("…" if len(dev["name"]) > 24 else "")
            ctk.CTkLabel(row, text=name_disp, width=205, anchor="w", font=("Segoe UI", 12, "bold"), text_color=T["accent1"] if dev["custom_name"] else T["text"], bg_color=T["inner"]).pack(side="left", padx=4)

            ctk.CTkLabel(row, text=dev["vendor"][:20], width=155, anchor="w", font=("Consolas", 11), text_color=T["muted"], bg_color=T["inner"]).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=dev["mac"], width=142, anchor="w", font=("Consolas", 11), text_color=T["muted"], bg_color=T["inner"]).pack(side="left", padx=4)

            ctk.CTkButton(row, text="PING", width=56, height=26, corner_radius=7, bg_color=T["inner"], font=("Segoe UI", 10, "bold"), fg_color=T["card_elev"], text_color=T["text"], border_width=1, border_color=T["border"], command=lambda addr=dev["ip"]: self.app.apply_dns_as_t1(addr)).pack(side="right", padx=(4, 10), pady=6)
            ctk.CTkButton(row, text="NAME", width=58, height=26, corner_radius=7, bg_color=T["inner"], font=("Segoe UI", 10, "bold"), fg_color=T["border"], text_color=T["text"], command=lambda d=dev: open_rename_device_modal(self.app, d, self._on_device_renamed)).pack(side="right", padx=4, pady=6)

    def _on_device_renamed(self, mac, new_nm):
        for item in self.last_devices:
            if item["mac"] == mac:
                item["custom_name"] = new_nm
                item["name"] = new_nm or item["host"] or ("Wi-Fi Router / Modem" if item["tag"] == "ROUTER" else "Unknown Device")
                if item["tag"] not in ("ROUTER", "THIS PC"):
                    item["tag"] = "KNOWN" if new_nm else "ACTIVE"
        self.render_devices(self.last_devices)