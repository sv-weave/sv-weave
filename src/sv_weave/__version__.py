# The release version. CI's tag check reads version_info; non-tag CI builds set SUFFIX
# to a PEP 440 local segment (".dev<run>+gh.g<sha>"), which PyPI refuses.
version_info = (0, 3, 0)
SUFFIX = ""
__version__ = ".".join(str(n) for n in version_info) + SUFFIX
