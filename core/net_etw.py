import ctypes
from ctypes import wintypes
import os
import threading
import time
import psutil

# ثابت‌های ETW ویندوز
WNODE_FLAG_TRACED_GUID = 0x00020000
EVENT_TRACE_REAL_TIME_MODE = 0x00000100
EVENT_TRACE_CONTROL_STOP = 1
EVENT_CONTROL_CODE_ENABLE_PROVIDER = 1
TRACE_LEVEL_INFORMATION = 4
PROCESS_TRACE_MODE_REAL_TIME = 0x00000100
PROCESS_TRACE_MODE_EVENT_RECORD = 0x10000000
INVALID_PROCESSTRACE_HANDLE = 0xFFFFFFFFFFFFFFFF

# Event IDs رسمی Microsoft-Windows-Kernel-Network (IPv4/IPv6 TCP & UDP)
SEND_EVENT_IDS = frozenset((10, 26, 42, 58))
RECV_EVENT_IDS = frozenset((11, 27, 43, 59))
SESSION_NAME = "NetworkToolsPro_NetETW"

# لیست پروسه‌های حیاتی ویندوز که نباید بسته شوند
PROTECTED_PROCESSES = frozenset({
    "system",
    "system idle process",
    "idle",
    "registry",
    "memory compression",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "winlogon.exe",
    "services.exe",
    "lsass.exe",
    "svchost.exe",
    "dwm.exe",
    "explorer.exe",
    "fontdrvhost.exe",
    "sihost.exe",
    "taskhostw.exe",
})


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


# Provider GUID: Microsoft-Windows-Kernel-Network {7dd42a49-5329-4832-8dfd-43d979153a88}
KERNEL_NETWORK_GUID = GUID(
    0x7DD42A49,
    0x5329,
    0x4832,
    (ctypes.c_ubyte * 8)(0x8D, 0xFD, 0x43, 0xD9, 0x79, 0x15, 0x3A, 0x88),
)


class WNODE_HEADER(ctypes.Structure):
    _fields_ = [
        ("BufferSize", wintypes.ULONG),
        ("ProviderId", wintypes.ULONG),
        ("HistoricalContext", ctypes.c_uint64),
        ("TimeStamp", ctypes.c_int64),
        ("Guid", GUID),
        ("ClientContext", wintypes.ULONG),
        ("Flags", wintypes.ULONG),
    ]


class EVENT_TRACE_PROPERTIES(ctypes.Structure):
    _fields_ = [
        ("Wnode", WNODE_HEADER),
        ("BufferSize", wintypes.ULONG),
        ("MinimumBuffers", wintypes.ULONG),
        ("MaximumBuffers", wintypes.ULONG),
        ("MaximumFileSize", wintypes.ULONG),
        ("LogFileMode", wintypes.ULONG),
        ("FlushTimer", wintypes.ULONG),
        ("EnableFlags", wintypes.ULONG),
        ("AgeLimit", wintypes.LONG),
        ("NumberOfBuffers", wintypes.ULONG),
        ("FreeBuffers", wintypes.ULONG),
        ("EventsLost", wintypes.ULONG),
        ("BuffersWritten", wintypes.ULONG),
        ("LogBuffersLost", wintypes.ULONG),
        ("RealTimeBuffersLost", wintypes.ULONG),
        ("LoggerThreadId", wintypes.HANDLE),
        ("LogFileNameOffset", wintypes.ULONG),
        ("LoggerNameOffset", wintypes.ULONG),
    ]


class EVENT_TRACE_PROPERTIES_BUF(ctypes.Structure):
    _fields_ = [
        ("Props", EVENT_TRACE_PROPERTIES),
        ("LoggerName", ctypes.c_wchar * 256),
        ("LogFileName", ctypes.c_wchar * 256),
    ]


class EVENT_DESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("Id", wintypes.USHORT),
        ("Version", ctypes.c_ubyte),
        ("Channel", ctypes.c_ubyte),
        ("Level", ctypes.c_ubyte),
        ("Opcode", ctypes.c_ubyte),
        ("Task", wintypes.USHORT),
        ("Keyword", ctypes.c_uint64),
    ]


class EVENT_HEADER(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.USHORT),
        ("HeaderType", wintypes.USHORT),
        ("Flags", wintypes.USHORT),
        ("EventProperty", wintypes.USHORT),
        ("ThreadId", wintypes.ULONG),
        ("ProcessId", wintypes.ULONG),
        ("TimeStamp", ctypes.c_int64),
        ("ProviderId", GUID),
        ("EventDescriptor", EVENT_DESCRIPTOR),
        ("ProcessorTime", ctypes.c_uint64),
        ("ActivityId", GUID),
    ]


