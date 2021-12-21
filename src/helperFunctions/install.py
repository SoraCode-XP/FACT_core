import configparser
import logging
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from subprocess import PIPE, CalledProcessError
from typing import List, Tuple, Union

import distro
from common_helper_process import execute_shell_command_get_return_code


class InstallationError(Exception):
    '''
    Class representing all expected errors that happen during installation, such as timeouts on remote hosts.
    '''


class OperateInDirectory:
    '''
    Context manager allowing to execute a number of commands in a given directory. On exit, the working directory is
    changed back to its previous value.

    :param target_directory: Directory path to use as working directory.
    :param remove: Optional boolean to indicate if `target_directory` should be removed on exit.
    '''
    def __init__(self, target_directory: Union[str, Path], remove: bool = False):
        self._current_working_dir = None
        self._target_directory = str(target_directory)
        self._remove = remove

    def __enter__(self):
        self._current_working_dir = os.getcwd()
        os.chdir(self._target_directory)

    def __exit__(self, *args):
        os.chdir(self._current_working_dir)
        if self._remove:
            remove_folder(self._target_directory)


def remove_folder(folder_name: str):
    '''
    Python equivalent to `rm -rf`. Remove a directory an all included files. If administrative rights are necessary,
    this effectively falls back to `sudo rm -rf`.

    :param folder_name: Path to directory to remove.
    '''
    try:
        shutil.rmtree(folder_name)
    except PermissionError:
        logging.debug(f'Falling back on root permission for deleting {folder_name}')
        execute_shell_command_get_return_code(f'sudo rm -rf {folder_name}')
    except Exception as exception:
        raise InstallationError(exception) from None


def log_current_packages(packages: Tuple[str], install: bool = True):
    '''
    Log which packages are installed or removed.

    :param packages: List of packages that are affected.
    :param install: Identifier to distinguish installation from removal.
    '''
    action = 'Installing' if install else 'Removing'
    logging.info(f"{action} {' '.join(packages)}")


def _run_shell_command_raise_on_return_code(command: str, error: str, add_output_on_error=False) -> str:  # pylint: disable=invalid-name
    output, return_code = execute_shell_command_get_return_code(command)
    if return_code != 0:
        if add_output_on_error:
            error = f'{error}\n{output}'
        raise InstallationError(error)
    return output


def dnf_update_sources():
    '''
    Update package lists on Fedora / RedHat / Cent systems.
    '''
    return _run_shell_command_raise_on_return_code('sudo dnf update -y', 'Unable to update')


def dnf_install_packages(*packages: str):
    '''
    Install packages on Fedora / RedHat / Cent systems.

    :param packages: Iterable containing packages to install.
    '''
    log_current_packages(packages)
    return _run_shell_command_raise_on_return_code(f"sudo dnf install -y {' '.join(packages)}", f"Error in installation of package(s) {' '.join(packages)}", True)


def dnf_remove_packages(*packages: str):
    '''
    Remove packages from Fedora / RedHat / Cent systems.

    :param packages: Iterable containing packages to remove.
    '''
    log_current_packages(packages, install=False)
    return _run_shell_command_raise_on_return_code(f"sudo dnf remove -y {' '.join(packages)}", f"Error in removal of package(s) {' '.join(packages)}", True)


def apt_update_sources():
    '''
    Update package lists on Ubuntu / Debian / Mint / Kali systems.
    '''
    return _run_shell_command_raise_on_return_code('sudo apt-get update', 'Unable to update repository sources. Check network.')


def apt_install_packages(*packages: str):
    '''
    Install packages on Ubuntu / Debian / Mint / Kali systems.

    :param packages: Iterable containing packages to install.
    '''
    log_current_packages(packages)
    return _run_shell_command_raise_on_return_code(f"sudo apt-get install -y {' '.join(packages)}", f"Error in installation of package(s) {' '.join(packages)}", True)


def apt_remove_packages(*packages: str):
    '''
    Remove packages from Ubuntu / Debian / Mint / Kali systems.

    :param packages: Iterable containing packages to remove.
    '''
    log_current_packages(packages, install=False)
    return _run_shell_command_raise_on_return_code(f"sudo apt-get remove -y {' '.join(packages)}", f"Error in removal of package(s) {' '.join(packages)}", True)


def check_if_command_in_path(command: str) -> bool:
    '''
    Check if a given command is executable on the current system, i.e. found in systems PATH.
    Useful to find out if a program is already installed.

    :param command: Command to check.
    '''
    _, return_code = execute_shell_command_get_return_code(f'command -v {command}')
    if return_code != 0:
        return False
    return True


