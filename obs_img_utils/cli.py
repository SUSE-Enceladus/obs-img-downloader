# Copyright (c) 2019 SUSE LLC, All rights reserved.
#
# This file is part of obs-img-utils. obs-img-utils provides
# an api and command line utilities for images in OBS.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import click
import logging

from obs_img_utils.utils import (
    get_config,
    click_progress_callback,
    conditions_repl,
    handle_errors,
    echo_package,
    echo_packages,
    get_logger,
    process_shared_options
)
from obs_img_utils.api import OBSImageUtil, extensions

shared_options = [
    click.option(
        '-C',
        '--config',
        type=click.Path(exists=True),
        help='Image Downloader config file to use. Default: '
             '~/.config/obs_img_utils/config.yaml'
    ),
    click.option(
        '--no-color',
        is_flag=True,
        help='Remove ANSI color and styling from output.'
    ),
    click.option(
        '--debug',
        'log_level',
        flag_value=logging.DEBUG,
        help='Display debug level logging to console.'
    ),
    click.option(
        '--verbose',
        'log_level',
        flag_value=logging.INFO,
        default=True,
        help='Display logging info to console. (Default)'
    ),
    click.option(
        '--quiet',
        'log_level',
        flag_value=logging.WARNING,
        help='Disable console output.'
    ),
    click.option(
        '--download-url',
        type=click.STRING,
        help='OBS download URL.'
    ),
    click.option(
        '--download-dir',
        type=click.Path(exists=True),
        help='Directory to store downloaded images and checksums.'
    ),
    click.option(
        '--image-name',
        type=click.STRING,
        help='Image name from the OBS download URL.',
        required=True
    ),
    click.option(
        '--cloud',
        type=click.Choice(extensions.keys()),
        help='Cloud framework for the image to be downloaded.'
    ),
    click.option(
        '--arch',
        type=click.Choice(['x86_64', 'aarch64']),
        help='Architecture of the image.'
    ),
    click.option(
        '--version-format',
        type=click.STRING,
        help='Version format for image. Should contain format strings for'
             ' {kiwi_version} and {obs_build}.'
             ' Example: "{kiwi_version}-Build{obs_build}".'
    )
]


def add_options(options):
    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func
    return _add_options


def print_license(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo('GPLv3+')
    ctx.exit()


def abort_if_false(ctx, param, value):
    if not value:
        ctx.abort()


@click.group()
@click.version_option()
@click.option(
    '--license',
    is_flag=True,
    callback=print_license,
    expose_value=False,
    is_eager=True,
    help='Show license information.'
)
@click.pass_context
def main(context):
    """
    The command line interface provides obs image utilities.

    This includes downloading images, checking packages in images
    and getting package version information.
    """
    if context.obj is None:
        context.obj = {}


@click.command()
@click.option(
    '--conditions',
    is_flag=True,
    help='Invoke conditions process to specify conditions '
         'for image'
)
@click.option(
    '--conditions-wait-time',
    type=click.INT,
    default=0,
    help='Time (in seconds) to wait for conditions '
         'to be met. Retry period is 150 seconds and'
         ' default is 0 seconds for no wait.'
)
@add_options(shared_options)
@click.pass_context
def download(context, conditions, conditions_wait_time, **kwargs):
    """
    Download image from Open Build Service at `download_url`.
    """
    context.obj['conditions_wait_time'] = conditions_wait_time

    process_shared_options(context.obj, kwargs)
    config_data = get_config(context.obj)
    logger = get_logger(config_data.log_level)

    image_conditions = []
    if conditions:
        image_conditions = conditions_repl()

    with handle_errors(config_data.log_level, config_data.no_color):
        downloader = OBSImageUtil(
            config_data.download_url,
            context.obj['image_name'],
            config_data.cloud,
            conditions=image_conditions,
            arch=config_data.arch,
            download_directory=config_data.download_dir,
            version_format=config_data.version_format,
            log_level=config_data.log_level,
            conditions_wait_time=config_data.conditions_wait_time,
            log_callback=logger,
            report_callback=click_progress_callback
        )
        image_source = downloader.get_image()

    click.echo(
        'Image downloaded: {img_source}'.format(img_source=image_source)
    )


@click.group()
def packages():
    """
    Handle package requests.
    """


@click.command(name='list')
@add_options(shared_options)
@click.pass_context
def list_packages(context, **kwargs):
    """
    Return a list of packages for the given image.
    """
    process_shared_options(context.obj, kwargs)
    config_data = get_config(context.obj)
    logger = get_logger(config_data.log_level)

    with handle_errors(config_data.log_level, config_data.no_color):
        downloader = OBSImageUtil(
            config_data.download_url,
            config_data.image_name,
            config_data.cloud,
            arch=config_data.arch,
            download_directory=config_data.download_dir,
            version_format=config_data.version_format,
            log_level=config_data.log_level,
            log_callback=logger
        )
        packages_metadata = downloader.get_image_packages_metadata()

    echo_packages(
        packages_metadata,
        no_color=config_data.no_color
    )


@click.command()
@click.option(
    '--package-name',
    type=click.STRING,
    required=True,
    help='Name of the package.'
)
@add_options(shared_options)
@click.pass_context
def show(context, package_name, **kwargs):
    """
    Return information for the provided package name.
    """
    process_shared_options(context.obj, kwargs)
    config_data = get_config(context.obj)
    logger = get_logger(config_data.log_level)

    with handle_errors(config_data.log_level, config_data.no_color):
        downloader = OBSImageUtil(
            config_data.download_url,
            config_data.image_name,
            config_data.cloud,
            arch=config_data.arch,
            download_directory=config_data.download_dir,
            version_format=config_data.version_format,
            log_level=config_data.log_level,
            log_callback=logger
        )
        packages_metadata = downloader.get_image_packages_metadata()

    echo_package(
        package_name,
        packages_metadata,
        no_color=config_data.no_color
    )


main.add_command(download)
packages.add_command(list_packages)
packages.add_command(show)
main.add_command(packages)
