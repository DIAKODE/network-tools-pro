import ctypes
import math
import os
import struct
import subprocess
import sys
import time
import wave

from plyer import notification
from core.config import APP_NAME, SFX_PROFILES

try:
    import winsound
except ImportError:
    winsound = None

try:
    import winreg
except ImportError:
    winreg = None


def set_app_user_model_id(app_id):
    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass


def show_os_notification(title, msg):
    try:
        notification.notify(title=title, message=msg, app_name=APP_NAME, timeout=4)
    except Exception:
        pass


# ================= تک‌اجرایی بودن برنامه (Win32 Mutex & Event) =================
class SingleInstanceManager:
    def __init__(
        self,
        mutex_name="Local\\NetworkToolsPro_SingleMutex_V61",
        event_name="Local\\NetworkToolsPro_ShowEvent_V61",
    ):
        self.mutex_handle = None
        self.event_handle = None
        self.already_running = False

        if os.name != "nt":
            return

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateEventW.restype = ctypes.c_void_p
        kernel32.OpenEventW.argtypes = [ctypes.c_uint32, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.OpenEventW.restype = ctypes.c_void_p
        kernel32.SetEvent.argtypes = [ctypes.c_void_p]
        kernel32.SetEvent.restype = ctypes.c_bool
        kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool
        self.kernel32 = kernel32

        self.mutex_handle = kernel32.CreateMutexW(None, False, mutex_name)
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            self.already_running = True
            h_event = kernel32.OpenEventW(0x0002, False, event_name)
            if h_event:
                kernel32.SetEvent(h_event)
                kernel32.CloseHandle(h_event)
            if self.mutex_handle:
                kernel32.CloseHandle(self.mutex_handle)
                self.mutex_handle = None
        else:
            self.event_handle = kernel32.CreateEventW(None, False, False, event_name)

    def wait_for_show(self, timeout_ms=500):
        if not self.event_handle:
            time.sleep(timeout_ms / 1000.0)
            return False
        return self.kernel32.WaitForSingleObject(self.event_handle, timeout_ms) == 0

    def cleanup(self):
        if os.name != "nt":
            return
        if self.event_handle:
            self.kernel32.CloseHandle(self.event_handle)
            self.event_handle = None
        if self.mutex_handle:
            self.kernel32.CloseHandle(self.mutex_handle)
            self.mutex_handle = None


# ================= قفل Click-Through روی بازی (Win32 API) =================
def set_window_click_through(tk_window, enable):
    """موس از روی مینی‌مود رد می‌شود تا وسط بازی اشتباهی روی آن کلیک نشود"""
    if os.name != "nt":
        return False
    try:
        user32 = ctypes.windll.user32
        tk_window.update_idletasks()
        hwnd = user32.GetAncestor(tk_window.winfo_id(), 2)  # GA_ROOT = 2
        if not hwnd:
            hwnd = tk_window.winfo_id()

        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020

        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if enable:
            style = style | WS_EX_LAYERED | WS_EX_TRANSPARENT
        else:
            style = style & ~WS_EX_TRANSPARENT

        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        # اعمال فوری تغییر استایل پنجره
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_FRAMECHANGED = 0x0020
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        return True
    except Exception:
        return False


def is_unlock_hotkey_pressed():
    """تشخیص شورت‌کات سراسری Ctrl + Shift + L برای باز کردن قفل مینی‌مود از داخل بازی"""
    if os.name != "nt":
        return False
    try:
        user32 = ctypes.windll.user32
        ctrl = (user32.GetAsyncKeyState(0x11) & 0x8000) != 0
        shift = (user32.GetAsyncKeyState(0x10) & 0x8000) != 0
        key_l = (user32.GetAsyncKeyState(0x4C) & 0x8000) != 0
        return ctrl and shift and key_l
    except Exception:
        return False


# ================= استارت‌آپ ویندوز =================
def is_autostart_enabled():
    if not winreg:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        for name in ("NetworkToolsPro", "DiakoPingMonitor"):
            try:
                winreg.QueryValueEx(key, name)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                continue
        winreg.CloseKey(key)
    except Exception:
        pass
    return False


def set_autostart(enable):
    if not winreg:
        return
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        for old_name in ("DiakoPingMonitor", "NetworkToolsPro"):
            try:
                winreg.DeleteValue(key, old_name)
            except FileNotFoundError:
                pass
        if enable:
            if getattr(sys, "frozen", False):
                cmd = f'"{sys.executable}" --minimized'
            else:
                entry = os.path.abspath(sys.argv[0])
                cmd = f'"{sys.executable}" "{entry}" --minimized'
            winreg.SetValueEx(key, "NetworkToolsPro", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
    except Exception:
        pass


# ================= کنترل DNS سیستم ویندوز =================
def get_active_system_dns():
    try:
        ps = "(Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object {$_.ServerAddresses.Count -gt 0} | Select-Object -First 1).ServerAddresses -join ', '"
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps],
            stderr=subprocess.STDOUT, universal_newlines=True, errors="ignore",
            creationflags=subprocess.CREATE_NO_WINDOW,
        ).strip()
        active_ips = {x.strip() for x in out.split(",") if x.strip()}
        txt = f"ACTIVE SYSTEM DNS: {out}" if out else "ACTIVE SYSTEM DNS: Auto (DHCP)"
        return active_ips, txt
    except Exception:
        return set(), "ACTIVE SYSTEM DNS: Unknown"


