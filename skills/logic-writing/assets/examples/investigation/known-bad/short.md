# Free-threaded Python: supported, not the default

Short answer: as of Python 3.14, the free-threaded build (CPython without the global interpreter lock) is officially supported and no longer experimental, but it is still an optional build. The standard build keeps the lock, and nothing in the release notes says that will change in a given release [What's New 3.14].