class ETW_BUFFER_CONTEXT(ctypes.Structure):
    _fields_ = [
        ("ProcessorNumber", ctypes.c_ubyte),
        ("Alignment", ctypes.c_ubyte),
        ("LoggerId", wintypes.USHORT),
    ]


class EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("EventHeader", EVENT_HEADER),
        ("BufferContext", ETW_BUFFER_CONTEXT),
        ("ExtendedDataCount", wintypes.USHORT),
        ("UserDataLength", wintypes.USHORT),
        ("ExtendedData", ctypes.c_void_p),
        ("UserData", ctypes.c_void_p),
        ("UserContext", ctypes.c_void_p),
    ]


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", wintypes.WORD),
        ("wMonth", wintypes.WORD),
        ("wDayOfWeek", wintypes.WORD),
        ("wDay", wintypes.WORD),
        ("wHour", wintypes.WORD),
        ("wMinute", wintypes.WORD),
        ("wSecond", wintypes.WORD),
        ("wMilliseconds", wintypes.WORD),
    ]


class TIME_ZONE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Bias", wintypes.LONG),
        ("StandardName", ctypes.c_wchar * 32),
        ("StandardDate", SYSTEMTIME),
        ("StandardBias", wintypes.LONG),
        ("DaylightName", ctypes.c_wchar * 32),
        ("DaylightDate", SYSTEMTIME),
        ("DaylightBias", wintypes.LONG),
    ]


class TRACE_LOGFILE_HEADER(ctypes.Structure):
    _fields_ = [
        ("BufferSize", wintypes.ULONG),
        ("Version", wintypes.ULONG),
        ("ProviderVersion", wintypes.ULONG),
        ("NumberOfProcessors", wintypes.ULONG),
        ("EndTime", ctypes.c_int64),
        ("TimerResolution", wintypes.ULONG),
        ("MaximumFileSize", wintypes.ULONG),
        ("LogFileMode", wintypes.ULONG),
        ("BuffersWritten", wintypes.ULONG),
        ("LogInstanceGuid", GUID),
        ("LoggerName", wintypes.LPWSTR),
        ("LogFileName", wintypes.LPWSTR),
        ("TimeZone", TIME_ZONE_INFORMATION),
        ("BootTime", ctypes.c_int64),
        ("PerfFreq", ctypes.c_int64),
        ("StartTime", ctypes.c_int64),
        ("ReservedFlags", wintypes.ULONG),
        ("BuffersLost", wintypes.ULONG),
    ]


class EVENT_TRACE_HEADER(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.USHORT),
        ("HeaderType", wintypes.USHORT),
        ("Version", wintypes.ULONG),
        ("ThreadId", wintypes.ULONG),
        ("ProcessId", wintypes.ULONG),
        ("TimeStamp", ctypes.c_int64),
        ("Guid", GUID),
        ("ProcessorTime", ctypes.c_uint64),
    ]


class EVENT_TRACE(ctypes.Structure):
    _fields_ = [
        ("Header", EVENT_TRACE_HEADER),
        ("InstanceId", wintypes.ULONG),
        ("ParentInstanceId", wintypes.ULONG),
        ("ParentGuid", GUID),
        ("MofData", ctypes.c_void_p),
        ("MofLength", wintypes.ULONG),
        ("ClientContext", wintypes.ULONG),
    ]


EVENT_RECORD_CALLBACK = ctypes.WINFUNCTYPE(None, ctypes.POINTER(EVENT_RECORD))
BUFFER_CALLBACK = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)


class EVENT_TRACE_LOGFILEW(ctypes.Structure):
    _fields_ = [
        ("LogFileName", wintypes.LPWSTR),
        ("LoggerName", wintypes.LPWSTR),
        ("CurrentTime", ctypes.c_int64),
        ("BuffersRead", wintypes.ULONG),
        ("ProcessTraceMode", wintypes.ULONG),
        ("CurrentEvent", EVENT_TRACE),
        ("LogfileHeader", TRACE_LOGFILE_HEADER),
        ("BufferCallback", BUFFER_CALLBACK),
        ("BufferSize", wintypes.ULONG),
        ("Filled", wintypes.ULONG),
        ("EventsLost", wintypes.ULONG),
        ("EventRecordCallback", EVENT_RECORD_CALLBACK),
        ("IsKernelTrace", wintypes.ULONG),
        ("Context", ctypes.c_void_p),
    ]


