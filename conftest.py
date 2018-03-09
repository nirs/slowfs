import logging
import os
import signal
import subprocess
import time

import pytest


log = logging.getLogger("test")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s')


@pytest.fixture
def basedir(tmpdir):
    # 1. Create real file system with a special __ready__ file.
    realfs = tmpdir.mkdir("realfs")
    realfs.join("__ready__").write("")

    # 2. Create slowfs mountpoint
    slowfs = tmpdir.mkdir("slowfs")

    # 3. Start slowfs
    log.debug("Starting slowfs...")
    cmd = ["python", "slowfs", str(realfs), str(slowfs)]
    if os.environ.get("DEBUG"):
        cmd.append("--debug")
    p = subprocess.Popen(cmd)
    try:
        # 4. Wait until __ready__ is visible via slowfs...
        log.debug("Waiting until mount is ready...")
        ready = slowfs.join("__ready__")
        for i in range(10):
            time.sleep(0.1)
            log.debug("Checking mount...")
            if ready.exists():
                log.debug("Mount is ready")
                break
        else:
            raise RuntimeError("Timeout waiting for slowfs mount %r" % slowfs)

        # 4. We are ready for the test
        yield tmpdir
    finally:
        # 5. Interrupt slowfs, unmounting
        log.debug("Stopping slowfs...")
        p.send_signal(signal.SIGINT)
        p.wait()
        log.debug("Stopped")
