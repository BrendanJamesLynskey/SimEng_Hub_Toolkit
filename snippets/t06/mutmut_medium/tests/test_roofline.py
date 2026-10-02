from roofline import step_time


def test_big_matmul_is_compute_bound():
    assert step_time(1e15, 1e9, 1e15, 1e12)[1] == "compute"


def test_small_batch_decode_is_memory_bound():
    assert step_time(1e9, 1e12, 1e15, 1e12)[1] == "memory"
