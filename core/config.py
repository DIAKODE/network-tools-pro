import json
import os

APP_NAME = "Network Tools Pro"
APP_VERSION = "6.2.1"

COLOR_GREEN = "#10B981"
COLOR_YELLOW = "#F59E0B"
COLOR_ORANGE = "#F97316"
COLOR_RED = "#EF4444"

CORE_TARGETS = ["8.8.8.8", "4.2.2.4", "1.1.1.1", "google.com", "cloudflare.com"]
CUSTOM_TARGET_OPTION = "+ Custom Target..."

THEMES = {
    "Cyberpunk Dark": {
        "mode": "Dark",
        "bg": "#080B12",
        "card": "#101624",
        "card_elev": "#151D2F",
        "inner": "#0A0F1A",
        "border": "#1E293B",
        "accent1": "#00D2FF",
        "accent2": "#A855F7",
        "text": "#F8FAFC",
        "muted": "#64748B",
        "grid": "#1B2538",
        "tooltip_bg": "#090E18",
    },
    "Light Pro": {
        "mode": "Light",
        "bg": "#EEF2F6",
        "card": "#FFFFFF",
        "card_elev": "#F1F5F9",
        "inner": "#F8FAFC",
        "border": "#CBD5E1",
        "accent1": "#0284C7",
        "accent2": "#7C3AED",
        "text": "#0F172A",
        "muted": "#64748B",
        "grid": "#E2E8F0",
        "tooltip_bg": "#FFFFFF",
    },
    "Emerald Matrix": {
        "mode": "Dark",
        "bg": "#050C09",
        "card": "#0C1914",
        "card_elev": "#11241C",
        "inner": "#07110D",
        "border": "#1A352A",
        "accent1": "#10B981",
        "accent2": "#14B8A6",
        "text": "#ECFDF5",
        "muted": "#6EE7B7",
        "grid": "#132A20",
        "tooltip_bg": "#07140E",
    },
    "Crimson Neon": {
        "mode": "Dark",
        "bg": "#0D080A",
        "card": "#191014",
        "card_elev": "#23161C",
        "inner": "#110A0D",
        "border": "#361E28",
        "accent1": "#F43F5E",
        "accent2": "#F59E0B",
        "text": "#FFF1F2",
        "muted": "#A8828E",
        "grid": "#29161E",
        "tooltip_bg": "#150A0E",
    },
    "Oceanic Blue": {
        "mode": "Dark",
        "bg": "#060C18",
        "card": "#0E192D",
        "card_elev": "#142340",
        "inner": "#091120",
        "border": "#1D3256",
        "accent1": "#38BDF8",
        "accent2": "#6366F1",
        "text": "#F0F9FF",
        "muted": "#7CA1C9",
        "grid": "#162744",
        "tooltip_bg": "#081020",
    },
}

SFX_PROFILES = {
    "Soft Glass": {
        "lost": [(587.33, 0.16, 7.0), (440.00, 0.30, 5.5)],
        "restored": [(523.25, 0.12, 8.0), (659.25, 0.12, 8.0), (783.99, 0.28, 6.0)],
        "warn": [(740.00, 0.14, 9.0), (880.00, 0.20, 8.0)],
        "harmonics": (0.80, 0.16, 0.04),
    },
    "Cyber Radar": {
        "lost": [(490.0, 0.11, 9.5), (320.0, 0.24, 6.5)],
        "restored": [(540.0, 0.10, 9.5), (860.0, 0.22, 7.0)],
        "warn": [(780.0, 0.09, 12.0), (0.0, 0.04, 1.0), (780.0, 0.12, 10.0)],
        "harmonics": (0.68, 0.22, 0.10),
    },
    "Minimal Pop": {
        "lost": [(440.0, 0.09, 15.0), (310.0, 0.12, 14.0)],
        "restored": [(520.0, 0.08, 16.0), (760.0, 0.12, 14.0)],
        "warn": [(660.0, 0.10, 15.0)],
        "harmonics": (0.88, 0.12, 0.0),
    },
}

