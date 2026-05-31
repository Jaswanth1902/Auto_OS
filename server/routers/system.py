from fastapi import APIRouter, HTTPException
import psutil
import json
import asyncio
from pathlib import Path
from datetime import datetime
from agent.bus import manager
from utils.logger import api_logger as logger
import sys
import subprocess

router = APIRouter(prefix="/system", tags=["System"])

@router.get("/health")
async def get_system_health():
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    battery = psutil.sensors_battery()

    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            if info['cpu_percent'] is not None:
                processes.append({
                    "pid": info['pid'],
                    "name": info['name'],
                    "cpu_percent": round(info['cpu_percent'], 1),
                    "memory_percent": round(info['memory_percent'] or 0.0, 1),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    processes = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:15]

    return {
        "cpu": cpu,
        "ram": ram,
        "battery": {
            "percent": battery.percent if battery else 100,
            "power_plugged": battery.power_plugged if battery else True
        } if battery else None,
        "disk": psutil.disk_usage('/').percent,
        "processes": processes,
    }

async def background_heartbeat():
    """
    Proactive Guardian Mode: Checks system status every 60 seconds
    and broadcasts alerts to the UI.
    """
    while True:
        try:
            # Check CPU
            cpu = psutil.cpu_percent(interval=1)
            if cpu > 90:
                await manager.broadcast({
                    "type": "guardian_alert",
                    "message": f"High CPU Load detected ({cpu}%). Suggest closing background apps."
                })

            # Check Battery
            battery = psutil.sensors_battery()
            if battery and battery.percent < 20 and not battery.power_plugged:
                await manager.broadcast({
                    "type": "guardian_alert",
                    "message": f"Low Battery ({battery.percent}%). Please connect a charger."
                })

            # Check Thermals (Windows)
            if sys.platform == "win32":
                try:
                    # Windows Management Instrumentation (WMI) query for thermal zones
                    # Returns temperature in tenths of degrees Kelvin
                    cmd = ['powershell', '-Command', 'Get-WmiObject -Namespace root\\wmi -Class MSAcpi_ThermalZoneTemperature | Select-Object -ExpandProperty CurrentTemperature']
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.stdout.strip():
                        # Pick the highest temp reading from any zone
                        temps = [int(x) for x in result.stdout.strip().split() if x.isdigit()]
                        if temps:
                            max_temp_k = max(temps)
                            temp_c = (max_temp_k / 10.0) - 273.15
                            if temp_c > 85.0:
                                await manager.broadcast({
                                    "type": "guardian_alert",
                                    "message": f"High System Temperature detected ({temp_c:.1f}°C). Ensure ventilation is clear."
                                })
                except Exception as e:
                    logger.debug(f"Failed to query Windows thermals: {e}")

        except Exception as e:
            logger.error(f"Heartbeat error: {e}")

        await asyncio.sleep(60)

@router.post("/processes/kill")
async def kill_process_api(data: dict):
    from agent.nodes.executor import kill_process
    target = data.get("target")
    if not target:
        raise HTTPException(status_code=400, detail="Missing target process name or PID")

    result = kill_process(str(target))
    if "Failed" in result or "No active" in result:
        raise HTTPException(status_code=400, detail=result)
    return {"message": result}
