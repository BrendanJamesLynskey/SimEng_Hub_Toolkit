"""The roofline step model at the heart of a performance simulator."""


def step_time(flops, nbytes, peak_flops, bandwidth, overhead=0.5e-3):
    """Seconds for one step, and which roof bounds it."""
    tc = flops / peak_flops
    tm = nbytes / bandwidth
    if tc >= tm:
        return tc + overhead, "compute"
    return tm + overhead, "memory"
