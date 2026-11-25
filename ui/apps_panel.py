import time
import customtkinter as ctk

from core.config import COLOR_GREEN, COLOR_ORANGE, COLOR_RED
from core.win_audio import kill_app_processes, show_os_notification

# عرض پیکسلی ثابت ستون‌های سمت راست برای تراز عمودی دقیق در تمام ردیف‌ها
COL_W_ACTION = 56
COL_W_TOTAL = 88
COL_W_UPLOAD = 102
COL_W_DOWNLOAD = 102


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
            bg_color=theme["bg"],
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

    def _is_dark(self) -> bool:
        return str(self.T.get("mode", "Dark")).lower() == "dark"

    def _build_ui(self):
        T = self.T

        # هدر پنل
        self.hdr = ctk.CTkFrame(self, fg_color=T["card"], corner_radius=0)
        self.hdr.pack(fill="x", padx=12, pady=(7, 4))

        self.hdr_left = ctk.CTkFrame(self.hdr, fg_color=T["card"], corner_radius=0)
        self.hdr_left.pack(side="left", fill="x", expand=True)

        self.lbl_title = ctk.CTkLabel(
            self.hdr_left,
            text="PER-APP NETWORK MONITOR",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=T["text"],
            bg_color=T["card"],
        )
        self.lbl_title.pack(side="left")

        badge_text = "  LIVE • ADMIN  " if self.is_admin_mode else "  STANDARD MODE  "
        badge_color = COLOR_GREEN if self.is_admin_mode else COLOR_ORANGE
        self.lbl_mode_badge = ctk.CTkLabel(
            self.hdr_left,
            text=badge_text,
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            fg_color=T["card_elev"],
            bg_color=T["card"],
            text_color=badge_color,
            corner_radius=6,
            height=19,
        )
        self.lbl_mode_badge.pack(side="left", padx=(8, 0))

        # دکمه سمت راست هدر
        if self.is_admin_mode:
            self.btn_action = ctk.CTkButton(
                self.hdr,
                text="RESET TOTALS",
                width=102,
                height=24,
                corner_radius=7,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color=T["card_elev"],
                bg_color=T["card"],
                hover_color=T["border"],
                text_color=T["muted"],
                command=self._handle_reset,
            )
            self.btn_action.pack(side="right")
        else:
            self.btn_action = ctk.CTkButton(
                self.hdr,
                text="ENABLE LIVE APP USAGE (ADMIN)",
                width=208,
                height=24,
                corner_radius=7,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color=T["accent1"],
                bg_color=T["card"],
                hover_color=T.get("accent2", T["accent1"]),
                text_color="#000000" if self._is_dark() else "#FFFFFF",
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
                text_color=T["muted"],
                bg_color=T["card"],
                anchor="w",
            )
            self.banner.pack(fill="x", padx=12, pady=(0, 4))

        # ردیف عنوان ستون‌ها (قفل‌شده از سمت راست، هم‌تراز با ردیف‌ها و اسکرول‌بار)
        self.col_hdr = ctk.CTkFrame(
            self,
            fg_color=T["card_elev"],
            bg_color=T["card"],
            corner_radius=7,
            height=24,
        )
        self.col_hdr.pack(fill="x", padx=10, pady=(0, 3))
        self.col_hdr.pack_propagate(False)

        hdr_font = ctk.CTkFont(family="Consolas", size=10, weight="bold")
        self._col_labels = []

        # چیدمان از راست به چپ با عرض ثابت تا کاملاً روی ستون ردیف‌ها قفل شود
        lbl_h_act = ctk.CTkLabel(
            self.col_hdr, text="ACTION", width=COL_W_ACTION, anchor="e",
            font=hdr_font, text_color=T["muted"], bg_color=T["card_elev"],
        )
        lbl_h_act.pack(side="right", padx=(6, 24), pady=3)
        self._col_labels.append(lbl_h_act)

        lbl_h_tot = ctk.CTkLabel(
            self.col_hdr, text="TOTAL", width=COL_W_TOTAL, anchor="e",
            font=hdr_font, text_color=T["muted"], bg_color=T["card_elev"],
        )
        lbl_h_tot.pack(side="right", padx=6, pady=3)
        self._col_labels.append(lbl_h_tot)

        lbl_h_ul = ctk.CTkLabel(
            self.col_hdr, text="UPLOAD", width=COL_W_UPLOAD, anchor="e",
            font=hdr_font, text_color=T["muted"], bg_color=T["card_elev"],
        )
        lbl_h_ul.pack(side="right", padx=6, pady=3)
        self._col_labels.append(lbl_h_ul)

        lbl_h_dl = ctk.CTkLabel(
            self.col_hdr, text="DOWNLOAD", width=COL_W_DOWNLOAD, anchor="e",
            font=hdr_font, text_color=T["muted"], bg_color=T["card_elev"],
        )
        lbl_h_dl.pack(side="right", padx=6, pady=3)
        self._col_labels.append(lbl_h_dl)

        lbl_h_app = ctk.CTkLabel(
            self.col_hdr, text="APPLICATION", anchor="w",
            font=hdr_font, text_color=T["muted"], bg_color=T["card_elev"],
        )
        lbl_h_app.pack(side="left", fill="x", expand=True, padx=(10, 6), pady=3)
        self._col_labels.append(lbl_h_app)

        # لیست اسکرول‌پذیر ردیف‌ها
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=T["card"],
            corner_radius=0,
            scrollbar_button_color=T["border"],
            scrollbar_button_hover_color=T["accent1"],
            height=185,
        )
        self.scroll.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self.lbl_empty = ctk.CTkLabel(
            self.scroll,
            text="No active network applications detected yet...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=T["muted"],
            bg_color=T["card"],
        )
        self.lbl_empty.pack(pady=24)

    def _create_row_widget(self):
        T = self.T
        frame = ctk.CTkFrame(
            self.scroll,
            fg_color=T["card_elev"],
            bg_color=T["card"],
            corner_radius=7,
            height=28,
        )
        frame.pack_propagate(False)

        # اول ستون‌های ثابت از راست بسته می‌شوند تا طول اسم برنامه هرگز جابه‌جایشان نکند
        btn_kill = ctk.CTkButton(
            frame,
            text="KILL",
            width=COL_W_ACTION,
            height=20,
            corner_radius=5,
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            fg_color="#3B151B" if self._is_dark() else "#FEE2E2",
            bg_color=T["card_elev"],
            hover_color=COLOR_RED,
            text_color=COLOR_RED,
            text_color_disabled=T["muted"],
        )
        btn_kill.pack(side="right", padx=(6, 8), pady=4)

        lbl_tot = ctk.CTkLabel(
            frame,
            text="—",
            width=COL_W_TOTAL,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=T["muted"],
            bg_color=T["card_elev"],
            anchor="e",
        )
        lbl_tot.pack(side="right", padx=6, pady=2)

        lbl_ul = ctk.CTkLabel(
            frame,
            text="—",
            width=COL_W_UPLOAD,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=T["muted"],
            bg_color=T["card_elev"],
            anchor="e",
        )
        lbl_ul.pack(side="right", padx=6, pady=2)

        lbl_dl = ctk.CTkLabel(
            frame,
            text="—",
            width=COL_W_DOWNLOAD,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=T["muted"],
            bg_color=T["card_elev"],
            anchor="e",
        )
        lbl_dl.pack(side="right", padx=6, pady=2)

        lbl_name = ctk.CTkLabel(
            frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=T["text"],
            bg_color=T["card_elev"],
            anchor="w",
        )
        lbl_name.pack(side="left", fill="x", expand=True, padx=(10, 6), pady=2)

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

        T = self.T
        is_dark = self._is_dark()

        for idx, item in enumerate(self._last_data):
            slot = self._rows_pool[idx]
            name = item["name"]
            key = item["key"]
            conns = item.get("conns", 0)
            protected = item.get("protected", False)

            conn_suffix = f"  ({conns})" if conns > 0 else ""
            display_name = f"{name[:34]}{conn_suffix}"
            slot["name"].configure(text=display_name, text_color=T["text"])

            if self.is_admin_mode:
                dl_bps = item.get("dl_bps", 0.0)
                ul_bps = item.get("ul_bps", 0.0)
                tot_bytes = item.get("total_dl", 0) + item.get("total_ul", 0)

                slot["dl"].configure(
                    text=_fmt_rate(dl_bps),
                    text_color=COLOR_GREEN if dl_bps >= 1024 else T["muted"],
                )
                slot["ul"].configure(
                    text=_fmt_rate(ul_bps),
                    text_color=COLOR_ORANGE if ul_bps >= 1024 else T["muted"],
                )
                slot["tot"].configure(
                    text=_fmt_total(tot_bytes),
                    text_color=T["text"] if tot_bytes > 0 else T["muted"],
                )
            else:
                slot["dl"].configure(text="Admin", text_color=T["muted"])
                slot["ul"].configure(text="Admin", text_color=T["muted"])
                slot["tot"].configure(text=f"{conns} conn", text_color=T["accent1"] if conns else T["muted"])

            # وضعیت دکمه KILL / SURE? / SYS
            if protected:
                slot["kill"].configure(
                    text="SYS",
                    state="disabled",
                    fg_color=T["card"],
                    bg_color=T["card_elev"],
                    text_color=T["muted"],
                    text_color_disabled=T["muted"],
                    command=lambda: None,
                )
            elif self._confirm_key == key:
                slot["kill"].configure(
                    text="SURE?",
                    state="normal",
                    fg_color=COLOR_RED,
                    bg_color=T["card_elev"],
                    hover_color="#DC2626",
                    text_color="#FFFFFF",
                    command=lambda n=name, k=key: self._on_kill_click(n, k),
                )
            else:
                slot["kill"].configure(
                    text="KILL",
                    state="normal",
                    fg_color="#3B151B" if is_dark else "#FEE2E2",
                    bg_color=T["card_elev"],
                    hover_color=COLOR_RED,
                    text_color=COLOR_RED,
                    command=lambda n=name, k=key: self._on_kill_click(n, k),
                )

            if not slot["visible"]:
                slot["frame"].pack(fill="x", padx=4, pady=1)
                slot["visible"] = True

        for idx in range(len(self._last_data), len(self._rows_pool)):
            slot = self._rows_pool[idx]
            if slot["visible"]:
                slot["frame"].pack_forget()
                slot["visible"] = False

    def apply_theme(self, theme: dict):
        self.T = theme
        T = theme
        self.configure(fg_color=T["card"], bg_color=T["bg"], border_color=T["border"])
        self.hdr.configure(fg_color=T["card"])
        self.hdr_left.configure(fg_color=T["card"])
        self.lbl_title.configure(text_color=T["text"], bg_color=T["card"])
        self.lbl_mode_badge.configure(fg_color=T["card_elev"], bg_color=T["card"])
        self.col_hdr.configure(fg_color=T["card_elev"], bg_color=T["card"])

        for lbl in self._col_labels:
            lbl.configure(text_color=T["muted"], bg_color=T["card_elev"])

        if self.banner is not None:
            self.banner.configure(text_color=T["muted"], bg_color=T["card"])

        if self.is_admin_mode:
            self.btn_action.configure(
                fg_color=T["card_elev"],
                bg_color=T["card"],
                hover_color=T["border"],
                text_color=T["muted"],
            )
        else:
            self.btn_action.configure(
                fg_color=T["accent1"],
                bg_color=T["card"],
                hover_color=T.get("accent2", T["accent1"]),
                text_color="#000000" if self._is_dark() else "#FFFFFF",
            )

        self.scroll.configure(
            fg_color=T["card"],
            scrollbar_button_color=T["border"],
            scrollbar_button_hover_color=T["accent1"],
        )
        self.lbl_empty.configure(text_color=T["muted"], bg_color=T["card"])

        for slot in self._rows_pool:
            slot["frame"].configure(fg_color=T["card_elev"], bg_color=T["card"])
            slot["name"].configure(bg_color=T["card_elev"])
            slot["dl"].configure(bg_color=T["card_elev"])
            slot["ul"].configure(bg_color=T["card_elev"])
            slot["tot"].configure(bg_color=T["card_elev"])
            slot["kill"].configure(bg_color=T["card_elev"])

        self.update_rows(self._last_data)