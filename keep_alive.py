# keep_alive.py - Servidor Flask para mantener el bot activo
from flask import Flask, jsonify
from threading import Thread
import ctypes
import os
import shutil
import subprocess

# Aplicación Flask para el monitoreo
app = Flask('')


def _get_ram_usage_percent():
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
            return int(memory_status.dwMemoryLoad)
    except Exception:
        pass

    try:
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", "r", encoding="utf-8") as file:
                meminfo = file.read()

            total_match = None
            available_match = None
            for line in meminfo.splitlines():
                if line.startswith("MemTotal:"):
                    total_match = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    available_match = int(line.split()[1])

            if total_match and available_match is not None and total_match > 0:
                used = total_match - available_match
                return round((used / total_match) * 100, 1)
    except Exception:
        pass

    return None


def _get_storage_usage_percent(path: str = "."):
    try:
        total, used, _ = shutil.disk_usage(path)
        if total <= 0:
            return None
        return round((used / total) * 100, 1)
    except Exception:
        return None


def _get_gpu_usage_percent():
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return "No disponible"

        values = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                values.append(float(line))
            except ValueError:
                continue

        if not values:
            return "No disponible"

        return f"{round(sum(values) / len(values), 1)}%"
    except Exception:
        return "No disponible"

@app.route('/')
def home():
    ram = _get_ram_usage_percent()
    storage = _get_storage_usage_percent(".")
    gpu = _get_gpu_usage_percent()

    return jsonify(
        {
            "estado": "El bot está en línea",
            "metricas": {
                "ram": f"{ram}%" if ram is not None else "No disponible",
                "gpu": gpu,
                "almacenamiento": f"{storage}%" if storage is not None else "No disponible",
            },
        }
    )

def run():
    # Ejecutar el servidor web en el puerto 8080 o en el host especificado
    app.run(host='0.0.0.0', port=8080)

# Inicializar un hilo separado para ejecutar el servidor web
def keep_alive():
    t = Thread(target=run)
    t.start()
