# slowfs
A very slow file system for simulating overloaded storage

## Usage

```
mkdir mountpoint
python slowfs.py /some/dir moutpoint
```

You will see all files in /some/dir under mountpoint/ and be able to manipulate
them exactly as if they were in the original filesystem.

## Configuration

Nothing fancy yet; add sleeps in the oprations you want to be slow:

```python
    def unlink(self, path):
        time.sleep(10)
        return os.unlink(self._full_path(path))
```
