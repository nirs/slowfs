# Copyright (c) 2015, Nir Soffer
# Copyright (c) 2013, Stavros Korokithakis
# All rights reserved.
#
# Licensed under BSD license, see LICENSE.

import argparse
import atexit
import collections
import contextlib
import errno
import logging
import os
import socket
import sys
import threading
import time

import fuse


def main(args):
    args = parse_args(args)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format='%(asctime)s %(levelname)s [%(name)s] %(message)s')
    config = Config(args.config)
    Controller(config)
    ops = SlowFS(args.root, config)
    fuse.FUSE(ops, args.mountpoint, foreground=True)


def parse_args(args):
    parser = argparse.ArgumentParser(description='A slow filesystem.')
    parser.add_argument('-c', '--config',
                        help='path to configuration file')
    parser.add_argument('--debug', action='store_true',
                        help=('enable extremely detailed and slow debug mode, '
                              'creating gigabytes of logs'))
    parser.add_argument('root', help='path to real file system')
    parser.add_argument('mountpoint', help='where to mount slowfs')
    return parser.parse_args(args)


class Config(object):

    def __init__(self, path):
        self._path = path
        self.enabled = True
        self._namespace = {}
        self.reload()

    def reload(self):
        if self._path is None:
            self._namespace = {}
        else:
            self._namespace = self._load()

    def get(self, name, default=0):
        return self._namespace.get(name, default)

    def set(self, name, value):
        self._namespace[name] = value

    def _load(self):
        d = {}
        with open(self._path) as f:
            exec f in d, d
        return d


class ClientError(Exception):
    pass


class Controller(object):

    SOCK = "control"
    log = logging.getLogger("ctl")

    def __init__(self, config):
        self.config = config
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self._remove_sock()
        self.sock.bind(self.SOCK)
        atexit.register(self._remove_sock)
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()

    def _run(self):
        try:
            while True:
                self._handle_command()
        except Exception:
            self.log.exception("Unhandled error")
            raise

    def _handle_command(self):
        try:
            msg, sender = self.sock.recvfrom(1024)
        except socket.error, e:
            self.log.error("Error receiving from control socket: %s", e)
            return
        self.log.debug("Received %r from %r", msg, sender)
        cmd, args = self._parse_msg(msg)
        try:
            handle = getattr(self, 'do_' + cmd)
        except AttributeError:
            self.log.warning("Unknown command %r", cmd)
            self.sock.sendto("2 Unknown command %r" % cmd, sender)
            return
        try:
            response = handle(*args)
        except ClientError as e:
            self.log.warning("Client error %s", e)
            self.sock.sendto("2 %s" % e, sender)
        except Exception:
            self.log.exception("Error handling %r", cmd)
            self.sock.sendto("1 Internal error", sender)
        else:
            self.sock.sendto("0 %s" % response, sender)

    def do_help(self, *args):
        """ show this help message """
        commands = sorted((name[3:], getattr(self, name))
                          for name in dir(self)
                          if name.startswith("do_"))
        response = "Available commands:\n"
        for name, func in commands:
            description = func.__doc__.splitlines()[0].strip()
            response += "  %-10s  %s\n" % (name, description)
        return response

    def do_reload(self, *args):
        """ reload configuration """
        self.log.info("Reloading configuration")
        self.config.reload()
        return ""

    def do_enable(self, *args):
        """ enable configuration """
        self.log.info("Enabling configuration")
        self.config.enabled = True
        return ""

    def do_disable(self, *args):
        """ disable configuration """
        self.log.info("Disabling configuration")
        self.config.enabled = False
        return ""

    def do_get(self, *args):
        """ get config value """
        if not args:
            raise ClientError("NAME is required")
        name = args[0]
        return "%s" % self.config.get(name)

    def do_set(self, *args):
        """ set config value """
        if len(args) < 2:
            raise ClientError("NAME and VALUE are required")
        name, value = args[:2]
        try:
            value = float(value)
        except ValueError as e:
            raise ClientError("Invalid config value: %s" % e)
        self.config.set(name, value)
        return ""

    def do_status(self, *args):
        """ show current status """
        return "Enabled" if self.config.enabled else "Disabled"

    def do_log(self, *args):
        """ change log level """
        if not args:
            raise ClientError("Log level is required")
        name = args[0]
        try:
            level = getattr(logging, name.upper())
        except AttributeError:
            raise ClientError("No such log level %r" % name)
        self.log.info("Setting log level to %r", name)
        logging.getLogger().setLevel(level)
        return ""

    def _parse_msg(self, msg):
        args = msg.split()
        if not args:
            return "help", []
        return args[0], args[1:]

    def _remove_sock(self):
        try:
            os.unlink(self.SOCK)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise


