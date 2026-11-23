import threading
import customtkinter as ctk

from core.config import COLOR_GREEN, COLOR_RED, ROUTE_CHECK_TARGETS, get_health_color, is_valid_ipv4
from core.net_engine import run_dns_benchmark, run_route_check
from core.win_audio import (
    flush_system_dns, get_active_system_dns, reset_system_dns,
    set_system_dns, show_os_notification,
)


class DnsTabView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=app.T["bg"], corner_radius=0)
        self.app = app

        self.subtab = "dns"
        self.dns_testing = False
        self.route_testing = False
        self.active_dns_ips = set()
        self.last_dns_results = None
        self.last_route_results = None

        self._build_ui()

    def _build_ui(self):
        T = self.app.T
        self.dns_mode_bar = ctk.CTkFrame(self, fg_color=T["bg"], corner_radius=0)
        self.dns_mode_bar.pack(fill="x", pady=(0, 8))

        self.btn_sub_dns = ctk.CTkButton(self.dns_mode_bar, text="DNS MANAGER", width=145, height=32, corner_radius=9, bg_color=T["bg"], font=("Segoe UI", 11, "bold"), command=lambda: self.switch_subtab("dns"))
        self.btn_sub_dns.pack(side="left", padx=(0, 6))

        self.btn_sub_routes = ctk.CTkButton(self.dns_mode_bar, text="GAME & ROUTE CHECK", width=170, height=32, corner_radius=9, bg_color=T["bg"], font=("Segoe UI", 11, "bold"), command=lambda: self.switch_subtab("routes"))
        self.btn_sub_routes.pack(side="left")

        # --- زیرتب DNS ---
        self.dns_sub_container = ctk.CTkFrame(self, fg_color=T["bg"], corner_radius=0)

        self.dns_top_bar = ctk.CTkFrame(self.dns_sub_container, corner_radius=12, border_width=1, bg_color=T["bg"])
        self.dns_top_bar.pack(fill="x", pady=(0, 8))

        self.lbl_active_dns = ctk.CTkLabel(self.dns_top_bar, text="ACTIVE SYSTEM DNS: Checking...", font=("Consolas", 12, "bold"))
        self.lbl_active_dns.pack(side="left", padx=14, pady=12)

        self.btn_run_dns = ctk.CTkButton(self.dns_top_bar, text="BENCHMARK ALL", width=132, height=32, corner_radius=8, font=("Segoe UI", 11, "bold"), command=self.start_dns_benchmark)
        self.btn_run_dns.pack(side="right", padx=(4, 12), pady=9)

        self.btn_reset_dns = ctk.CTkButton(self.dns_top_bar, text="AUTO (DHCP)", width=104, height=32, corner_radius=8, font=("Segoe UI", 11, "bold"), command=self._on_reset_dns)
        self.btn_reset_dns.pack(side="right", padx=4, pady=9)

        self.btn_flush_dns = ctk.CTkButton(self.dns_top_bar, text="FLUSH DNS", width=96, height=32, corner_radius=8, font=("Segoe UI", 11, "bold"), command=self._on_flush_dns)
        self.btn_flush_dns.pack(side="right", padx=4, pady=9)

        self.dns_add_bar = ctk.CTkFrame(self.dns_sub_container, corner_radius=12, border_width=1, bg_color=T["bg"])
        self.dns_add_bar.pack(fill="x", pady=(0, 8))

        self.entry_dns_name = ctk.CTkEntry(self.dns_add_bar, placeholder_text="Name (e.g. Gaming)", width=185, height=32, corner_radius=8)
        self.entry_dns_name.pack(side="left", padx=(12, 6), pady=8)

        self.entry_dns_ip = ctk.CTkEntry(self.dns_add_bar, placeholder_text="Primary (1.1.1.1)", width=170, height=32, corner_radius=8)
        self.entry_dns_ip.pack(side="left", padx=6, pady=8)

        self.entry_dns_ip2 = ctk.CTkEntry(self.dns_add_bar, placeholder_text="Secondary (1.0.0.1)", width=170, height=32, corner_radius=8)
        self.entry_dns_ip2.pack(side="left", padx=6, pady=8)

        self.btn_add_dns = ctk.CTkButton(self.dns_add_bar, text="+ ADD DNS", width=114, height=32, corner_radius=8, font=("Segoe UI", 11, "bold"), fg_color=COLOR_GREEN, text_color="#000000", hover_color="#059669", command=self.add_custom_dns)
        self.btn_add_dns.pack(side="left", padx=8, pady=8)

        self.dns_scroll = ctk.CTkScrollableFrame(self.dns_sub_container, corner_radius=12, border_width=1, bg_color=T["bg"])
        self.dns_scroll.pack(fill="both", expand=True)

        # --- زیرتب Route Check ---
        self.route_sub_container = ctk.CTkFrame(self, fg_color=T["bg"], corner_radius=0)

        self.route_top_bar = ctk.CTkFrame(self.route_sub_container, corner_radius=12, border_width=1, bg_color=T["bg"])
        self.route_top_bar.pack(fill="x", pady=(0, 8))
        self.lbl_route_info = ctk.CTkLabel(self.route_top_bar, text="QUICK ROUTE CHECK  •  GAME, CLOUD & SERVICE LATENCY", font=("Consolas", 12, "bold"))
        self.lbl_route_info.pack(side="left", padx=14, pady=12)
        self.btn_run_routes = ctk.CTkButton(self.route_top_bar, text="CHECK ALL ROUTES", width=148, height=32, corner_radius=8, font=("Segoe UI", 11, "bold"), command=self.start_route_check)
        self.btn_run_routes.pack(side="right", padx=12, pady=9)

        self.route_scroll = ctk.CTkScrollableFrame(self.route_sub_container, corner_radius=12, border_width=1, bg_color=T["bg"])
        self.route_scroll.pack(fill="both", expand=True)

    def apply_theme(self, T):
        self.configure(fg_color=T["bg"])
        self.dns_mode_bar.configure(fg_color=T["bg"])
        self.dns_sub_container.configure(fg_color=T["bg"])
        self.route_sub_container.configure(fg_color=T["bg"])
        self.btn_sub_dns.configure(bg_color=T["bg"])
        self.btn_sub_routes.configure(bg_color=T["bg"])

        self.dns_top_bar.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"])
        self.lbl_active_dns.configure(text_color=T["accent1"], bg_color=T["card"])
        self.btn_run_dns.configure(fg_color=T["accent2"], bg_color=T["card"], text_color="#FFFFFF")
        self.btn_reset_dns.configure(fg_color=T["card_elev"], bg_color=T["card"], text_color=T["text"], border_width=1, border_color=T["border"])
        self.btn_flush_dns.configure(fg_color=T["card_elev"], bg_color=T["card"], text_color=T["text"], border_width=1, border_color=T["border"])

        self.dns_add_bar.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"])
        self.entry_dns_name.configure(fg_color=T["inner"], bg_color=T["card"], border_color=T["border"], text_color=T["text"])
        self.entry_dns_ip.configure(fg_color=T["inner"], bg_color=T["card"], border_color=T["border"], text_color=T["text"])
        self.entry_dns_ip2.configure(fg_color=T["inner"], bg_color=T["card"], border_color=T["border"], text_color=T["text"])
        self.btn_add_dns.configure(bg_color=T["card"])
        self.dns_scroll.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"], scrollbar_button_color=T["border"], scrollbar_button_hover_color=T["muted"])

        self.route_top_bar.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"])
        self.lbl_route_info.configure(text_color=T["accent1"], bg_color=T["card"])
        self.btn_run_routes.configure(fg_color=T["accent1"], bg_color=T["card"], text_color="#000000" if T["mode"] == "Dark" else "#FFFFFF")
        self.route_scroll.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"], scrollbar_button_color=T["border"], scrollbar_button_hover_color=T["muted"])

        self.switch_subtab(self.subtab)
        if not self.dns_testing:
            if self.last_dns_results:
                self._render_dns_results(self.last_dns_results)
            else:
                self.render_dns_list_initial()
        if not self.route_testing:
            if self.last_route_results:
                self._render_route_results(self.last_route_results)
            else:
                self.render_route_list_initial()

    def switch_subtab(self, sub):
        self.subtab = sub
        T = self.app.T
        self.dns_sub_container.pack_forget()
        self.route_sub_container.pack_forget()

        if sub == "dns":
            self.btn_sub_dns.configure(fg_color=T["accent2"], text_color="#FFFFFF", hover_color=T["accent2"])
            self.btn_sub_routes.configure(fg_color=T["card"], text_color=T["muted"], hover_color=T["border"])
            self.dns_sub_container.pack(fill="both", expand=True)
        else:
            self.btn_sub_dns.configure(fg_color=T["card"], text_color=T["muted"], hover_color=T["border"])
            self.btn_sub_routes.configure(fg_color=T["accent1"], text_color="#000000" if T["mode"] == "Dark" else "#FFFFFF", hover_color=T["accent1"])
            self.route_sub_container.pack(fill="both", expand=True)

    # ================= اکشن‌های DNS سیستم =================
    def refresh_active_dns(self):
        active_ips, txt = get_active_system_dns()
        self.active_dns_ips = active_ips

        def _update_ui():
            self.lbl_active_dns.configure(text=txt)
            if not self.dns_testing:
                if self.last_dns_results:
                    self._render_dns_results(self.last_dns_results)
                else:
                    self.render_dns_list_initial()

        if self.app.app_alive:
            self.app.after(0, _update_ui)

    def _on_set_dns(self, ip, ip2, name):
        if set_system_dns(ip, ip2):
            disp = f"{ip} / {ip2}" if ip2 else ip
            show_os_notification("DNS Applied", f"Setting DNS to {name} ({disp})...")
            self.app.after(2500, lambda: threading.Thread(target=self.refresh_active_dns, daemon=True).start())
        else:
            show_os_notification("Error", "Could not request Admin privileges.")

    def _on_reset_dns(self):
        if reset_system_dns():
            show_os_notification("DNS Reset", "Restoring automatic DHCP DNS...")
            self.app.after(2500, lambda: threading.Thread(target=self.refresh_active_dns, daemon=True).start())

    def _on_flush_dns(self):
        if flush_system_dns():
            show_os_notification("DNS Flushed", "Windows DNS cache cleared successfully.")

    def add_custom_dns(self):
        name = self.entry_dns_name.get().strip() or "Custom DNS"
        ip = self.entry_dns_ip.get().strip()
        ip2 = self.entry_dns_ip2.get().strip()

        if not is_valid_ipv4(ip):
            self.entry_dns_ip.configure(border_color=COLOR_RED)
            self.app.after(1200, lambda: self.entry_dns_ip.configure(border_color=self.app.T["border"]))
            return
        if ip2 and not is_valid_ipv4(ip2):
            self.entry_dns_ip2.configure(border_color=COLOR_RED)
            self.app.after(1200, lambda: self.entry_dns_ip2.configure(border_color=self.app.T["border"]))
            return

        existing = next((d for d in self.app.dns_servers if d["ip"] == ip), None)
        if existing:
            existing["name"] = name
            existing["ip2"] = ip2
        else:
            self.app.dns_servers.append({"name": name, "ip": ip, "ip2": ip2, "custom": True})
        self.last_dns_results = None
        self.app.save_config()

        self.entry_dns_name.delete(0, "end")
        self.entry_dns_ip.delete(0, "end")
        self.entry_dns_ip2.delete(0, "end")
        self.render_dns_list_initial()

    def remove_custom_dns(self, ip):
        self.app.dns_servers = [d for d in self.app.dns_servers if d["ip"] != ip]
        self.last_dns_results = None
        self.app.save_config()
        self.render_dns_list_initial()

    def render_dns_list_initial(self):
        for w in self.dns_scroll.winfo_children():
            w.destroy()
        T = self.app.T
        for item in self.app.dns_servers:
            ip1 = item["ip"]
            ip2 = item.get("ip2", "")
            ip_display = f"{ip1}  /  {ip2}" if ip2 else ip1
            is_active = ip1 in self.active_dns_ips

            row = ctk.CTkFrame(self.dns_scroll, fg_color=T["inner"], bg_color=T["card"], corner_radius=9, border_width=1.5 if is_active else 1, border_color=COLOR_GREEN if is_active else T["border"])
            row.pack(fill="x", padx=6, pady=4)
            ctk.CTkLabel(row, text=item["name"], width=120, anchor="w", font=("Segoe UI", 13, "bold"), text_color=T["text"], bg_color=T["inner"]).pack(side="left", padx=(14, 4), pady=8)
            ctk.CTkLabel(row, text=ip_display, width=235, anchor="w", font=("Consolas", 11), text_color=T["muted"], bg_color=T["inner"]).pack(side="left", padx=4)

            if is_active:
                ctk.CTkLabel(row, text="ACTIVE", width=62, height=22, corner_radius=6, fg_color=COLOR_GREEN, bg_color=T["inner"], text_color="#000000", font=("Consolas", 10, "bold")).pack(side="left", padx=6)
            else:
                ctk.CTkLabel(row, text="Ready", width=62, font=("Consolas", 11), text_color=T["muted"], bg_color=T["inner"]).pack(side="left", padx=6)

            if item.get("custom"):
                ctk.CTkButton(row, text="X", width=28, height=26, corner_radius=7, bg_color=T["inner"], font=("Segoe UI", 11, "bold"), fg_color="#7F1D1D", hover_color=COLOR_RED, command=lambda addr=ip1: self.remove_custom_dns(addr)).pack(side="right", padx=(4, 10), pady=6)
            ctk.CTkButton(row, text="SET DNS", width=78, height=26, corner_radius=7, bg_color=T["inner"], font=("Segoe UI", 11, "bold"), fg_color=COLOR_GREEN, text_color="#000000", hover_color="#059669", command=lambda a1=ip1, a2=ip2, nm=item["name"]: self._on_set_dns(a1, a2, nm)).pack(side="right", padx=(4, 10 if not item.get("custom") else 4), pady=6)
            ctk.CTkButton(row, text="SET T1", width=66, height=26, corner_radius=7, bg_color=T["inner"], font=("Segoe UI", 11, "bold"), fg_color=T["card_elev"], text_color=T["text"], border_width=1, border_color=T["border"], command=lambda addr=ip1: self.app.apply_dns_as_t1(addr)).pack(side="right", padx=4, pady=6)

    def start_dns_benchmark(self):
        if self.dns_testing:
            return
        self.dns_testing = True
        self.btn_run_dns.configure(state="disabled", text="TESTING...")
        for w in self.dns_scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.dns_scroll, text=f"Benchmarking {len(self.app.dns_servers)} DNS servers in parallel...", font=("Consolas", 12), text_color=self.app.T["accent1"], bg_color=self.app.T["card"]).pack(pady=40)
        threading.Thread(target=self._dns_worker, daemon=True).start()

    def _dns_worker(self):
        results = run_dns_benchmark(list(self.app.dns_servers))
        self.last_dns_results = results
        if self.app.app_alive:
            self.app.after(0, self._render_dns_results, results)

    def _render_dns_results(self, results):
        self.dns_testing = False
        self.btn_run_dns.configure(state="normal", text="BENCHMARK ALL")
        for w in self.dns_scroll.winfo_children():
            w.destroy()

        T = self.app.T
        for idx, (item, avg, loss) in enumerate(results, start=1):
            ip1 = item["ip"]
            ip2 = item.get("ip2", "")
            ip_display = f"{ip1} / {ip2}" if ip2 else ip1
            is_active = ip1 in self.active_dns_ips

            border_c = COLOR_GREEN if (is_active or (idx == 1 and loss < 100)) else T["border"]
            row = ctk.CTkFrame(self.dns_scroll, fg_color=T["inner"], bg_color=T["card"], corner_radius=9, border_width=1.5 if is_active else 1, border_color=border_c)
            row.pack(fill="x", padx=6, pady=4)

            rank_color = COLOR_GREEN if idx == 1 else (T["accent1"] if idx <= 3 else T["muted"])
            ctk.CTkLabel(row, text=f"#{idx}", width=28, font=("Consolas", 13, "bold"), text_color=rank_color, bg_color=T["inner"]).pack(side="left", padx=(10, 4), pady=8)
            ctk.CTkLabel(row, text=item["name"], width=106, anchor="w", font=("Segoe UI", 12, "bold"), text_color=T["text"], bg_color=T["inner"]).pack(side="left", padx=2)
            ctk.CTkLabel(row, text=ip_display, width=220, anchor="w", font=("Consolas", 11), text_color=T["muted"], bg_color=T["inner"]).pack(side="left", padx=2)

            ping_txt = f"{avg} ms" if avg != 9999 else "TIMEOUT"
            ping_clr = get_health_color(-1 if avg == 9999 else avg)
            ctk.CTkLabel(row, text=ping_txt, width=74, font=("Consolas", 12, "bold"), text_color=ping_clr, bg_color=T["inner"]).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f"L:{loss}%", width=48, font=("Consolas", 11), text_color=COLOR_RED if loss > 0 else T["muted"], bg_color=T["inner"]).pack(side="left", padx=2)

            if is_active:
                ctk.CTkLabel(row, text="ACTIVE", width=56, height=20, corner_radius=6, fg_color=COLOR_GREEN, bg_color=T["inner"], text_color="#000000", font=("Consolas", 9, "bold")).pack(side="left", padx=4)

            if item.get("custom"):
                ctk.CTkButton(row, text="X", width=28, height=26, corner_radius=7, bg_color=T["inner"], font=("Segoe UI", 11, "bold"), fg_color="#7F1D1D", hover_color=COLOR_RED, command=lambda addr=ip1: self.remove_custom_dns(addr)).pack(side="right", padx=(4, 10), pady=6)
            ctk.CTkButton(row, text="SET DNS", width=76, height=26, corner_radius=7, bg_color=T["inner"], font=("Segoe UI", 11, "bold"), fg_color=COLOR_GREEN, text_color="#000000", hover_color="#059669", command=lambda a1=ip1, a2=ip2, nm=item["name"]: self._on_set_dns(a1, a2, nm)).pack(side="right", padx=(4, 10 if not item.get("custom") else 4), pady=6)
            ctk.CTkButton(row, text="SET T1", width=64, height=26, corner_radius=7, bg_color=T["inner"], font=("Segoe UI", 11, "bold"), fg_color=T["card_elev"], text_color=T["text"], border_width=1, border_color=T["border"], command=lambda addr=ip1: self.app.apply_dns_as_t1(addr)).pack(side="right", padx=4, pady=6)

    # ================= تست مسیر سرورهای گیم و سرویس‌ها =================
    def render_route_list_initial(self):
        for w in self.route_scroll.winfo_children():
            w.destroy()
        T = self.app.T
        for item in ROUTE_CHECK_TARGETS:
            row = ctk.CTkFrame(self.route_scroll, fg_color=T["inner"], bg_color=T["card"], corner_radius=9, border_width=1, border_color=T["border"])
            row.pack(fill="x", padx=6, pady=4)
            ctk.CTkLabel(row, text=item["cat"], width=68, height=22, corner_radius=6, fg_color=T["card_elev"], bg_color=T["inner"], text_color=T["accent1"], font=("Consolas", 10, "bold")).pack(side="left", padx=(10, 8), pady=8)
            ctk.CTkLabel(row, text=item["name"], width=155, anchor="w", font=("Segoe UI", 13, "bold"), text_color=T["text"], bg_color=T["inner"]).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=item["host"], width=245, anchor="w", font=("Consolas", 11), text_color=T["muted"], bg_color=T["inner"]).pack(side="left", padx=4)
            ctk.CTkLabel(row, text="Not tested", width=95, font=("Consolas", 11), text_color=T["muted"], bg_color=T["inner"]).pack(side="left", padx=6)
            ctk.CTkButton(row, text="SET T1", width=68, height=26, corner_radius=7, bg_color=T["inner"], font=("Segoe UI", 11, "bold"), fg_color=T["card_elev"], text_color=T["text"], border_width=1, border_color=T["border"], command=lambda h=item["host"]: self.app.apply_dns_as_t1(h)).pack(side="right", padx=10, pady=6)

    def start_route_check(self):
        if self.route_testing:
            return
        self.route_testing = True
        self.btn_run_routes.configure(state="disabled", text="CHECKING...")
        for w in self.route_scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.route_scroll, text=f"Testing latency & jitter to {len(ROUTE_CHECK_TARGETS)} game & web routes...", font=("Consolas", 12), text_color=self.app.T["accent1"], bg_color=self.app.T["card"]).pack(pady=40)
        threading.Thread(target=self._route_worker, daemon=True).start()

    def _route_worker(self):
        results = run_route_check(ROUTE_CHECK_TARGETS)
        self.last_route_results = results
        if self.app.app_alive:
            self.app.after(0, self._render_route_results, results)

    def _render_route_results(self, results):
        self.route_testing = False
        self.btn_run_routes.configure(state="normal", text="CHECK ALL ROUTES")
        for w in self.route_scroll.winfo_children():
            w.destroy()

        T = self.app.T
        for idx, (item, avg, jit, loss) in enumerate(results, start=1):
            row = ctk.CTkFrame(self.route_scroll, fg_color=T["inner"], bg_color=T["card"], corner_radius=9, border_width=1, border_color=COLOR_GREEN if idx == 1 and loss < 100 else T["border"])
            row.pack(fill="x", padx=6, pady=4)
            ctk.CTkLabel(row, text=item["cat"], width=68, height=22, corner_radius=6, fg_color=T["card_elev"], bg_color=T["inner"], text_color=T["accent1"], font=("Consolas", 10, "bold")).pack(side="left", padx=(10, 8), pady=8)
            ctk.CTkLabel(row, text=item["name"], width=150, anchor="w", font=("Segoe UI", 13, "bold"), text_color=T["text"], bg_color=T["inner"]).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=item["host"][:28], width=220, anchor="w", font=("Consolas", 11), text_color=T["muted"], bg_color=T["inner"]).pack(side="left", padx=4)

            ping_txt = f"{avg} ms" if avg != 9999 else "TIMEOUT"
            ping_clr = get_health_color(-1 if avg == 9999 else avg)
            ctk.CTkLabel(row, text=ping_txt, width=78, font=("Consolas", 13, "bold"), text_color=ping_clr, bg_color=T["inner"]).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f"Jit:{jit}ms", width=70, font=("Consolas", 11), text_color=T["muted"], bg_color=T["inner"]).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f"Loss:{loss}%", width=70, font=("Consolas", 11), text_color=COLOR_RED if loss > 0 else T["muted"], bg_color=T["inner"]).pack(side="left", padx=4)

            ctk.CTkButton(row, text="SET T1", width=66, height=26, corner_radius=7, bg_color=T["inner"], font=("Segoe UI", 11, "bold"), fg_color=T["card_elev"], text_color=T["text"], border_width=1, border_color=T["border"], command=lambda h=item["host"]: self.app.apply_dns_as_t1(h)).pack(side="right", padx=10, pady=6)