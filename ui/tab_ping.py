import tkinter as tk
import customtkinter as ctk
from PIL import ImageTk

from core.config import (
    COLOR_GREEN, COLOR_ORANGE, COLOR_RED, COLOR_YELLOW,
    get_health_color, get_health_tag, get_quality_badge,
)
from ui.graphics import render_ping_graph_base, render_ping_graph_frame

MAX_LOG_LINES = 1200


class PingTabView(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=app.T["bg"], corner_radius=0)
        self.app = app

        self.graph_data_1 = [None] * 60
        self.graph_data_2 = [None] * 60
        self.graph_times = [""] * 60
        self.hover_idx = None
        self._base_img = None
        self._meta = None
        self._photo = None

        self._build_ui()

    def _build_ui(self):
        T = self.app.T
        self.dash_frame = ctk.CTkFrame(self, fg_color=T["bg"], corner_radius=0)
        self.dash_frame.pack(pady=0, fill="x")

        # کارت تارگت ۱
        self.card1 = ctk.CTkFrame(self.dash_frame, height=158, corner_radius=14, border_width=1.5, bg_color=T["bg"])
        self.card1.pack(side="left", expand=True, padx=(0, 6), fill="x")
        self.card1.pack_propagate(False)
        self.lbl_t1_grade = ctk.CTkLabel(self.card1, text="IDLE", font=("Consolas", 10, "bold"), corner_radius=7, width=76, height=22)
        self.lbl_t1_grade.place(relx=0.96, rely=0.14, anchor="e")
        self.lbl_t1_name = ctk.CTkLabel(self.card1, text="TARGET 1", font=("Segoe UI", 13, "bold"))
        self.lbl_t1_name.pack(pady=(14, 0))
        self.lbl_t1_ping = ctk.CTkLabel(self.card1, text="-- ms", font=("Segoe UI", 46, "bold"))
        self.lbl_t1_ping.pack(pady=0)
        self.bar_t1 = ctk.CTkProgressBar(self.card1, height=7, corner_radius=4)
        self.bar_t1.pack(padx=38, pady=6, fill="x")
        self.bar_t1.set(0)
        self.lbl_t1_stats = ctk.CTkLabel(self.card1, text="Min: -  |  Avg: -  |  Max: -  |  Jit: -  |  Loss: 0%", font=("Consolas", 11))
        self.lbl_t1_stats.pack(pady=2)

        # کارت تارگت ۲
        self.card2 = ctk.CTkFrame(self.dash_frame, height=158, corner_radius=14, border_width=1.5, bg_color=T["bg"])
        self.card2.pack_propagate(False)
        self.lbl_t2_grade = ctk.CTkLabel(self.card2, text="IDLE", font=("Consolas", 10, "bold"), corner_radius=7, width=76, height=22)
        self.lbl_t2_grade.place(relx=0.96, rely=0.14, anchor="e")
        self.lbl_t2_name = ctk.CTkLabel(self.card2, text="TARGET 2", font=("Segoe UI", 13, "bold"))
        self.lbl_t2_name.pack(pady=(14, 0))
        self.lbl_t2_ping = ctk.CTkLabel(self.card2, text="-- ms", font=("Segoe UI", 46, "bold"))
        self.lbl_t2_ping.pack(pady=0)
        self.bar_t2 = ctk.CTkProgressBar(self.card2, height=7, corner_radius=4)
        self.bar_t2.pack(padx=38, pady=6, fill="x")
        self.bar_t2.set(0)
        self.lbl_t2_stats = ctk.CTkLabel(self.card2, text="Min: -  |  Avg: -  |  Max: -  |  Jit: -  |  Loss: 0%", font=("Consolas", 11))
        self.lbl_t2_stats.pack(pady=2)

        # نمودار رادار + لاگ اتصال
        self.bottom_container = ctk.CTkFrame(self, fg_color=T["bg"], corner_radius=0)
        self.bottom_container.pack(pady=10, fill="both", expand=True)

        self.graph_frame = ctk.CTkFrame(self.bottom_container, corner_radius=14, border_width=1, bg_color=T["bg"])
        self.graph_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.lbl_graph_title = ctk.CTkLabel(self.graph_frame, text="LIVE LATENCY RADAR  •  HD ANTI-ALIASED  (HOVER TO INSPECT)", font=("Consolas", 10, "bold"))
        self.lbl_graph_title.pack(pady=(10, 0))
        self.canvas = tk.Canvas(self.graph_frame, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True, padx=12, pady=(6, 12))
        self.canvas.bind("<Configure>", lambda e: self.draw_grid(rebuild_base=True))
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<Leave>", self._on_leave)

        self.log_frame = ctk.CTkFrame(self.bottom_container, corner_radius=14, width=325, border_width=1, bg_color=T["bg"])
        self.log_frame.pack(side="right", fill="both")
        self.log_frame.pack_propagate(False)

        self.log_head = ctk.CTkFrame(self.log_frame, fg_color=T["card"], corner_radius=0)
        self.log_head.pack(fill="x", padx=12, pady=(10, 0))
        self.lbl_log_title = ctk.CTkLabel(self.log_head, text="CONNECTION LOG", font=("Consolas", 11, "bold"))
        self.lbl_log_title.pack(side="left")
        self.btn_clear_log = ctk.CTkButton(self.log_head, text="CLEAR", width=54, height=22, corner_radius=6, font=("Consolas", 9, "bold"), command=self.clear_log)
        self.btn_clear_log.pack(side="right")

        self.log_box = ctk.CTkTextbox(self.log_frame, state="disabled", font=("Consolas", 11, "bold"), border_width=1, corner_radius=10)
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(8, 10))
        self.log_box.tag_config("GREEN", foreground=COLOR_GREEN)
        self.log_box.tag_config("YELLOW", foreground=COLOR_YELLOW)
        self.log_box.tag_config("ORANGE", foreground=COLOR_ORANGE)
        self.log_box.tag_config("RED", foreground=COLOR_RED)
        self.log_box.tag_config("INFO", foreground="#38BDF8")
        self.log_box.tag_config("TIME", foreground="#64748B")
        self.log_box.tag_config("LINE", foreground="#334155")

    def apply_theme(self, T):
        self.configure(fg_color=T["bg"])
        self.dash_frame.configure(fg_color=T["bg"])
        self.bottom_container.configure(fg_color=T["bg"])

        self.card1.configure(fg_color=T["card"], border_color=T["accent1"], bg_color=T["bg"])
        self.lbl_t1_name.configure(text_color=T["accent1"], bg_color=T["card"])
        self.lbl_t1_grade.configure(fg_color=T["card_elev"], text_color=T["muted"], bg_color=T["card"])
        self.bar_t1.configure(fg_color=T["border"], bg_color=T["card"])
        self.lbl_t1_stats.configure(text_color=T["muted"], bg_color=T["card"])

        self.card2.configure(fg_color=T["card"], border_color=T["accent2"], bg_color=T["bg"])
        self.lbl_t2_name.configure(text_color=T["accent2"], bg_color=T["card"])
        self.lbl_t2_grade.configure(fg_color=T["card_elev"], text_color=T["muted"], bg_color=T["card"])
        self.bar_t2.configure(fg_color=T["border"], bg_color=T["card"])
        self.lbl_t2_stats.configure(text_color=T["muted"], bg_color=T["card"])

        if not self.app.is_running:
            self.lbl_t1_ping.configure(text_color=T["text"], bg_color=T["card"])
            self.lbl_t2_ping.configure(text_color=T["text"], bg_color=T["card"])
        else:
            self.lbl_t1_ping.configure(bg_color=T["card"])
            self.lbl_t2_ping.configure(bg_color=T["card"])

        self.graph_frame.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"])
        self.lbl_graph_title.configure(text_color=T["muted"], bg_color=T["card"])
        self.canvas.configure(bg=T["card"])

        self.log_frame.configure(fg_color=T["card"], border_color=T["border"], bg_color=T["bg"])
        self.log_head.configure(fg_color=T["card"])
        self.lbl_log_title.configure(text_color=T["muted"], bg_color=T["card"])
        self.btn_clear_log.configure(fg_color=T["card_elev"], bg_color=T["card"], text_color=T["muted"], hover_color=T["border"])
        self.log_box.configure(fg_color=T["inner"], bg_color=T["card"], text_color=T["text"], border_color=T["border"])
        self.draw_grid(rebuild_base=True)

    def set_target2_visible(self, visible):
        if visible:
            self.card2.pack(side="right", expand=True, padx=(6, 0), fill="x")
        else:
            self.card2.pack_forget()
        self.draw_grid(rebuild_base=True)

    def set_target_names(self, t1, t2):
        self.lbl_t1_name.configure(text=f"{t1[:15]}..." if len(t1) > 15 else t1)
        self.lbl_t2_name.configure(text=f"{t2[:15]}..." if len(t2) > 15 else t2)

    def update_card(self, which, ping_val, stats_txt, loss_pct):
        clr = get_health_color(ping_val)
        badge_txt, badge_clr = get_quality_badge(ping_val, loss_pct)
        badge_fg = "#000000" if badge_clr != COLOR_RED else "#FFFFFF"

        if which == 1:
            self.lbl_t1_stats.configure(text=stats_txt)
            self.lbl_t1_grade.configure(text=badge_txt, fg_color=badge_clr, text_color=badge_fg)
            self.lbl_t1_ping.configure(text=f"{ping_val} ms" if ping_val != -1 else "TIMEOUT", text_color=clr)
            self.bar_t1.configure(progress_color=clr)
            self.bar_t1.set(min(ping_val / 300.0, 1.0) if ping_val != -1 else 1.0)
        else:
            self.lbl_t2_stats.configure(text=stats_txt)
            self.lbl_t2_grade.configure(text=badge_txt, fg_color=badge_clr, text_color=badge_fg)
            self.lbl_t2_ping.configure(text=f"{ping_val} ms" if ping_val != -1 else "TIMEOUT", text_color=clr)
            self.bar_t2.configure(progress_color=clr)
            self.bar_t2.set(min(ping_val / 300.0, 1.0) if ping_val != -1 else 1.0)

    def _trim_log(self):
        if int(self.log_box.index("end-1c").split(".")[0]) > MAX_LOG_LINES:
            self.log_box.delete(f"{MAX_LOG_LINES + 1}.0", "end")

    def append_ping_log(self, time_str, t1, p1, t2, p2, num_targets):
        self.log_box.configure(state="normal")
        self.log_box.insert("1.0", "-" * 28 + "\n", "LINE")
        if num_targets == 2:
            t2_val = f"{p2}ms" if p2 != -1 else "TIMEOUT"
            self.log_box.insert("1.0", f" {t2}: {t2_val}\n", get_health_tag(p2))
        t1_val = f"{p1}ms" if p1 != -1 else "TIMEOUT"
        self.log_box.insert("1.0", f" {t1}: {t1_val}\n", get_health_tag(p1))
        self.log_box.insert("1.0", f"[{time_str}]\n", "TIME")
        self._trim_log()
        self.log_box.configure(state="disabled")

    def append_info_log(self, time_str, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("1.0", "-" * 28 + "\n", "LINE")
        self.log_box.insert("1.0", f" {message}\n", "INFO")
        self.log_box.insert("1.0", f"[{time_str}]\n", "TIME")
        self._trim_log()
        self.log_box.configure(state="disabled")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def push_graph_point(self, p1, p2, time_str, num_targets):
        self.graph_data_1.append(-1 if p1 == -1 else p1)
        self.graph_data_1.pop(0)
        self.graph_times.append(time_str)
        self.graph_times.pop(0)
        if num_targets == 2:
            self.graph_data_2.append(-1 if p2 == -1 else p2)
            self.graph_data_2.pop(0)
        self.draw_grid(rebuild_base=True)

    def _on_hover(self, event):
        w = self.canvas.winfo_width()
        plot_w = w - 48
        if plot_w <= 10:
            return
        idx = max(0, min(59, int(round((event.x / plot_w) * 59.0))))
        if idx != self.hover_idx:
            self.hover_idx = idx
            self.draw_grid(rebuild_base=False)

    def _on_leave(self, event):
        if self.hover_idx is not None:
            self.hover_idx = None
            self.draw_grid(rebuild_base=False)

    def draw_grid(self, rebuild_base=True):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 24 or h < 24:
            return
        T = self.app.T
        if rebuild_base or self._base_img is None or self._base_img.size != (w * 2, h * 2):
            self._base_img, self._meta = render_ping_graph_base(
                w, h, T, self.graph_data_1, self.graph_data_2, self.app.num_targets
            )
        disp = render_ping_graph_frame(
            self._base_img, self._meta, w, h, T,
            self.graph_data_1, self.graph_data_2, self.graph_times,
            self.app.num_targets, self.hover_idx,
        )
        self._photo = ImageTk.PhotoImage(disp)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)