from pbr.version import VersionInfo
_v = VersionInfo(__name__)
__version__ = _v.release_string()
version_info = _v.semantic_version().version_tuple()
