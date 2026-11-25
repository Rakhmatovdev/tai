"""Conservative local inference budgets and hardware detection for offline AI."""
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
import os
import shutil
import sys
import time

GIB = 1024**3


@dataclass(frozen=True)
class Resources:
    ram_free: int | None = None
    ram_total: int | None = None
    gpu_free: int | None = None
    gpu_total: int | None = None
    cpu_cores: int | None = None
    cpu_threads: int | None = None
    cpu_name: str = ''
    gpu_name: str = ''
    disk_free: int | None = None
    disk_total: int | None = None


@lru_cache(maxsize=1)
def gpu_backend():
    try:
        import pynvml
        pynvml.nvmlInit()
        return pynvml
    except Exception:
        return None


def sample_resources(probe_hardware: bool = False):
    ram_free = ram_total = gpu_free = gpu_total = None
    cpu_cores = cpu_threads = None
    cpu_name = gpu_name = ''
    disk_free = disk_total = None

    # RAM
    try:
        import psutil
        memory = psutil.virtual_memory()
        ram_free, ram_total = int(memory.available), int(memory.total)
    except Exception:
        pass

    # GPU
    try:
        nvml = gpu_backend()
        if nvml is not None:
            devices = []
            for i in range(nvml.nvmlDeviceGetCount()):
                handle = nvml.nvmlDeviceGetHandleByIndex(i)
                mem = nvml.nvmlDeviceGetMemoryInfo(handle)
                dev_name = ''
                if probe_hardware:
                    try:
                        raw = nvml.nvmlDeviceGetName(handle)
                        dev_name = raw.decode('utf-8', errors='ignore') if isinstance(raw, bytes) else str(raw)
                    except Exception:
                        pass
                devices.append((mem, dev_name))
            if devices:
                best_mem, best_name = max(devices, key=lambda item: item[0].free)
                gpu_free, gpu_total = int(best_mem.free), int(best_mem.total)
                gpu_name = best_name
    except Exception:
        pass

    if probe_hardware:
        # CPU cores and threads
        try:
            import psutil
            cpu_cores = psutil.cpu_count(logical=False)
            cpu_threads = psutil.cpu_count(logical=True)
        except Exception:
            pass

        # CPU model name
        try:
            if sys.platform == 'win32':
                try:
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                    val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                    if val:
                        cpu_name = str(val).strip()
                except Exception:
                    pass
            if not cpu_name:
                import platform
                cpu_name = platform.processor() or ''
        except Exception:
            pass

        # Disk free space in Ollama models directory
        try:
            models_dir = Path(os.environ.get('OLLAMA_MODELS', str(Path.home() / '.ollama' / 'models'))).expanduser()
            probe = models_dir
            while not probe.exists() and probe.parent != probe:
                probe = probe.parent
            usage = shutil.disk_usage(probe)
            disk_free, disk_total = int(usage.free), int(usage.total)
        except Exception:
            pass

    return Resources(
        ram_free=ram_free,
        ram_total=ram_total,
        gpu_free=gpu_free,
        gpu_total=gpu_total,
        cpu_cores=cpu_cores,
        cpu_threads=cpu_threads,
        cpu_name=cpu_name,
        gpu_name=gpu_name,
        disk_free=disk_free,
        disk_total=disk_total
    )


def sample_hardware():
    """Sample full notebook resources including CPU, GPU device name, and disk space."""
    return sample_resources(probe_hardware=True)


def suggested_profile(resources):
    """Conservative profile selection: memory alone cannot predict speed."""
    if resources.ram_free is None or resources.ram_free < 4*GIB:
        return 'economy'
    if resources.ram_total and resources.ram_free/resources.ram_total < .15:
        return 'economy'
    if resources.gpu_free is not None:
        if resources.gpu_free < GIB or (resources.gpu_total and resources.gpu_free/resources.gpu_total < .10):
            return 'economy'
    return 'balanced'


def hardware_tier(resources: Resources) -> str:
    """Classify hardware capability into: 'entry', 'mid', or 'high'."""
    vram_free = resources.gpu_free or 0
    vram_total = resources.gpu_total or 0
    ram_free = resources.ram_free or 0
    ram_total = resources.ram_total or 0
    if vram_total >= 6*GIB or vram_free >= 4*GIB or ram_total >= 24*GIB or ram_free >= 14*GIB:
        return 'high'
    if vram_total >= 4*GIB or vram_free >= 2*GIB or ram_total >= 12*GIB or ram_free >= 6*GIB:
        return 'mid'
    return 'entry'