class CountedLock(object):

    def __init__(self):
        self.lock = threading.Lock()
        self.count = 0

    def __enter__(self):
        self.lock.acquire()
        return self

    def __exit__(self, *args):
        self.lock.release()


class LockManager(object):

    def __init__(self):
        self._lock = threading.Lock()
        self._busy = collections.defaultdict(CountedLock)

    @contextlib.contextmanager
    def __call__(self, fh):
        with self._lock:
            lock = self._busy[fh]
            lock.count += 1
        try:
            with lock:
                yield
        finally:
            with self._lock:
                lock.count -= 1
                if lock.count == 0:
                    del self._busy[fh]


class SlowFS(fuse.Operations):

    log = logging.getLogger("fs")

    def __init__(self, root, config):
        self.root = os.path.realpath(root)
        self.config = config
        self.locked = LockManager()

    def __call__(self, op, path, *args):
        if not hasattr(self, op):
            raise FuseOSError(EFAULT)
        self.log.debug('-> %s %r %r', op, path, args)
        self._delay(op)
        try:
            ret = getattr(self, op)(self.root + path, *args)
        except Exception as e:
            self.log.debug('<- %s %s', op, e)
            raise
        self.log.debug('<- %s %r', op, ret)
        return ret

    def _delay(self, op):
        if self.config.enabled:
            seconds = self.config.get(op, 0)
            if seconds:
                time.sleep(seconds)

    # Filesystem methods

    def access(self, path, mode):
        if not os.access(path, mode):
            raise fuse.FuseOSError(errno.EACCES)

    chmod = os.chmod
    chown = os.chown

    def getattr(self, path, fh=None):
        st = os.lstat(path)
        return dict((key, getattr(st, key)) for key in dir(st) if key.startswith('st_'))

    def readdir(self, path, fh):
        return ['.', '..'] + os.listdir(path)

    readlink = os.readlink
    mknod = os.mknod
    rmdir = os.rmdir
    mkdir = os.mkdir

    def statfs(self, path):
        stv = os.statvfs(path)
        return dict((key, getattr(stv, key)) for key in dir(stv) if key.startswith('f_'))

    unlink = os.unlink

    def symlink(self, path, target):
        return os.symlink(target, path)

    def rename(self, path, new):
        return os.rename(path, self.root + new)

    def link(self, path, target):
        return os.link(self.root + target, path)

    def utimens(self, path, times=None):
        return os.utime(path, times)

    # File methods

    open = os.open

    def create(self, path, mode, fi=None):
        return os.open(path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path, length, offset, fh):
        with self.locked(fh):
            os.lseek(fh, offset, os.SEEK_SET)
            return os.read(fh, length)

    def write(self, path, buf, offset, fh):
        with self.locked(fh):
            os.lseek(fh, offset, os.SEEK_SET)
            return os.write(fh, buf)

    def truncate(self, path, length, fh=None):
        with open(path, 'r+') as f:
            f.truncate(length)

    def flush(self, path, fh):
        return os.fsync(fh)

    def release(self, path, fh):
        return os.close(fh)

    def fsync(self, path, fdatasync, fh):
        return os.fsync(fh)


if __name__ == '__main__':
    main(sys.argv[1:])
