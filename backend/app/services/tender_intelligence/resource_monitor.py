"""Resource and Telemetry Monitoring Service for MYGPT Pipeline.

Captures stage-level resource usage:
- Timestamps and elapsed duration
- Process Resident Set Size (RSS) and Virtual Memory Size (VMS)
- System available RAM
- CPU utilization percentage
- Process thread count
- Batch indexing and vector metrics

Strictly guarantees that no tender text, chunk strings, or embedding data are retained.
"""

import os
import time
from typing import Any, Dict, Optional
import psutil
from loguru import logger


class ResourceSnapshot:
    """Immutable point-in-time snapshot of system and process resource metrics."""

    def __init__(self) -> None:
        self.timestamp = time.time()
        self.time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        vm = psutil.virtual_memory()

        self.rss_mb = round(mem.rss / (1024 * 1024), 2)
        self.vms_mb = round(mem.vms / (1024 * 1024), 2)
        self.system_avail_ram_gb = round(vm.available / (1024 ** 3), 2)
        self.system_total_ram_gb = round(vm.total / (1024 ** 3), 2)
        self.cpu_percent = psutil.cpu_percent(interval=None)
        self.num_threads = proc.num_threads()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.time_str,
            "rss_mb": self.rss_mb,
            "vms_mb": self.vms_mb,
            "system_avail_ram_gb": self.system_avail_ram_gb,
            "system_total_ram_gb": self.system_total_ram_gb,
            "cpu_percent": self.cpu_percent,
            "num_threads": self.num_threads,
        }


class ResourceMonitor:
    """Manages telemetry collection across all 10 stages of tender intelligence."""

    @staticmethod
    def capture() -> ResourceSnapshot:
        return ResourceSnapshot()

    @staticmethod
    def log_stage(
        stage_name: str,
        start_time: float,
        extra: Optional[Dict[str, Any]] = None,
    ) -> ResourceSnapshot:
        """Logs a standardized single-line resource telemetry record for a pipeline stage."""
        elapsed = round(time.time() - start_time, 3)
        snap = ResourceSnapshot()

        extra_str = ""
        if extra:
            # Format extra metadata cleanly (e.g. batch_num, chunks, vectors)
            formatted_items = [f"{k}={v}" for k, v in extra.items() if v is not None]
            if formatted_items:
                extra_str = " | " + " ".join(formatted_items)

        logger.info(
            f"[RESOURCE_TELEMETRY] stage='{stage_name}' elapsed={elapsed:.3f}s "
            f"rss_mb={snap.rss_mb} avail_ram_gb={snap.system_avail_ram_gb} "
            f"cpu={snap.cpu_percent}% threads={snap.num_threads}{extra_str}"
        )
        return snap


resource_monitor = ResourceMonitor()