def hardware_summary(resources: Resources) -> str:
    """Human-readable Uzbek summary of the notebook's hardware specs."""
    parts = []
    if resources.cpu_name:
        core_info = ''
        if resources.cpu_cores:
            core_info = f" ({resources.cpu_cores} yadro"
            if resources.cpu_threads and resources.cpu_threads != resources.cpu_cores:
                core_info += f", {resources.cpu_threads} oqim"
            core_info += ")"
        parts.append(f"CPU: {resources.cpu_name}{core_info}")
    elif resources.cpu_cores:
        parts.append(f"CPU: {resources.cpu_cores} yadro")

    if resources.ram_total is not None and resources.ram_free is not None:
        parts.append(f"RAM: {resources.ram_total/GIB:.1f} GB ({resources.ram_free/GIB:.1f} GB bo‘sh)")
    elif resources.ram_free is not None:
        parts.append(f"RAM: {resources.ram_free/GIB:.1f} GB bo‘sh")

    if resources.gpu_name:
        vram_info = ''
        if resources.gpu_total is not None and resources.gpu_free is not None:
            vram_info = f" ({resources.gpu_total/GIB:.1f} GB VRAM, {resources.gpu_free/GIB:.1f} GB bo‘sh)"
        elif resources.gpu_free is not None:
            vram_info = f" ({resources.gpu_free/GIB:.1f} GB VRAM)"
        parts.append(f"GPU: {resources.gpu_name}{vram_info}")
    elif resources.gpu_free is not None:
        parts.append(f"GPU VRAM: {resources.gpu_free/GIB:.1f} GB bo‘sh")

    if resources.disk_free is not None:
        parts.append(f"Disk: {resources.disk_free/GIB:.1f} GB bo‘sh")

    return ' · '.join(parts) if parts else "Noutbuk parametrlari aniqlanmoqda…"


def hardware_recommendation_text(resources: Resources) -> str:
    """Actionable Uzbek advice explaining which models suit this notebook best."""
    tier = hardware_tier(resources)
    vram = (resources.gpu_free or 0) / GIB
    ram = (resources.ram_free or 0) / GIB

    if tier == 'high':
        gpu_note = f" ({resources.gpu_name} {vram:.1f} GB VRAM)" if resources.gpu_name else ""
        return (
            f"Katta imkoniyatli noutbuk{gpu_note}. 7B–8B modellari (Qwen 2.5 7B, Llama 3.1 8B, DeepSeek R1 8B) "
            "GPU xotirasiga to‘liq sig‘adi va yuqori tezlikda ishlaydi. 14B modellar ham ishlatilishi mumkin."
        )
    elif tier == 'mid':
        return (
            f"O‘rtacha noutbuk ({ram:.1f} GB bo‘sh RAM). 3B–8B parametrli modellar (Llama 3.2 3B, Qwen 2.5 7B, Phi-3 Mini) "
            "tavsiya etiladi. Ular tezkor, sifatli va xotirani ortiqcha yuklamaydi."
        )
    else:
        return (
            f"Tejamkor noutbuk ({ram:.1f} GB bo‘sh RAM). Ixcham modellar tavsiya etiladi: Llama 3.2 (1B yoki 3B), "
            "Qwen 2.5 (1.5B yoki 3B). Ular protsessorda ham tezkor javob beradi."
        )


class AutoProfile:
    """Downshift promptly; wait a minute before increasing a recovered budget."""
    def __init__(self):
        self.current = None
        self.changed_at = 0

    def resolve(self, settings, resources, now=None):
        if settings.profile != 'auto':
            return settings
        now = time.monotonic() if now is None else now
        candidate = suggested_profile(resources)
        if candidate == 'economy':
            self.current, self.changed_at = candidate, now
        elif self.current is None or now-self.changed_at >= 60:
            if self.current != candidate:
                self.current, self.changed_at = candidate, now
        return replace(settings, profile=self.current)
