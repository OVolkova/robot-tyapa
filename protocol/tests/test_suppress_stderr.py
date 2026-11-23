def test_suppress_stderr_restores_fd2():
    import os

    from tyapa_protocol import suppress_stderr

    before = os.fstat(2)
    with suppress_stderr():
        pass
    after = os.fstat(2)
    assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