def _setup_advapi():
    adv = ctypes.windll.advapi32
    adv.ControlTraceW.argtypes = [
        ctypes.c_uint64,
        wintypes.LPCWSTR,
        ctypes.POINTER(EVENT_TRACE_PROPERTIES),
        wintypes.ULONG,
    ]
    adv.ControlTraceW.restype = wintypes.ULONG

    adv.StartTraceW.argtypes = [
        ctypes.POINTER(ctypes.c_uint64),
        wintypes.LPCWSTR,
        ctypes.POINTER(EVENT_TRACE_PROPERTIES),
    ]
    adv.StartTraceW.restype = wintypes.ULONG

    adv.EnableTraceEx2.argtypes = [
        ctypes.c_uint64,
        ctypes.POINTER(GUID),
        wintypes.ULONG,
        ctypes.c_ubyte,
        ctypes.c_uint64,
        ctypes.c_uint64,
        wintypes.ULONG,
        ctypes.c_void_p,
    ]
    adv.EnableTraceEx2.restype = wintypes.ULONG

    adv.OpenTraceW.argtypes = [ctypes.POINTER(EVENT_TRACE_LOGFILEW)]
    adv.OpenTraceW.restype = ctypes.c_uint64

    adv.ProcessTrace.argtypes = [
        ctypes.POINTER(ctypes.c_uint64),
        wintypes.ULONG,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    adv.ProcessTrace.restype = wintypes.ULONG

    adv.CloseTrace.argtypes = [ctypes.c_uint64]
    adv.CloseTrace.restype = wintypes.ULONG
    return adv


class PerAppNetworkMonitor:
    """
    مانیتور سبک مصرف شبکه به تفکیک هر برنامه:
    - در حالت Admin: از کرنل ETW ویندوز برای خواندن سرعت لحظه‌ای Download/Upload و حجم کل استفاده می‌کند.
    - در حالت عادی: لیست برنامه‌های متصل را از psutil می‌گیرد و دکمه KILL همچنان کار می‌کند.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._own_pid = os.getpid()
        self._running = False
        self._etw_active = False

        self._session_handle = ctypes.c_uint64(0)
        self._trace_handle = ctypes.c_uint64(INVALID_PROCESSTRACE_HANDLE)
        self._thread = None
        self._adv = None

        # بافر خام بایت‌ها از زمان آخرین خوانش (key = pid -> [dl_bytes, ul_bytes])
        self._interval_bytes = {}
        # آمار تجمیعی نشست به تفکیک نام برنامه (key = name.lower())
        self._app_totals = {}  # key -> {"name": str, "dl": int, "ul": int, "last_seen": float}
        # کش سریع PID -> نام برنامه
        self._pid_cache = {}  # pid -> (name, timestamp)
        self._last_snapshot_ts = time.monotonic()

        # نگه داشتن رفرنس قوی برای جلوگیری از آزاد شدن توسط GC
        self._event_cb = None
        self._buffer_cb = None
        self._logfile = None
        self._session_name_buf = None

    @property
    def is_etw_active(self) -> bool:
        return self._etw_active

    def _make_props(self):
        buf = EVENT_TRACE_PROPERTIES_BUF()
        buf.Props.Wnode.BufferSize = ctypes.sizeof(EVENT_TRACE_PROPERTIES_BUF)
        buf.Props.Wnode.Flags = WNODE_FLAG_TRACED_GUID
        buf.Props.Wnode.ClientContext = 1  # QPC
        buf.Props.BufferSize = 64  # KB
        buf.Props.MinimumBuffers = 4
        buf.Props.MaximumBuffers = 32
        buf.Props.LogFileMode = EVENT_TRACE_REAL_TIME_MODE
        buf.Props.FlushTimer = 1  # فلاش هر ۱ ثانیه برای نمایش زنده بدون تأخیر
        buf.Props.LoggerNameOffset = ctypes.sizeof(EVENT_TRACE_PROPERTIES)
        buf.Props.LogFileNameOffset = 0
        buf.LoggerName = SESSION_NAME
        return buf

    def start(self) -> bool:
        if self._running:
            return self._etw_active

        try:
            if not ctypes.windll.shell32.IsUserAnAdmin():
                return False
        except Exception:
            return False

        try:
            self._adv = _setup_advapi()

            # اگر نشست قبلی از کرش یا اجرای قبلی باقی مانده، اول متوقفش کن
            stop_buf = self._make_props()
            self._adv.ControlTraceW(0, SESSION_NAME, ctypes.byref(stop_buf.Props), EVENT_TRACE_CONTROL_STOP)

            start_buf = self._make_props()
            session_handle = ctypes.c_uint64(0)
            status = self._adv.StartTraceW(
                ctypes.byref(session_handle),
                SESSION_NAME,
                ctypes.byref(start_buf.Props),
            )
            if status != 0:
                return False

            self._session_handle = session_handle

            # فعال‌سازی Provider شبکه کرنل (IPv4=0x10 و IPv6=0x20)
            status = self._adv.EnableTraceEx2(
                self._session_handle,
                ctypes.byref(KERNEL_NETWORK_GUID),
                EVENT_CONTROL_CODE_ENABLE_PROVIDER,
                TRACE_LEVEL_INFORMATION,
                0x30,
                0,
                0,
                None,
            )
            if status != 0:
                self._stop_session()
                return False

            self._running = True
            self._event_cb = EVENT_RECORD_CALLBACK(self._on_event)
            self._buffer_cb = BUFFER_CALLBACK(self._on_buffer)
            self._session_name_buf = ctypes.create_unicode_buffer(SESSION_NAME)

            self._logfile = EVENT_TRACE_LOGFILEW()
            self._logfile.LoggerName = ctypes.cast(self._session_name_buf, wintypes.LPWSTR)
            self._logfile.ProcessTraceMode = PROCESS_TRACE_MODE_REAL_TIME | PROCESS_TRACE_MODE_EVENT_RECORD
            self._logfile.EventRecordCallback = self._event_cb
            self._logfile.BufferCallback = self._buffer_cb

            trace_handle = self._adv.OpenTraceW(ctypes.byref(self._logfile))
            if trace_handle == INVALID_PROCESSTRACE_HANDLE:
                self._running = False
                self._stop_session()
                return False

            self._trace_handle = ctypes.c_uint64(trace_handle)
            self._etw_active = True

            self._thread = threading.Thread(target=self._process_loop, daemon=True)
            self._thread.start()
            return True
        except Exception:
            self._running = False
            self._etw_active = False
            self._stop_session()
            return False

    def _on_buffer(self, _logfile_ptr):
        return 1 if self._running else 0

    def _on_event(self, record_ptr):
        if not self._running:
            return
        try:
            rec = record_ptr.contents
            ev_id = rec.EventHeader.EventDescriptor.Id
            is_recv = ev_id in RECV_EVENT_IDS
            if not is_recv and ev_id not in SEND_EVENT_IDS:
                return

            if not rec.UserData or rec.UserDataLength < 8:
                return

            # در Microsoft-Windows-Kernel-Network دو فیلد اول همیشه PID و Size هستند
            vals = ctypes.cast(rec.UserData, ctypes.POINTER(ctypes.c_uint32))
            pid = int(vals[0])
            size = int(vals[1])
            if size <= 0:
                return

            if pid == 0:
                hdr_pid = int(rec.EventHeader.ProcessId)
                if 0 < hdr_pid < 0xFFFFFFFF:
                    pid = hdr_pid

            with self._lock:
                entry = self._interval_bytes.get(pid)
                if entry is None:
                    self._interval_bytes[pid] = [size, 0] if is_recv else [0, size]
                else:
                    if is_recv:
                        entry[0] += size
                    else:
                        entry[1] += size
        except Exception:
            pass

    def _process_loop(self):
        try:
            handle_arr = (ctypes.c_uint64 * 1)(self._trace_handle.value)
            self._adv.ProcessTrace(handle_arr, 1, None, None)
        except Exception:
            pass
        finally:
            self._etw_active = False

    def _stop_session(self):
        if not self._adv:
            return
        try:
            if self._trace_handle.value != INVALID_PROCESSTRACE_HANDLE:
                self._adv.CloseTrace(self._trace_handle.value)
                self._trace_handle = ctypes.c_uint64(INVALID_PROCESSTRACE_HANDLE)
        except Exception:
            pass
        try:
            stop_buf = self._make_props()
            self._adv.ControlTraceW(0, SESSION_NAME, ctypes.byref(stop_buf.Props), EVENT_TRACE_CONTROL_STOP)
        except Exception:
            pass
        self._session_handle = ctypes.c_uint64(0)

    def stop(self):
        self._running = False
        self._etw_active = False
        self._stop_session()

    def reset_totals(self):
        with self._lock:
            self._app_totals.clear()
            self._interval_bytes.clear()

    def _resolve_pid_name(self, pid: int, now: float) -> str:
        if pid == 4:
            return "System"
        if pid == 0:
            return "System"

        cached = self._pid_cache.get(pid)
        if cached and (now - cached[1]) < 8.0:
            return cached[0]

        name = None
        try:
            name = psutil.Process(pid).name()
        except Exception:
            name = cached[0] if cached else f"PID {pid}"

        if len(self._pid_cache) > 500:
            self._pid_cache = {k: v for k, v in self._pid_cache.items() if (now - v[1]) < 15.0}
        self._pid_cache[pid] = (name, now)
        return name

    def get_snapshot(self, limit: int = 22) -> list[dict]:
        """
        برگرداندن لیست مرتب‌شده برنامه‌ها:
        [{"name", "key", "dl_bps", "ul_bps", "total_dl", "total_ul", "conns", "protected"}, ...]
        """
        now = time.monotonic()
        dt = max(0.25, now - self._last_snapshot_ts)
        self._last_snapshot_ts = now

        # ۱. برداشتن بایت‌های جمع‌شده از ETW
        with self._lock:
            raw_delta = self._interval_bytes
            self._interval_bytes = {}

        interval_by_app = {}  # key -> [display_name, dl_bytes, ul_bytes]
        for pid, (dl_b, ul_b) in raw_delta.items():
            name = self._resolve_pid_name(pid, now)
            key = name.lower()
            cur = interval_by_app.get(key)
            if cur is None:
                interval_by_app[key] = [name, dl_b, ul_b]
            else:
                cur[1] += dl_b
                cur[2] += ul_b

        # ۲. شمارش اتصالات فعال از psutil (در هر دو حالت Admin و عادی کار می‌کند)
        conns_by_app = {}  # key -> [display_name, conn_count, has_own_pid]
        try:
            for c in psutil.net_connections(kind="inet"):
                if not c.pid:
                    continue
                if c.status not in ("ESTABLISHED", "SYN_SENT", "CLOSE_WAIT"):
                    continue
                name = self._resolve_pid_name(c.pid, now)
                key = name.lower()
                item = conns_by_app.get(key)
                is_self = c.pid == self._own_pid
                if item is None:
                    conns_by_app[key] = [name, 1, is_self]
                else:
                    item[1] += 1
                    if is_self:
                        item[2] = True
        except Exception:
            pass

        # ۳. به‌روزرسانی آمار تجمیعی و ساخت ردیف‌های خروجی
        own_name_key = self._resolve_pid_name(self._own_pid, now).lower()
        all_keys = set(interval_by_app.keys()) | set(conns_by_app.keys())

        with self._lock:
            for key, (name, dl_b, ul_b) in interval_by_app.items():
                tot = self._app_totals.get(key)
                if tot is None:
                    self._app_totals[key] = {"name": name, "dl": dl_b, "ul": ul_b, "last_seen": now}
                else:
                    tot["dl"] += dl_b
                    tot["ul"] += ul_b
                    tot["last_seen"] = now

            # نگه داشتن برنامه‌هایی که تا ۱۵ ثانیه پیش مصرف داشته‌اند تا لیست پرش نکند
            for key, tot in list(self._app_totals.items()):
                if (now - tot["last_seen"]) <= 15.0:
                    all_keys.add(key)

            rows = []
            for key in all_keys:
                dl_b = interval_by_app[key][1] if key in interval_by_app else 0
                ul_b = interval_by_app[key][2] if key in interval_by_app else 0
                conn_info = conns_by_app.get(key)
                conns = conn_info[1] if conn_info else 0
                is_self = (conn_info[2] if conn_info else False) or (key == own_name_key)

                tot = self._app_totals.get(key)
                name = (
                    (interval_by_app[key][0] if key in interval_by_app else None)
                    or (conn_info[0] if conn_info else None)
                    or (tot["name"] if tot else key)
                )

                rows.append({
                    "name": name,
                    "key": key,
                    "dl_bps": dl_b / dt,
                    "ul_bps": ul_b / dt,
                    "total_dl": tot["dl"] if tot else 0,
                    "total_ul": tot["ul"] if tot else 0,
                    "conns": conns,
                    "protected": (key in PROTECTED_PROCESSES) or is_self,
                })

        # مرتب‌سازی: اول بیشترین سرعت لحظه‌ای، بعد مجموع مصرف، بعد تعداد اتصال
        rows.sort(
            key=lambda r: (
                round(r["dl_bps"] + r["ul_bps"], 1),
                r["total_dl"] + r["total_ul"],
                r["conns"],
                r["name"].lower(),
            ),
            reverse=True,
        )
        return rows[:limit]