def set_system_dns(ip, ip2=""):
    servers = f"'{ip}','{ip2}'" if ip2 else f"'{ip}'"
    ps_cmd = (
        f"$adapters = Get-NetAdapter | Where-Object {{$_.Status -eq 'Up'}}; "
        f"foreach ($a in $adapters) {{ Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ServerAddresses ({servers}) }}; "
        f"ipconfig /flushdns"
    )
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "powershell.exe",
            f'-NoProfile -WindowStyle Hidden -Command "{ps_cmd}"', None, 0
        )
        return True
    except Exception:
        return False


def reset_system_dns():
    ps_cmd = (
        "$adapters = Get-NetAdapter | Where-Object {$_.Status -eq 'Up'}; "
        "foreach ($a in $adapters) { Set-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ResetServerAddresses }; "
        "ipconfig /flushdns"
    )
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "powershell.exe",
            f'-NoProfile -WindowStyle Hidden -Command "{ps_cmd}"', None, 0
        )
        return True
    except Exception:
        return False


def flush_system_dns():
    try:
        subprocess.run(["ipconfig", "/flushdns"], creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except Exception:
        return False


# ================= موتور تولید و پخش صدا با ولوم دقیق =================
def write_chime_wav(filepath, notes, harmonics=(0.80, 0.16, 0.04), sample_rate=44100, volume=0.30):
    effective_vol = max(0.0, min(1.0, volume)) ** 1.35 * 0.65
    samples = []
    h1, h2, h3 = harmonics
    for freq, dur, decay in notes:
        num_samples = int(sample_rate * dur)
        attack_samples = max(1, int(sample_rate * 0.014))
        release_samples = max(1, int(sample_rate * 0.032))
        for i in range(num_samples):
            if freq <= 0 or effective_vol <= 0.001:
                samples.append(0)
                continue
            t = i / sample_rate
            env = math.exp(-t * decay)
            if i < attack_samples:
                env *= i / attack_samples
            elif i > num_samples - release_samples:
                env *= (num_samples - i) / release_samples

            val = (
                h1 * math.sin(2.0 * math.pi * freq * t)
                + h2 * math.sin(2.0 * math.pi * (freq * 2.0) * t)
                + h3 * math.sin(2.0 * math.pi * (freq * 3.0) * t)
            )
            sample = max(-1.0, min(1.0, val * env * effective_vol))
            samples.append(int(sample * 32767))

    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack("<" + "h" * len(samples), *samples))


def scale_custom_wav_volume(src_path, dst_path, volume):
    try:
        with wave.open(src_path, "rb") as rf:
            params = rf.getparams()
            if params.sampwidth != 2:
                return src_path
            raw = rf.readframes(params.nframes)
        count = len(raw) // 2
        ints = struct.unpack("<" + "h" * count, raw)
        gain = max(0.0, min(1.0, volume))
        scaled = [max(-32768, min(32767, int(s * gain))) for s in ints]
        with wave.open(dst_path, "wb") as wf:
            wf.setparams(params)
            wf.writeframes(struct.pack("<" + "h" * count, *scaled))
        return dst_path
    except Exception:
        return src_path


class SoundManager:
    def __init__(self, sfx_dir, profile="Soft Glass", volume=0.30, enabled=True, custom_lost="", custom_online=""):
        self.sfx_dir = sfx_dir
        self.profile = profile if profile in SFX_PROFILES else "Soft Glass"
        self.volume = float(volume)
        self.enabled = bool(enabled)
        self.custom_lost = custom_lost
        self.custom_online = custom_online

        self.wav_lost = os.path.join(sfx_dir, "sfx_lost.wav")
        self.wav_online = os.path.join(sfx_dir, "sfx_online.wav")
        self.wav_warn = os.path.join(sfx_dir, "sfx_warn.wav")
        self.wav_custom_lost_vol = os.path.join(sfx_dir, "sfx_custom_lost_vol.wav")
        self.wav_custom_online_vol = os.path.join(sfx_dir, "sfx_custom_online_vol.wav")
        self.rebuild_files()

    def rebuild_files(self):
        if winsound:
            try:
                winsound.PlaySound(None, 0)
            except Exception:
                pass
        prof = SFX_PROFILES.get(self.profile, SFX_PROFILES["Soft Glass"])
        harmonics = prof["harmonics"]
        try:
            write_chime_wav(self.wav_lost, prof["lost"], harmonics, volume=self.volume)
            write_chime_wav(self.wav_online, prof["restored"], harmonics, volume=self.volume)
            write_chime_wav(self.wav_warn, prof["warn"], harmonics, volume=self.volume)
            if self.custom_lost and os.path.exists(self.custom_lost):
                scale_custom_wav_volume(self.custom_lost, self.wav_custom_lost_vol, self.volume)
            if self.custom_online and os.path.exists(self.custom_online):
                scale_custom_wav_volume(self.custom_online, self.wav_custom_online_vol, self.volume)
        except Exception:
            pass

    def play(self, kind, force=False):
        if (not self.enabled and not force) or not winsound or self.volume <= 0.001:
            return
        path = None
        if kind == "lost":
            if self.custom_lost and os.path.exists(self.custom_lost):
                path = self.wav_custom_lost_vol if os.path.exists(self.wav_custom_lost_vol) else self.custom_lost
            else:
                path = self.wav_lost
        elif kind == "restored":
            if self.custom_online and os.path.exists(self.custom_online):
                path = self.wav_custom_online_vol if os.path.exists(self.wav_custom_online_vol) else self.custom_online
            else:
                path = self.wav_online
        elif kind == "warn":
            path = self.wav_warn

        if path and os.path.exists(path):
            try:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception:
                pass