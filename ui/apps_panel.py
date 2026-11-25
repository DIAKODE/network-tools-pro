import time
import customtkinter as ctk

from core.config import COLOR_GREEN, COLOR_ORANGE, COLOR_RED
from core.win_audio import kill_app_processes, show_os_notification


def _fmt_rate(bps: float) -> str:
    if bps < 100:
        return "0 B/s"
    if bps < 1024:
        return f"{int(bps)} B/s"
    kbs = bps / 1024.0
    if kbs < 1024.0:
        return f"{kbs:.1f} KB/s"
    return f"{kbs / 1024.0:.2f} MB/s"


def _fmt_total(num_bytes: int) -> str:
    if num_bytes <= 0:
        return "0 B"
    kb = num_bytes / 1024.0
    if kb < 1024.0:
        return f"{kb:.0f} KB"
    mb = kb / 1024.0
    if mb < 1024.0:
        return f"{mb:.1f} MB"
    return f"{mb / 1024.0:.2f} GB"


class LiveAppsPanel(ctk.CTkFrame):
    """جدول زنده مصرف اینترنت به تفکیک هر برنامه + دکمه ایمن KILL + ارتقای اختیاری به Admin"""

    def __init__(self, master, theme: dict, is_admin_mode: bool, on_request_admin, on_reset_totals):
        super().__init__(
            master,
            fg_color=theme["card"],
            border_width=1,
            border_color=theme["border"],
            corner_radius=12,
        )
        self.T = theme
        self.is_admin_mode = is_admin_mode
        self.on_request_admin = on_request_admin
        self.on_reset_totals = on_reset_totals

        self._rows_pool = []
        self._last_data = []
        self._confirm_key = None
        self._confirm_until = 0.0

        self._build_ui()

    def _build_ui(self):
        # هدر پنل
        self.hdr = ctk.CTkFrame(self, fg_color="transparent")
        self.hdr.pack(fill="x", padx=12, pady=(10, 6))

        left = ctk.CTkFrame(self.hdr, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)

        self.lbl_title = ctk.CTkLabel(
            left,
            text="PER-APP NETWORK MONITOR",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=self.T["text"],
        )
        self.lbl_title.pack(side="left")

        badge_text = "  LIVE • ADMIN  " if self.is_admin_mode else "  STANDARD MODE  "
        badge_color = COLOR_GREEN if self.is_admin_mode else COLOR_ORANGE
        self.lbl_mode_badge = ctk.CTkLabel(
            left,
            text=badge_text,
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            fg_color=self.T["card_elev"],
            text_color=badge_color,
            corner_radius=6,
            height=20,
        )
        self.lbl_mode_badge.pack(side="left", padx=(8, 0))

        # دکمه سمت راست هدر
        if self.is_admin_mode:
            self.btn_action = ctk.CTkButton(
                self.hdr,
                text="RESET TOTALS",
                width=105,
                height=26,
                corner_radius=7,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color=self.T["card_elev"],
                hover_color=self.T["border"],
                text_color=self.T["muted"],
                command=self._handle_reset,
            )
            self.btn_action.pack(side="right")
        else:
            self.btn_action = ctk.CTkButton(
                self.hdr,
                text="ENABLE LIVE APP USAGE (ADMIN)",
                width=210,
                height=26,
                corner_radius=7,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color=self.T["accent1"],
                hover_color=self.T.get("accent2", self.T["accent1"]),
                text_color="#090D16",
                command=self._handle_request_admin,
            )
            self.btn_action.pack(side="right")

        # بنر راهنمای کوتاه در حالت غیرادمین
        self.banner = None
        if not self.is_admin_mode:
            self.banner = ctk.CTkLabel(
                self,
                text="Showing active apps with KILL support. Click 'ENABLE LIVE APP USAGE (ADMIN)' to view real-time KB/s & MB per app.",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=self.T["muted"],
                anchor="w",
            )
            self.banner.pack(fill="x", padx=12, pady=(0, 6))

        # ردیف عنوان ستون‌ها
        self.col_hdr = ctk.CTkFrame(self, fg_color=self.T["card_elev"], corner_radius=7, height=26)
        self.col_hdr.pack(fill="x", padx=10, pady=(0, 4))
        self.col_hdr.pack_propagate(False)

        self.col_hdr.grid_columnconfigure(0, weight=4)
        self.col_hdr.grid_columnconfigure(1, weight=2)
        self.col_hdr.grid_columnconfigure(2, weight=2)
        self.col_hdr.grid_columnconfigure(3, weight=2)
        self.col_hdr.grid_columnconfigure(4, weight=1)

        headers = [
            ("APPLICATION", "w", 0),
            ("DOWNLOAD", "e", 1),
            ("UPLOAD", "e", 2),
            ("TOTAL", "e", 3),
            ("ACTION", "e", 4),
        ]
        self._col_labels = []
        for text, anchor, col in headers:
            lbl = ctk.CTkLabel(
                self.col_hdr,
                text=text,
                font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
                text_color=self.T["muted"],
                anchor=anchor,
            )
            lbl.grid(row=0, column=col, sticky="ew", padx=(10 if col == 0 else 6, 10 if col == 4 else 6), pady=4)
            self._col_labels.append(lbl)

        # لیست اسکرول‌پذیر ردیف‌ها
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=self.T["border"],
            scrollbar_button_hover_color=self.T["accent1"],
            height=180,
        )
        self.scroll.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        self.lbl_empty = ctk.CTkLabel(
            self.scroll,
            text="No active network applications detected yet...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=self.T["muted"],
        )
        self.lbl_empty.pack(pady=24)

    def _create_row_widget(self):
        frame = ctk.CTkFrame(self.scroll, fg_color=self.T["card_elev"], corner_radius=8, height=34)
        frame.pack_propagate(False)
        frame.grid_columnconfigure(0, weight=4)
        frame.grid_columnconfigure(1, weight=2)
        frame.grid_columnconfigure(2, weight=2)
        frame.grid_columnconfigure(3, weight=2)
        frame.grid_columnconfigure(4, weight=1)

        lbl_name = ctk.CTkLabel(
            frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=self.T["text"],
            anchor="w",
        )
        lbl_name.grid(row=0, column=0, sticky="ew", padx=(10, 6), pady=4)

        lbl_dl = ctk.CTkLabel(
            frame,
            text="—",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=self.T["muted"],
            anchor="e",
        )
        lbl_dl.grid(row=0, column=1, sticky="ew", padx=6, pady=4)

        lbl_ul = ctk.CTkLabel(
            frame,
            text="—",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=self.T["muted"],
            anchor="e",
        )
        lbl_ul.grid(row=0, column=2, sticky="ew", padx=6, pady=4)

        lbl_tot = ctk.CTkLabel(
            frame,
            text="—",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=self.T["muted"],
            anchor="e",
        )
        lbl_tot.grid(row=0, column=3, sticky="ew", padx=6, pady=4)

        btn_kill = ctk.CTkButton(
            frame,
            text="KILL",
            width=54,
            height=22,
            corner_radius=6,
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            fg_color="#3B151B",
            hover_color=COLOR_RED,
            text_color=COLOR_RED,
        )
        btn_kill.grid(row=0, column=4, sticky="e", padx=(6, 8), pady=5)

        return {
            "frame": frame,
            "name": lbl_name,
            "dl": lbl_dl,
            "ul": lbl_ul,
            "tot": lbl_tot,
            "kill": btn_kill,
            "visible": False,
        }

    def _handle_request_admin(self):
        if callable(self.on_request_admin):
            self.on_request_admin()

    def _handle_reset(self):
        if callable(self.on_reset_totals):
            self.on_reset_totals()

    def _on_kill_click(self, app_name: str, app_key: str):
        now = time.monotonic()
        # کلیک اول: ورود به حالت تایید ۳ ثانیه‌ای
        if self._confirm_key != app_key or now > self._confirm_until:
            self._confirm_key = app_key
            self._confirm_until = now + 3.0
            self.update_rows(self._last_data)
            self.after(3100, self._clear_expired_confirm)
            return

        # کلیک دوم: بستن واقعی برنامه
        self._confirm_key = None
        self._confirm_until = 0.0
        killed, failed = kill_app_processes(app_name)
        if killed > 0:
            show_os_notification("Process Terminated", f"Closed {app_name} ({killed} proc)")
        elif failed > 0:
            show_os_notification("Access Denied", f"Need Admin rights to close {app_name}")
        self.update_rows(self._last_data)

    def _clear_expired_confirm(self):
        if self._confirm_key and time.monotonic() > self._confirm_until:
            self._confirm_key = None
            self.update_rows(self._last_data)

    def update_rows(self, rows: list[dict]):
        self._last_data = rows or []
        now = time.monotonic()
        if self._confirm_key and now > self._confirm_until:
            self._confirm_key = None

        if not self._last_data:
            for slot in self._rows_pool:
                if slot["visible"]:
                    slot["frame"].pack_forget()
                    slot["visible"] = False
            if not self.lbl_empty.winfo_ismapped():
                self.lbl_empty.pack(pady=24)
            return

        if self.lbl_empty.winfo_ismapped():
            self.lbl_empty.pack_forget()

        while len(self._rows_pool) < len(self._last_data):
            self._rows_pool.append(self._create_row_widget())

        for idx, item in enumerate(self._last_data):
            slot = self._rows_pool[idx]
            name = item["name"]
            key = item["key"]
            conns = item.get("conns", 0)
            protected = item.get("protected", False)

            conn_suffix = f"  ({conns})" if conns > 0 else ""
            display_name = f"{name[:24]}{conn_suffix}"
            slot["name"].configure(text=display_name, text_color=self.T["text"])

            if self.is_admin_mode:
                dl_bps = item.get("dl_bps", 0.0)
                ul_bps = item.get("ul_bps", 0.0)
                tot_bytes = item.get("total_dl", 0) + item.get("total_ul", 0)

                slot["dl"].configure(
                    text=_fmt_rate(dl_bps),
                    text_color=COLOR_GREEN if dl_bps >= 1024 else self.T["muted"],
                )
                slot["ul"].configure(
                    text=_fmt_rate(ul_bps),
                    text_color=COLOR_ORANGE if ul_bps >= 1024 else self.T["muted"],
                )
                slot["tot"].configure(
                    text=_fmt_total(tot_bytes),
                    text_color=self.T["text"] if tot_bytes > 0 else self.T["muted"],
                )
            else:
                slot["dl"].configure(text="Admin", text_color=self.T["muted"])
                slot["ul"].configure(text="Admin", text_color=self.T["muted"])
                slot["tot"].configure(text=f"{conns} conn", text_color=self.T["accent1"] if conns else self.T["muted"])

            # وضعیت دکمه KILL / SURE? / SYS
            if protected:
                slot["kill"].configure(
                    text="SYS",
                    state="disabled",
                    fg_color=self.T["card"],
                    text_color=self.T["muted"],
                    command=lambda: None,
                )
            elif self._confirm_key == key:
                slot["kill"].configure(
                    text="SURE?",
                    state="normal",
                    fg_color=COLOR_RED,
                    hover_color="#DC2626",
                    text_color="#FFFFFF",
                    command=lambda n=name, k=key: self._on_kill_click(n, k),
                )
            else:
                slot["kill"].configure(
                    text="KILL",
                    state="normal",
                    fg_color="#3B151B" if self.T.get("mode", "dark") == "dark" else "#FEE2E2",
                    hover_color=COLOR_RED,
                    text_color=COLOR_RED,
                    command=lambda n=name, k=key: self._on_kill_click(n, k),
                )

            if not slot["visible"]:
                slot["frame"].pack(fill="x", padx=4, pady=2)
                slot["visible"] = True

        for idx in range(len(self._last_data), len(self._rows_pool)):
            slot = self._rows_pool[idx]
            if slot["visible"]:
                slot["frame"].pack_forget()
                slot["visible"] = False

    def apply_theme(self, theme: dict):
        self.T = theme
        self.configure(fg_color=theme["card"], border_color=theme["border"])
        self.lbl_title.configure(text_color=theme["text"])
        self.lbl_mode_badge.configure(fg_color=theme["card_elev"])
        self.col_hdr.configure(fg_color=theme["card_elev"])
        for lbl in self._col_labels:
            lbl.configure(text_color=theme["muted"])
        if self.banner is not None:
            self.banner.configure(text_color=theme["muted"])
        if self.is_admin_mode:
            self.btn_action.configure(
                fg_color=theme["card_elev"],
                hover_color=theme["border"],
                text_color=theme["muted"],
            )
        else:
            self.btn_action.configure(
                fg_color=theme["accent1"],
                hover_color=theme.get("accent2", theme["accent1"]),
            )
        self.scroll.configure(
            scrollbar_button_color=theme["border"],
            scrollbar_button_hover_color=theme["accent1"],
        )
        self.lbl_empty.configure(text_color=theme["muted"])
        for slot in self._rows_pool:
            slot["frame"].configure(fg_color=theme["card_elev"])
        self.update_rows(self._last_data)
