def test_suppress_stderr_restores_fd2():
    import os

    from tyapa_protocol import suppress_stderr

    before = os.fstat(2)
    with suppress_stderr():
        pass
    after = os.fstat(2)
    assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)


def test_suppress_stderr_concurrent_use_restores_fd2():
    import os
    import threading

    from tyapa_protocol import suppress_stderr

    before = os.fstat(2)

    def worker():
        for _ in range(20):
            with suppress_stderr():
                pass

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    after = os.fstat(2)
    assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
