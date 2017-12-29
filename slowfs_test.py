def test_create_real_file(basedir):
    realfile = basedir.join("realfs", "file")
    realfile.write("real")
    slowfile = basedir.join("slowfs", "file")
    assert slowfile.read() == "real"


def test_create_slow_file(basedir):
    slowfile = basedir.join("slowfs", "file")
    slowfile.write("slow")
    realfile = basedir.join("realfs", "file")
    assert realfile.read() == "slow"
