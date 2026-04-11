"""erpclasp — ERPNext Server Script sync library and CLI."""

from erpclasp.api import FrappeAPIError, FrappeClient
from erpclasp.config import AppConfig, load_app_config
from erpclasp.diff import diff_against_remote
from erpclasp.sync import (
    PullResult,
    PushItemResult,
    load_mapping,
    map_path,
    pull_scripts,
    push_scripts,
    push_single_file,
    register_script,
    resolve_scripts_file,
    save_mapping,
    unmapped_local_scripts,
)
from erpclasp.utils import find_project_root, require_project_root, scripts_dir

__version__ = "0.1.0"

__all__ = [
    "AppConfig",
    "FrappeAPIError",
    "FrappeClient",
    "PullResult",
    "PushItemResult",
    "diff_against_remote",
    "find_project_root",
    "load_app_config",
    "load_mapping",
    "map_path",
    "pull_scripts",
    "push_scripts",
    "push_single_file",
    "register_script",
    "require_project_root",
    "resolve_scripts_file",
    "save_mapping",
    "scripts_dir",
    "unmapped_local_scripts",
]