def install_github_project(project_path: str, commands: List[str]):
    '''
    Install github project by cloning it, running a set of commands and removing the cloned files afterwards.

    :param project_path: Github path to project. For FACT this is 'fkie-cad/FACT_core'.
    :param commands: List of commands to run after cloning to install project.

    :Example:

        .. code-block:: python

            install_github_project(
                'ghusername/c-style-project',
                ['./configure', 'make', 'sudo make install']
            )
    '''
    log_current_packages((project_path, ))
    folder_name = Path(project_path).name
    _checkout_github_project(project_path, folder_name)

    with OperateInDirectory(folder_name, remove=True):
        error = None
        for command in commands:
            output, return_code = execute_shell_command_get_return_code(command)
            if return_code != 0:
                error = f'Error while processing github project {project_path}!\n{output}'
                break

    if error:
        raise InstallationError(error)


def _checkout_github_project(github_path: str, folder_name: str):
    clone_url = f'https://www.github.com/{github_path}'
    _, return_code = execute_shell_command_get_return_code(f'git clone {clone_url}')
    if return_code != 0:
        raise InstallationError(f'Cloning from github failed for project {github_path}\n {clone_url}')
    if not Path('.', folder_name).exists():
        raise InstallationError(f'Repository creation failed on folder {folder_name}\n {clone_url}')


def load_main_config() -> configparser.ConfigParser:
    '''
    Create config object from main.cfg in src/config folder.

    :return: config object.
    '''
    config = configparser.ConfigParser()
    config_path = Path(Path(__file__).parent.parent, 'config', 'main.cfg')
    if not config_path.is_file():
        raise InstallationError(f'Could not load config at path {config_path}')
    config.read(str(config_path))
    return config


def run_cmd_with_logging(cmd: str, raise_error=True, shell=False, silent: bool = False, **kwargs):
    '''
    Runs `cmd` with subprocess.run, logs the command it executes and logs
    stderr on non-zero returncode.
    All keyword arguments are execpt `raise_error` passed to subprocess.run.

    :param shell: execute the command through the shell.
    :param raise_error: Whether or not an error should be raised when `cmd` fails
    :param silent: don't log in case of error.
    '''
    logging.debug(f'Running: {cmd}')
    try:
        cmd_ = cmd if shell else shlex.split(cmd)
        subprocess.run(cmd_, stdout=PIPE, stderr=PIPE, encoding='UTF-8', shell=shell, check=True, **kwargs)
    except CalledProcessError as err:
        # pylint:disable=no-else-raise
        if not silent:
            logging.log(logging.ERROR if raise_error else logging.DEBUG, f'Failed to run {cmd}:\n{err.stderr}')
        if raise_error:
            raise err


def check_distribution():
    '''
    Check if the distribution is supported by the installer.

    :return: The codename of the distribution
    '''
    bionic_code_names = ['bionic', 'tara', 'tessa', 'tina', 'disco']
    debian_code_names = ['buster', 'stretch', 'kali-rolling']
    focal_code_names = ['focal', 'ulyana', 'ulyssa', 'uma']

    codename = distro.codename().lower()
    if codename in bionic_code_names:
        logging.debug('Ubuntu 18.04 detected')
        return 'bionic'
    if codename in focal_code_names:
        logging.debug('Ubuntu 20.04 detected')
        return 'focal'
    if codename in debian_code_names:
        logging.debug('Debian/Kali detected')
        return 'debian'
    if distro.id() == 'fedora':
        logging.debug('Fedora detected')
        return 'fedora'
    logging.critical(f'Your Distribution ({distro.id()} {distro.version()}) is not supported. FACT Installer requires Ubuntu 18.04, 20.04 or compatible!')
    sys.exit(1)


def install_pip_packages(package_file: Path):
    '''
    Install or upgrade python packages from file `package_file` using pip. Does not raise an error if the installation
    fails because the package is already installed through the system's package manager. The package file should
    have one package per line (empty lines and comments are allowed).

    :param package_file: The path to the package file.
    '''
    for package in read_package_list_from_file(package_file):
        try:
            command = f'pip3 install -U {package} --prefer-binary'  # prefer binary release to compiling latest
            if not is_virtualenv():
                command = 'sudo -EH ' + command
            run_cmd_with_logging(command, silent=True)
        except CalledProcessError as error:
            # don't fail if a package is already installed using apt and can't be upgraded
            if 'distutils installed' in error.stderr:
                logging.warning(f'Pip package {package} is already installed with distutils. This may Cause problems:\n{error.stderr}')
                continue
            logging.error(f'Pip package {package} could not be installed:\n{error.stderr}')
            raise


def read_package_list_from_file(path: Path):
    '''
    Reads the file at `path` into a list.
    Each line in the file should be either a comment (starts with #) or a
    package name.
    There may not be multiple packages in one line.

    :param path: The path to the file.
    :return: A list of package names contained in the file.
    '''
    packages = []
    for line_ in path.read_text().splitlines():
        line = line_.strip(' \t')
        # Skip comments and empty lines
        if line.startswith('#') or len(line) == 0:
            continue
        packages.append(line)

    return packages


def is_virtualenv() -> bool:
    '''Check if FACT runs in a virtual environment'''
    return sys.prefix != getattr(sys, 'base_prefix', getattr(sys, 'real_prefix', None))
