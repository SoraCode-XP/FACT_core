from configparser import ConfigParser
from pathlib import Path

from pydantic import BaseModel, Extra
from werkzeug.local import LocalProxy

_cfg = None

cfg = LocalProxy(lambda: _cfg)

# TODO use url types for urls

class DataStorage(BaseModel, extra=Extra.forbid):
    firmware_file_storage_directory: str
    mongo_server: str
    mongo_port: int
    main_database: str
    intercom_database_prefix: str
    statistic_database: str
    view_storage: str
    report_threshold: int
    db_admin_user: str
    db_admin_pw: str
    db_readonly_user: str
    db_readonly_pw: str
    user_database: str
    password_salt: str
    variety_path: str
    structural_threshold: int
    temp_dir_path: str


class Logging(BaseModel, extra=Extra.forbid):
    logfile: str
    mongodblogfile: str
    loglevel: str # TODO enum


class Unpack(BaseModel, extra=Extra.forbid):
    threads: str
    whitelist: list
    max_depth: int
    memory_limit: int


class DefaultPlugins(BaseModel, extra=Extra.forbid):
    default: list
    minimal: list
    # TODO
    # custom = init_systems, printable_strings


class Database(BaseModel, extra=Extra.forbid):
    results_per_page: int
    number_of_latest_firmwares_to_display: int
    ajax_stats_reload_time: int


class Statistics(BaseModel, extra=Extra.forbid):
    max_elements_per_chart: int


class ExpertSettings(BaseModel, extra=Extra.forbid):
    block_delay: float
    ssdeep_ignore: int
    communication_timeout: int
    unpack_threshold: float
    unpack_throttle_limit: int
    throw_exceptions: bool
    authentication: bool
    nginx: bool
    intercom_poll_delay: float
    radare2_host: str


# We need to allow extra here since we don't know what plugins will be loaded
class Config(BaseModel, extra=Extra.allow):
    data_storage: DataStorage
    logging: Logging
    unpack: Unpack
    default_plugins: DefaultPlugins
    database: Database
    statistics: Statistics
    expert_settings: ExpertSettings


def load_config(path=None):
    global _cfg

    if path is None:
        path = Path(__file__).parent / 'config/main.cfg'

    parser = ConfigParser()
    with open(path) as f:
        parser.read_file(f)

    parsed_sections = parser._sections.copy()
    parsed_sections['unpack']['whitelist'] = _parse_comma_separated_list(parser._sections['unpack']['whitelist'])
    parsed_sections['default_plugins']['default'] = _parse_comma_separated_list(parser._sections['default_plugins']['default'])
    parsed_sections['default_plugins']['minimal'] = _parse_comma_separated_list(parser._sections['default_plugins']['minimal'])

    # We should really not use private API of ConfigParser but whatever
    _cfg = Config(**parsed_sections)


def _parse_comma_separated_list(list_string):
    return [item.strip() for item in list_string.split(',')]
