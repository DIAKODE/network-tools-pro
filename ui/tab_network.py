import threading
import tkinter as tk
from datetime import datetime
import customtkinter as ctk
from PIL import ImageTk

from core.config import COLOR_GREEN, COLOR_ORANGE, COLOR_RED, format_bytes
from core.net_engine import run_speedtest
from ui.apps_panel import LiveAppsPanel
from ui.graphics import render_net_graph_base, render_net_graph_frame


class NetworkTabView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=app.T["bg"], corner_radius=0)
        self.app = app

        self.speedtest_running = False
        self.dl_history = [0.0] * 60
        self.ul_history = [0.0] * 60
        self.net_times = [""] * 60
        self.hover_idx = None
        self._base_img = None
        self._meta = None
        self._photo = None
        self._last_apps = []

        self._build_ui()

    def _build_ui(self):
        T = self.app.T
        self.net_cards_frame = ctk.CTkFrame(self, fg_color=T["bg"], corner_radius=0)
        self.net_cards_frame.pack(pady=0, fill="x")

        # کارت دانلود
        self.card_dl = ctk.CTkFrame(self.net_cards_frame, corner_radius=14, border_width=1.5, border_color=COLOR_GREEN, bg_color=T["bg"])
        self.card_dl.pack(side="left", expand=True, padx=(0, 6), fill="x", ipady=6)
        self.dl_head = ctk.CTkFrame(self.card_dl, fg_color=T["card"], corner_radius=0)
        self.dl_head.pack(pady=(10, 0))
        self.lbl_dl_icon = ctk.CTkLabel(self.dl_head, text="")
        self.lbl_dl_icon.pack(side="left", padx=(0, 8))
        self.lbl_dl_title = ctk.CTkLabel(self.dl_head, text="DOWNLOAD SPEED", font=("Segoe UI", 12, "bold"), text_color=COLOR_GREEN)
        self.lbl_dl_title.pack(side="left")
        self.lbl_dl_val = ctk.CTkLabel(self.card_dl, text="0.0", font=("Segoe UI", 36, "bold"))
        self.lbl_dl_val.pack()
        self.lbl_dl_unit = ctk.CTkLabel(self.card_dl, text="KB/s", font=("Consolas", 11))
        self.lbl_dl_unit.pack(pady=(0, 4))
        self.bar_dl = ctk.CTkProgressBar(self.card_dl, height=6, progress_color=COLOR_GREEN, corner_radius=3)
        self.bar_dl.pack(padx=34, fill="x")
        self.bar_dl.set(0)
        self.lbl_dl_total = ctk.CTkLabel(self.card_dl, text="Session Total: 0.0 KB", font=("Consolas", 11, "bold"))
        self.lbl_dl_total.pack(pady=(6, 2))

        # کارت آپلود
        self.card_ul = ctk.CTkFrame(self.net_cards_frame, corner_radius=14, border_width=1.5, border_color=COLOR_ORANGE, bg_color=T["bg"])
        self.card_ul.pack(side="right", expand=True, padx=(6, 0), fill="x", ipady=6)
        self.ul_head = ctk.CTkFrame(self.card_ul, fg_color=T["card"], corner_radius=0)
        self.ul_head.pack(pady=(10, 0))
        self.lbl_ul_icon = ctk.CTkLabel(self.ul_head, text="")
        self.lbl_ul_icon.pack(side="left", padx=(0, 8))
        self.lbl_ul_title = ctk.CTkLabel(self.ul_head, text="UPLOAD SPEED", font=("Segoe UI", 12, "bold"), text_color=COLOR_ORANGE)
        self.lbl_ul_title.pack(side="left")
        self.lbl_ul_val = ctk.CTkLabel(self.card_ul, text="0.0", font=("Segoe UI", 36, "bold"))
        self.lbl_ul_val.pack()
        self.lbl_ul_unit = ctk.CTkLabel(self.card_ul, text="KB/s", font=("Consolas", 11))
        self.lbl_ul_unit.pack(pady=(0, 4))
        self.bar_ul = ctk.CTkProgressBar(self.card_ul, height=6, progress_color=COLOR_ORANGE, corner_radius=3)
        self.bar_ul.pack(padx=34, fill="x")
        self.bar_ul.set(0)
        self.lbl_ul_total = ctk.CTkLabel(self.card_ul, text="Session Total: 0.0 KB", font=("Consolas", 11, "bold"))
        self.lbl_ul_total.pack(pady=(6, 2))

        # نوار تست سرعت داخلی
        self.speedtest_bar = ctk.CTkFrame(self, corner_radius=12, border_width=1, bg_color=T["bg"])
        self.speedtest_bar.pack(fill="x", pady=(8, 0))
        self.lbl_speedtest = ctk.CTkLabel(self.speedtest_bar, text="SPEED TEST: Ready to measure real line throughput (Mbps)", font=("Consolas", 12, "bold"))
        self.lbl_speedtest.pack(side="left", padx=14, pady=9)
        self.btn_speedtest = ctk.CTkButton(
            self.speedtest_bar, text=" RUN SPEED TEST", compound="left", width=152, height=30,
            corner_radius=8, font=("Segoe UI", 11, "bold"), fg_color=COLOR_GREEN,
            text_color="#000000", hover_color="#059669", command=self.start_speedtest,
        )
        self.btn_speedtest.pack(side="right", padx=10, pady=7)

        # نمودار زنده پهنای باند
        self.net_graph_frame = ctk.CTkFrame(self, height=150, corner_radius=14, border_width=1, bg_color=T["bg"])
        self.net_graph_frame.pack(fill="x", pady=(8, 6))
        self.net_graph_frame.pack_propagate(False)
        self.lbl_net_graph_title = ctk.CTkLabel(self.net_graph_frame, text="LIVE BANDWIDTH MONITOR  •  HD ANTI-ALIASED  (HOVER TO INSPECT)", font=("Consolas", 10, "bold"))
        self.lbl_net_graph_title.pack(pady=(8, 0))
        self.net_canvas = tk.Canvas(self.net_graph_frame, highlightthickness=0, cursor="crosshair")
        self.net_canvas.pack(fill="both", expand=True, padx=12, pady=(4, 10))
        self.net_canvas.bind("<Configure>", lambda e: self.draw_net_graph(rebuild_base=True))
        self.net_canvas.bind("<Motion>", self._on_hover)
        self.net_canvas.bind("<Leave>", self._on_leave)

        # جدول تعاملی مصرف اینترنت به تفکیک هر برنامه + KILL
        self.apps_panel = LiveAppsPanel(
            self,
            theme=T,
            is_admin_mode=getattr(self.app, "is_etw_active", False),
            on_request_admin=self.app.request_admin_elevation,
            on_reset_totals=self.app.reset_app_usage_totals,
        )
        self.apps_panel.pack(fill="both", expand=True, pady=(2, 4))

    def apply_theme(self, T, icons):
        self.configure(fg_color=T["bg"])
        self.net_cards_frame.configure(fg_color=T["bg"])

        self.lbl_dl_icon.configure(image=icons["dl"], bg_color=T["card"])
        self.lbl_dl_title.configure(bg_color=T["card"])
        self.lbl_ul_icon.configure(image=icons["ul"], bg_color=T["card"])
        self.lbl_ul_title.configure(bg_color=T["card"])
        self.btn_speedtest.configure(image=icons["bolt"], bg_color=T["card"])

        self.card_dl.configure(fg_color=T["card"], bg_color=T["bg"])
        self.dl_head.configure(fg_color=T["card"])
        self.lbl_dl_val.configure(text_color=T["text"], bg_color=T["card"])
        self.lbl_dl_unit.configure(text_color=T["muted"], bg_color=T["card"])
        self.bar_dl.configure(fg_color=T["border"], bg_color=T["card"])
        self.lbl_dl_total.configure(text_color=T["muted"], bg_color=T["card"])

        self.card_ul.configure(fg_color=T["card"], bg_color=T["bg"])
        self.ul_head.configure(fg_color=T["card"])
        self.lbl_ul_val.configure(text_color=T["text"], bg_color=T["card"])
        self.lbl_ul_unit.configure(text_color=T["muted"], bg_color=T["card"])
        self.bar_ul.configure(fg_color=T["border"], bg_color=T["card"])
        self.lbl_ul_total.configure(text_color=T["muted"], bg_color=T["card"])

        self.speedtest_bar.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"])
        if not self.speedtest_running:
            self.lbl_speedtest.configure(text_color=T["accent1"], bg_color=T["card"])
        else:
            self.lbl_speedtest.configure(bg_color=T["card"])

        self.net_graph_frame.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"])
        self.lbl_net_graph_title.configure(text_color=T["muted"], bg_color=T["card"])
        self.net_canvas.configure(bg=T["card"])

        self.apps_panel.apply_theme(T)
        self.draw_net_graph(rebuild_base=True)

    def on_tab_selected(self):
        self.apps_panel.update_rows(self._last_apps)
        self.after(30, lambda: self.draw_net_graph(rebuild_base=True))

    def update_network(self, dl, ul, total_dl, total_ul, apps, is_active_tab):
        if dl < 1024:
            self.lbl_dl_val.configure(text=f"{dl:.1f}")
            self.lbl_dl_unit.configure(text="KB/s")
            self.bar_dl.set(min(dl / 1024.0, 1.0))
        else:
            self.lbl_dl_val.configure(text=f"{dl / 1024:.2f}")
            self.lbl_dl_unit.configure(text="MB/s")
            self.bar_dl.set(min(dl / 10240.0, 1.0))

        if ul < 1024:
            self.lbl_ul_val.configure(text=f"{ul:.1f}")
            self.lbl_ul_unit.configure(text="KB/s")
            self.bar_ul.set(min(ul / 1024.0, 1.0))
        else:
            self.lbl_ul_val.configure(text=f"{ul / 1024:.2f}")
            self.lbl_ul_unit.configure(text="MB/s")
            self.bar_ul.set(min(ul / 10240.0, 1.0))

        self.lbl_dl_total.configure(text=f"Session Total: {format_bytes(total_dl)}")
        self.lbl_ul_total.configure(text=f"Session Total: {format_bytes(total_ul)}")

        now_str = datetime.now().strftime("%H:%M:%S")
        self.dl_history.append(dl)
        self.dl_history.pop(0)
        self.ul_history.append(ul)
        self.ul_history.pop(0)
        self.net_times.append(now_str)
        self.net_times.pop(0)

        if isinstance(apps, list) and (not apps or isinstance(apps[0], dict)):
            self._last_apps = apps

        if is_active_tab:
            self.draw_net_graph(rebuild_base=True)
            self.apps_panel.update_rows(self._last_apps)

    def start_speedtest(self):
        if self.speedtest_running:
            return
        self.speedtest_running = True
        self.btn_speedtest.configure(state="disabled", text=" TESTING...")
        self.lbl_speedtest.configure(text="SPEED TEST: Connecting to fast edge server...", text_color=self.app.T["accent1"])
        threading.Thread(target=self._speedtest_worker, daemon=True).start()

    def _speedtest_worker(self):
        def on_prog(avg_mbps, elapsed, limit):
            if self.app.app_alive:
                self.app.after(0, lambda a=avg_mbps, e=elapsed: self.lbl_speedtest.configure(text=f"SPEED TEST: {a:.2f} Mbps  ({e:.1f}s / {limit:.0f}s)"))

        final_mbps, peak_mbps = run_speedtest(lambda: self.app.app_alive, on_prog, duration_limit=5.0)
        if self.app.app_alive:
            self.app.after(0, self._finish_speedtest, final_mbps, peak_mbps)

    def _finish_speedtest(self, avg_mbps, peak_mbps):
        self.speedtest_running = False
        self.btn_speedtest.configure(state="normal", text=" RUN SPEED TEST")
        if avg_mbps is not None:
            mb_per_sec = avg_mbps / 8.0
            self.lbl_speedtest.configure(
                text=f"SPEED RESULT:  Avg {avg_mbps:.2f} Mbps ({mb_per_sec:.2f} MB/s)  |  Peak {peak_mbps:.2f} Mbps",
                text_color=COLOR_GREEN,
            )
        else:
            self.lbl_speedtest.configure(text="SPEED TEST: Failed (Check connection or VPN)", text_color=COLOR_RED)

    def _on_hover(self, event):
        w = self.net_canvas.winfo_width()
        plot_w = w - 56
        if plot_w <= 10:
            return
        idx = max(0, min(59, int(round((event.x / plot_w) * 59.0))))
        if idx != self.hover_idx:
            self.hover_idx = idx
            self.draw_net_graph(rebuild_base=False)

    def _on_leave(self, event):
        if self.hover_idx is not None:
            self.hover_idx = None
            self.draw_net_graph(rebuild_base=False)

    def draw_net_graph(self, rebuild_base=True):
        w, h = self.net_canvas.winfo_width(), self.net_canvas.winfo_height()
        if w < 24 or h < 24:
            return
        T = self.app.T
        if rebuild_base or self._base_img is None or self._base_img.size != (w * 2, h * 2):
            self._base_img, self._meta = render_net_graph_base(w, h, T, self.dl_history, self.ul_history)
        disp = render_net_graph_frame(
            self._base_img, self._meta, w, h, T,
            self.dl_history, self.ul_history, self.net_times, self.hover_idx,
        )
        self._photo = ImageTk.PhotoImage(disp)
        self.net_canvas.delete("all")
        self.net_canvas.create_image(0, 0, anchor="nw", image=self._photo)
