"""Convert lx-music backup exports (.lxmc / .json) to any-listen songlist backup (.alcfg)."""

from .converter import (
    convert,
    convert_file,
    detect_lx_type,
    load_lx_data,
    save_alcfg,
    save_json,
)

__version__ = "0.1.0"
__all__ = [
    "convert",
    "convert_file",
    "detect_lx_type",
    "load_lx_data",
    "save_alcfg",
    "save_json",
    "__version__",
]
