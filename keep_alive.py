# keep_alive.py - Servidor Flask para mantener el bot activo
from flask import Flask, jsonify
from threading import Thread
import ctypes
import datetime
import os
from pathlib import Path
import shutil
import time

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

try:
    import psutil
except Exception:
    psutil = None

app = Flask('')

PROJECT_ROOT = Path(__file__).resolve().parent
CLEANUP_INTERVAL_SECONDS = 6 * 60 * 60
METRICS_CACHE_TTL_SECONDS = 5

_last_cleanup_ts = 0.0
_last_cleanup_summary = {"archivos_eliminados": 0, "carpetas_eliminadas": 0}
_last_metrics_ts = 0.0
_last_metrics = None
EL_SALVADOR_TZ = ZoneInfo("America/El_Salvador") if ZoneInfo is not None else datetime.timezone(datetime.timedelta(hours=-6))


def _format_bytes(num_bytes: int | float | None):
    if num_bytes is None:
        return "No disponible"

    size_mb = float(num_bytes) / (1024 ** 2)
    return f"{size_mb:.1f} MB"


def _safe_percent(used: int | float, total: int | float):
    if not total:
        return "No disponible"
    return f"{(used / total) * 100:.1f}%"


def _get_ram_metrics():
    if psutil is not None:
        try:
            mem = psutil.virtual_memory()
            return {
                "usada": _format_bytes(mem.used),
                "total": _format_bytes(mem.total),
                "libre": _format_bytes(mem.available),
                "porcentaje_usado": f"{mem.percent:.1f}%",
            }
        except Exception:
            pass

    try:
        if hasattr(ctypes, "windll"):
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            memory_status = MEMORYSTATUSEX()
            memory_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status))
            used = memory_status.ullTotalPhys - memory_status.ullAvailPhys
            total = memory_status.ullTotalPhys
            free = memory_status.ullAvailPhys
            return {
                "usada": _format_bytes(used),
                "total": _format_bytes(total),
                "libre": _format_bytes(free),
                "porcentaje_usado": _safe_percent(used, total),
            }
    except Exception:
        pass

    try:
        if os.path.exists("/proc/meminfo"):
            meminfo = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as file:
                for line in file:
                    if ":" not in line:
                        continue
                    key, value = line.split(":", 1)
                    meminfo[key.strip()] = int(value.strip().split()[0])

            total_kb = meminfo.get("MemTotal")
            available_kb = meminfo.get("MemAvailable")
            if total_kb and available_kb is not None:
                used_kb = total_kb - available_kb
                return {
                    "usada": _format_bytes(used_kb * 1024),
                    "total": _format_bytes(total_kb * 1024),
                    "libre": _format_bytes(available_kb * 1024),
                    "porcentaje_usado": _safe_percent(used_kb, total_kb),
                }
    except Exception:
        pass

    return {
        "usada": "No disponible",
        "total": "No disponible",
        "libre": "No disponible",
        "porcentaje_usado": "No disponible",
    }


def _get_storage_metrics(path: str = "."):
    try:
        usage = shutil.disk_usage(path)
        return {
            "usado": _format_bytes(usage.used),
            "total": _format_bytes(usage.total),
            "libre": _format_bytes(usage.free),
            "porcentaje_usado": _safe_percent(usage.used, usage.total),
        }
    except Exception:
        return {
            "usado": "No disponible",
            "total": "No disponible",
            "libre": "No disponible",
            "porcentaje_usado": "No disponible",
        }


def _get_cpu_metrics():
    cpu_percent = None
    if psutil is not None:
        try:
            cpu_percent = psutil.cpu_percent(interval=0.2)
        except Exception:
            cpu_percent = None

    load_text = "No disponible"
    try:
        if hasattr(os, "getloadavg"):
            load_1m, load_5m, load_15m = os.getloadavg()
            load_text = f"1m={load_1m:.2f}, 5m={load_5m:.2f}, 15m={load_15m:.2f}"
    except Exception:
        pass

    if cpu_percent is None:
        cpu_usage = "No disponible"
    else:
        cpu_usage = f"{cpu_percent:.1f}%"

    return {
        "uso": cpu_usage,
        "carga": load_text,
    }


def _cleanup_transient_files():
    deleted_files = 0
    deleted_dirs = 0

    ignore_roots = {".git", ".venv"}

    for pycache_dir in PROJECT_ROOT.rglob("__pycache__"):
        if any(part in ignore_roots for part in pycache_dir.parts):
            continue
        try:
            shutil.rmtree(pycache_dir)
            deleted_dirs += 1
        except Exception:
            pass

    for ext in ("*.pyc", "*.pyo"):
        for file_path in PROJECT_ROOT.rglob(ext):
            if any(part in ignore_roots for part in file_path.parts):
                continue
            try:
                file_path.unlink(missing_ok=True)
                deleted_files += 1
            except Exception:
                pass

    return {
        "archivos_eliminados": deleted_files,
        "carpetas_eliminadas": deleted_dirs,
    }


def _run_periodic_maintenance():
    global _last_cleanup_ts, _last_cleanup_summary

    now = time.time()
    if (now - _last_cleanup_ts) < CLEANUP_INTERVAL_SECONDS:
        return

    # Mantenimiento seguro: solo elimina artefactos temporales de Python.
    _last_cleanup_summary = _cleanup_transient_files()
    _last_cleanup_ts = now


def _collect_metrics():
    global _last_metrics_ts, _last_metrics

    now = time.time()
    if _last_metrics is not None and (now - _last_metrics_ts) < METRICS_CACHE_TTL_SECONDS:
        return _last_metrics

    _last_metrics = {
        "cpu": _get_cpu_metrics(),
        "ram": _get_ram_metrics(),
        "almacenamiento": _get_storage_metrics("."),
    }
    _last_metrics_ts = now
    return _last_metrics


def _get_timestamp_fields():
    now_sv = datetime.datetime.now(EL_SALVADOR_TZ)
    return {
        "actualizado_en": now_sv.isoformat(timespec="seconds"),
        "actualizado_en_12h": now_sv.strftime("%Y-%m-%d %I:%M:%S %p"),
    }

@app.route('/')
def home():
    _run_periodic_maintenance()
    metrics = _collect_metrics()
    timestamps = _get_timestamp_fields()

    return jsonify(
        {
            "estado": "El bot está en línea",
            "actualizado_en": timestamps["actualizado_en"],
            "actualizado_en_12h": timestamps["actualizado_en_12h"],
            "metricas": metrics,
        }
    )

def run():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()