DEFAULT_DNS_LIST = [
    {"name": "Cloudflare", "ip": "1.1.1.1", "ip2": "1.0.0.1", "custom": False},
    {"name": "Google", "ip": "8.8.8.8", "ip2": "8.8.4.4", "custom": False},
    {"name": "Level3", "ip": "4.2.2.4", "ip2": "4.2.2.2", "custom": False},
    {"name": "Electro", "ip": "78.157.42.100", "ip2": "78.157.42.101", "custom": False},
    {"name": "Radar Game", "ip": "10.202.10.10", "ip2": "10.202.10.11", "custom": False},
    {"name": "Shecan", "ip": "178.22.122.100", "ip2": "185.51.200.2", "custom": False},
    {"name": "Quad9", "ip": "9.9.9.9", "ip2": "149.112.112.112", "custom": False},
    {"name": "OpenDNS", "ip": "208.67.222.222", "ip2": "208.67.220.220", "custom": False},
]

ROUTE_CHECK_TARGETS = [
    {"name": "Cloudflare Edge", "host": "1.1.1.1", "cat": "CDN"},
    {"name": "Google Global", "host": "8.8.8.8", "cat": "Web"},
    {"name": "Steam EU (Valve)", "host": "155.133.248.34", "cat": "Game"},
    {"name": "Riot Games EU", "host": "162.249.72.1", "cat": "Game"},
    {"name": "AWS Frankfurt", "host": "dynamodb.eu-central-1.amazonaws.com", "cat": "EU Cloud"},
    {"name": "GitHub", "host": "github.com", "cat": "Dev"},
    {"name": "Discord", "host": "discord.com", "cat": "Voice"},
    {"name": "Telegram DC4", "host": "149.154.167.91", "cat": "Chat"},
    {"name": "Twitch", "host": "twitch.tv", "cat": "Stream"},
]

MAC_VENDORS = {
    "00:1A:2B": "Ayecom", "00:50:56": "VMware", "00:0C:29": "VMware", "08:00:27": "VirtualBox",
    "DC:A6:32": "Raspberry Pi", "B8:27:EB": "Raspberry Pi", "E4:5F:01": "Raspberry Pi",
    "18:D6:C7": "TP-Link", "50:C7:BF": "TP-Link", "C0:25:E9": "TP-Link", "EC:08:6B": "TP-Link",
    "F4:F2:6D": "TP-Link", "98:DA:C4": "TP-Link", "54:AF:97": "TP-Link", "A4:2B:B0": "TP-Link",
    "1C:7E:E5": "D-Link", "28:10:7B": "D-Link", "B8:A3:86": "D-Link", "C8:BE:19": "D-Link",
    "F0:7D:68": "D-Link", "00:26:5A": "D-Link", "34:08:04": "D-Link",
    "4C:5E:0C": "MikroTik", "D4:CA:6D": "MikroTik", "E4:8D:8C": "MikroTik", "64:D1:54": "MikroTik",
    "00:1B:63": "Apple", "3C:15:C2": "Apple", "A4:5E:60": "Apple", "F0:18:98": "Apple",
    "28:CF:E9": "Apple", "D0:25:98": "Apple", "AC:BC:32": "Apple", "88:66:A5": "Apple",
    "00:23:39": "Samsung", "34:23:BA": "Samsung", "5C:0A:5B": "Samsung", "8C:77:12": "Samsung",
    "A0:CC:2B": "Samsung", "CC:07:AB": "Samsung", "F4:42:8F": "Samsung", "94:35:0A": "Samsung",
    "28:6C:07": "Xiaomi", "64:09:80": "Xiaomi", "78:11:DC": "Xiaomi", "F8:A4:5F": "Xiaomi",
    "04:CF:8C": "Xiaomi", "50:EC:50": "Xiaomi", "8C:BE:BE": "Xiaomi", "34:80:B3": "Xiaomi",
    "00:E0:FC": "Huawei", "24:09:95": "Huawei", "48:46:FB": "Huawei", "70:8C:B6": "Huawei",
    "C8:D1:5E": "Huawei", "E0:24:7F": "Huawei", "04:B0:E7": "Huawei",
    "00:D9:D1": "Sony / PS", "70:9E:29": "Sony / PS", "F8:46:1C": "Sony / PS",
    "C8:63:F1": "Sony / PS", "00:1F:A7": "Sony / PS", "A8:E3:EE": "Sony / PS",
    "00:15:5D": "Microsoft", "28:18:78": "Microsoft", "60:45:BD": "Microsoft",
    "00:1B:21": "Intel", "3C:97:0E": "Intel", "A4:34:D9": "Intel", "D8:F2:CA": "Intel",
    "00:E0:4C": "Realtek", "52:54:00": "QEMU / KVM", "04:D4:C4": "ASUS", "2C:FD:A1": "ASUS",
    "AC:9E:17": "ASUS", "18:31:BF": "ASUS", "C8:3A:35": "Tenda", "CC:2D:21": "Tenda",
    "24:6F:28": "Espressif IoT", "30:AE:A4": "Espressif IoT", "A4:CF:12": "Espressif IoT",
    "3C:5A:B4": "Google", "F4:F5:D8": "Google", "00:1C:62": "LG", "B4:E6:2A": "LG",
    "C0:EE:FB": "OnePlus", "94:65:2D": "OnePlus", "18:FE:34": "Espressif IoT",
    "D8:BB:C1": "MSI", "70:85:C2": "ASRock", "E0:D5:5E": "Gigabyte", "B4:2E:99": "Gigabyte",
}


