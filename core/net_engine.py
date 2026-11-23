import json
import re
import socket
import subprocess
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import psutil
from core.config import is_valid_ipv4, lookup_mac_vendor


def get_ping(target, timeout_ms=1000):
    try:
        output = subprocess.check_output(
            ["ping", "-n", "1", "-w", str(timeout_ms), target],
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            errors="ignore",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        match = re.search(r"(?:time|زمان|تایم)[\s]*[=<][\s]*([0-9]+)[\s]*ms", output, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match_fallback = re.search(r"[=<][\s]*([0-9]+)[\s]*ms", output, re.IGNORECASE)
        if match_fallback:
            return int(match_fallback.group(1))
    except Exception:
        pass
    return -1


def fetch_public_ip():
    endpoints = [
        "http://api.ipify.org",
        "http://icanhazip.com",
        "http://checkip.amazonaws.com",
        "https://api.ipify.org",
    ]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for ep in endpoints:
        try:
            url = f"{ep}?t={int(time.time())}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"})
            with opener.open(req, timeout=3) as resp:
                ip = resp.read().decode("utf-8", errors="ignore").strip()
                if is_valid_ipv4(ip):
                    return ip
        except Exception:
            continue

    try:
        out = subprocess.check_output(
            ["curl", "-s", "--max-time", "3", "http://api.ipify.org"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            universal_newlines=True,
            errors="ignore",
        ).strip()
        if is_valid_ipv4(out):
            return out
    except Exception:
        pass
    return None


def fetch_geo_for_ip(ip, cache):
    if not ip or ip in ("Loading...", "OFFLINE"):
        return ""
    if ip in cache and cache[ip]:
        return cache[ip]

    geo_apis = [
        (f"http://ip-api.com/json/{ip}?fields=status,countryCode,city", "countryCode", "city", "status", "success"),
        (f"https://get.geojs.io/v1/ip/geo/{ip}.json", "country_code", "city", None, None),
        (f"http://ipwho.is/{ip}", "country_code", "city", "success", True),
        (f"https://ipinfo.io/{ip}/json", "country", "city", None, None),
        (f"https://freeipapi.com/api/json/{ip}", "countryCode", "cityName", None, None),
    ]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    for api_url, country_key, city_key, ok_key, ok_val in geo_apis:
        try:
            req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
            with opener.open(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                if ok_key is not None and data.get(ok_key) != ok_val:
                    continue
                country = str(data.get(country_key) or "").strip()
                city = str(data.get(city_key) or "").strip()
                if not country and not city:
                    continue
                loc = f"{city}, {country}".strip(", ")
                if loc and loc != ",":
                    cache[ip] = loc
                    return loc
        except Exception:
            continue
    return ""


def get_active_network_apps():
    active_apps = set()
    try:
        for c in psutil.net_connections(kind="inet"):
            if c.status == "ESTABLISHED" and c.pid:
                try:
                    active_apps.add(psutil.Process(c.pid).name())
                except Exception:
                    pass
    except Exception:
        pass
    return active_apps


def run_dns_benchmark(dns_servers):
    results = []
    lock = threading.Lock()

    def test_one(item):
        pings = []
        for _ in range(3):
            p = get_ping(item["ip"])
            if p != -1:
                pings.append(p)
        loss = int(((3 - len(pings)) / 3) * 100)
        avg = int(sum(pings) / len(pings)) if pings else 9999
        with lock:
            results.append((item, avg, loss))

    threads = [threading.Thread(target=test_one, args=(it,)) for it in dns_servers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    results.sort(key=lambda x: (x[2], x[1]))
    return results


def run_route_check(targets):
    results = []
    lock = threading.Lock()

    def test_one(item):
        pings = []
        for _ in range(3):
            p = get_ping(item["host"])
            if p != -1:
                pings.append(p)
        loss = int(((3 - len(pings)) / 3) * 100)
        avg = int(sum(pings) / len(pings)) if pings else 9999
        jit = (
            int(sum(abs(pings[i] - pings[i - 1]) for i in range(1, len(pings))) / max(1, len(pings) - 1))
            if len(pings) >= 2
            else 0
        )
        with lock:
            results.append((item, avg, jit, loss))

    threads = [threading.Thread(target=test_one, args=(it,)) for it in targets]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    results.sort(key=lambda x: (x[3], x[1]))
    return results


def run_speedtest(is_alive_cb, progress_cb, duration_limit=5.0):
    test_urls = [
        "https://speed.cloudflare.com/__down?bytes=25000000",
        "https://proof.ovh.net/files/10Mb.dat",
        "http://ipv4.download.thinkbroadband.com/10MB.zip",
    ]
    total_bytes = 0
    peak_mbps = 0.0
    final_mbps = None

    for url in test_urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                start = time.perf_counter()
                last_ui = start
                window_bytes = 0
                window_start = start

                while is_alive_cb():
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    n = len(chunk)
                    total_bytes += n
                    window_bytes += n
                    now = time.perf_counter()
                    elapsed = now - start

                    if now - last_ui >= 0.35:
                        w_dt = max(0.05, now - window_start)
                        inst_mbps = (window_bytes * 8.0) / (w_dt * 1_000_000.0)
                        peak_mbps = max(peak_mbps, inst_mbps)
                        avg_mbps = (total_bytes * 8.0) / (max(0.1, elapsed) * 1_000_000.0)
                        progress_cb(avg_mbps, elapsed, duration_limit)
                        last_ui = now
                        window_bytes = 0
                        window_start = now

                    if elapsed >= duration_limit:
                        break

                total_elapsed = max(0.1, time.perf_counter() - start)
                if total_bytes > 50_000:
                    final_mbps = (total_bytes * 8.0) / (total_elapsed * 1_000_000.0)
                    peak_mbps = max(peak_mbps, final_mbps)
                    break
        except Exception:
            continue

    return final_mbps, peak_mbps


def get_local_network_info():
    local_ip, local_mac = None, ""
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    skip_kw = (
        "loopback", "vethernet", "vmware", "virtualbox", "tun", "tap",
        "wireguard", "wg", "vpn", "sing", "xray", "tailscale", "zerotier",
        "hyper-v", "wsl", "bluetooth",
    )
    candidates = []
    for iface, addr_list in addrs.items():
        st = stats.get(iface)
        if not st or not st.isup:
            continue
        low = iface.lower()
        is_virtual = any(k in low for k in skip_kw)
        ip4, mac = None, ""
        for a in addr_list:
            if a.family == socket.AF_INET and not a.address.startswith("127.") and not a.address.startswith("169.254."):
                ip4 = a.address
            elif getattr(psutil, "AF_LINK", -1) == a.family:
                mac = a.address.replace("-", ":").upper()
        if ip4:
            score = (0 if is_virtual else 10) + (5 if ip4.startswith("192.168.") else (3 if ip4.startswith("10.") else 1))
            candidates.append((score, ip4, mac, iface))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        _, local_ip, local_mac, _ = candidates[0]

    if not local_ip:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "192.168.1.100"

    prefix = ".".join(local_ip.split(".")[:3])
    gateway = f"{prefix}.1"
    try:
        out = subprocess.check_output(
            ["ipconfig"], stderr=subprocess.STDOUT, universal_newlines=True,
            errors="ignore", creationflags=subprocess.CREATE_NO_WINDOW
        )
        for line in out.splitlines():
            if "Gateway" in line or "Default Gateway" in line:
                m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                if m and m.group(1).startswith(prefix + "."):
                    gateway = m.group(1)
                    break
    except Exception:
        pass
    return local_ip, local_mac, prefix, gateway


def scan_lan_devices(lan_names, known_macs, is_first_scan):
    local_ip, local_mac, prefix, gateway = get_local_network_info()
    subnet_str = f"{prefix}.0/24"
    replied_ips = set()

    def fast_ping(ip):
        try:
            res = subprocess.run(
                ["ping", "-n", "1", "-w", "220", ip],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if res.returncode == 0:
                return ip
        except Exception:
            pass
        return None

    ips_to_scan = [f"{prefix}.{i}" for i in range(1, 255)]
    with ThreadPoolExecutor(max_workers=64) as ex:
        for r in ex.map(fast_ping, ips_to_scan):
            if r:
                replied_ips.add(r)

    found = {}
    try:
        arp_out = subprocess.check_output(
            ["arp", "-a"], stderr=subprocess.STDOUT, universal_newlines=True,
            errors="ignore", creationflags=subprocess.CREATE_NO_WINDOW
        )
        for line in arp_out.splitlines():
            m = re.match(r"^\s*(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})\s+(\S+)", line)
            if not m:
                continue
            ip, mac_raw, kind = m.group(1), m.group(2), m.group(3).lower()
            mac = mac_raw.replace("-", ":").upper()
            if not ip.startswith(prefix + "."):
                continue
            if ip.endswith(".0") or ip.endswith(".255") or mac == "FF:FF:FF:FF:FF:FF":
                continue
            if mac.startswith("01:00:5E") or mac.startswith("33:33:"):
                continue
            if kind == "dynamic" or ip == gateway or ip in replied_ips:
                found[ip] = mac
    except Exception:
        pass

    found[local_ip] = local_mac or "LOCAL-PC"

    hostnames = {}

    def resolve_host(ip):
        if ip == local_ip:
            return ip, socket.gethostname()
        try:
            name, _, _ = socket.gethostbyaddr(ip)
            return ip, name.split(".")[0]
        except Exception:
            return ip, ""

    with ThreadPoolExecutor(max_workers=24) as ex:
        for ip, hname in ex.map(resolve_host, list(found.keys())):
            hostnames[ip] = hname

    devices = []
    new_unknown = []

    for ip, mac in found.items():
        is_self = ip == local_ip
        is_router = ip == gateway
        custom_name = lan_names.get(mac, "")
        vendor = "This Computer" if is_self else lookup_mac_vendor(mac)
        host = hostnames.get(ip, "")
        display_name = custom_name or host or ("Wi-Fi Router / Modem" if is_router else "Unknown Device")

        is_new = (not is_first_scan) and (mac not in known_macs) and (not is_self) and (not is_router)
        if is_new and not custom_name:
            new_unknown.append((ip, display_name, vendor))

        if is_router:
            tag, sort_prio = "ROUTER", 0
        elif is_self:
            tag, sort_prio = "THIS PC", 1
        elif is_new:
            tag, sort_prio = "NEW", 2
        elif custom_name:
            tag, sort_prio = "KNOWN", 3
        else:
            tag, sort_prio = "ACTIVE", 4

        devices.append({
            "ip": ip, "mac": mac, "name": display_name, "host": host,
            "custom_name": custom_name, "vendor": vendor, "tag": tag,
            "sort_key": (sort_prio, int(ip.split(".")[-1])),
        })

    devices.sort(key=lambda d: d["sort_key"])
    return {
        "subnet": subnet_str,
        "devices": devices,
        "found_macs": set(found.values()),
        "new_unknown": new_unknown,
    }