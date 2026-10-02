from roofline import step_time


def test_big_matmul_is_compute_bound():
    t, bound = step_time(flops=1e15, nbytes=1e9, peak_flops=1e15, bandwidth=1e12)
    assert bound == "compute"
    assert t > 0