def get_app_paths():
    app_dir = os.path.join(os.environ.get("APPDATA", "."), "DiakoPingMonitor")
    sfx_dir = os.path.join(app_dir, "sfx")
    os.makedirs(sfx_dir, exist_ok=True)
    config_path = os.path.join(app_dir, "config.json")
    app_icon_path = os.path.join(app_dir, "network_tools_pro.ico")
    return app_dir, sfx_dir, config_path, app_icon_path


def load_config(config_path):
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_config(config_path, data):
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def lookup_mac_vendor(mac):
    if not mac or len(mac) < 8:
        return "Unknown"
    mac_up = mac.replace("-", ":").upper()
    prefix = mac_up[:8]
    if prefix in MAC_VENDORS:
        return MAC_VENDORS[prefix]
    try:
        if int(mac_up[:2], 16) & 0x02:
            return "Mobile (Private MAC)"
    except Exception:
        pass
    return "Network Device"


def is_valid_ipv4(ip):
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if not part.isdigit() or not (0 <= int(part) <= 255):
            return False
    return True


def format_bytes(b):
    if b < 1024 * 1024:
        return f"{b / 1024:.1f} KB"
    if b < 1024 * 1024 * 1024:
        return f"{b / (1024 * 1024):.2f} MB"
    return f"{b / (1024 * 1024 * 1024):.2f} GB"


def get_health_color(ping):
    if ping == -1:
        return COLOR_RED
    if ping <= 110:
        return COLOR_GREEN
    if ping <= 160:
        return COLOR_YELLOW
    if ping <= 220:
        return COLOR_ORANGE
    return COLOR_RED


def get_health_tag(ping):
    if ping == -1:
        return "RED"
    if ping <= 110:
        return "GREEN"
    if ping <= 160:
        return "YELLOW"
    if ping <= 220:
        return "ORANGE"
    return "RED"


def get_quality_badge(ping, loss_pct):
    if ping == -1:
        return "OFFLINE", COLOR_RED
    if loss_pct >= 15 or ping > 220:
        return "POOR", COLOR_RED
    if loss_pct >= 5 or ping > 160:
        return "UNSTABLE", COLOR_ORANGE
    if ping > 110:
        return "FAIR", COLOR_YELLOW
    if ping <= 65 and loss_pct == 0:
        return "EXCELLENT", COLOR_GREEN
    return "GOOD", COLOR_GREEN