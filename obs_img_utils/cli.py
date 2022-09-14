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
    echo_package_json,
    echo_package_text,
    echo_packages_json,
    echo_packages_text,
    get_logger,
    get_condition_list_from_file,
    get_condition_list_from_arg,
    process_shared_options,
    license_repl,
    packages_repl,
    filter_packages_by_licenses,
    filter_packages_by_name
)
from obs_img_utils.api import OBSImageUtil

shared_options = [
    click.option(
        '-C',
        '--config',
        type=click.Path(exists=True),
        help='OBS Image utils config file to use. Default: '
             '~/.config/obs_img_utils/config.yaml'
    ),
    click.option(
        '--no-color',
        is_flag=True,
        help='Remove ANSI color and styling from output.'
    ),
    click.option(
        '--debug',
        '--verbose',
        'log_level',
        flag_value=logging.DEBUG,
        help='Display debug level logging to console.'
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
        help='URL for OBS download repository.'
    ),
    click.option(
        '--target-dir',
        type=click.Path(exists=True),
        help='Directory to store downloaded images and checksums.'
    ),
    click.option(
        '--image-name',
        type=click.STRING,
        help='Image name to download from the download-url.',
        required=True
    ),
    click.option(
        '--arch',
        type=click.Choice(['x86_64', 'aarch64']),
        help='Architecture of the image.'
    ),
    click.option(
        '--profile',
        type=click.STRING,
        help='The multibuild profile name for the image.'
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
    '--add-conditions-interactive',
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
@click.option(
    '--extension',
    type=click.STRING,
    help='Image file extension. Examples: [tar.gz, raw.xz]'
)
@click.option(
    '--checksum-extension',
    type=click.STRING,
    help='Image checksum file extension. Example: sha256'
)
@click.option(
    '--disallow-licenses-interactive',
    is_flag=True,
    help='Invoke license REPL to specify any licenses that '
         'should not be in the image.'
)
@click.option(
    '--disallow-packages-interactive',
    is_flag=True,
    help='Invoke packages REPL to specify any packages which '
         ' should not be in the image. This can use a wildcard'
         ' (*) to match a naming pattern like "*-mini".'
)
@click.option(
    '--skip-checksum-validation',
    is_flag=True,
    help='Skip the image checksum validation.'
)
@click.option(
    '--add-conditions-file',
    type=click.STRING,
    help='Specify conditions for the image from a file (witht the conditions '
         'in json format as a LIST)',
    default=''
)
@click.option(
    '--add-conditions-json',
    type=click.STRING,
    help='Specify conditions for the image from a CLI arg (witht the '
         'conditions in json format as a LIST as a single string)',
    default=''
)
@click.option(
    '--disallow-licenses',
    type=click.STRING,
    help='Specify any licenses that should not be in the image.'
         'More than one license can be specified sepparated by comma(,)',
    default=''
)
@click.option(
    '--disallow-packages',
    type=click.STRING,
    help='Specify any packages that should not be in the image.'
         'More than one license can be specified sepparated by comma(,).'
         'This can use a wildcard(*) to mach any naming pattern like "*-mini.',
    default=''
)
@add_options(shared_options)
@click.pass_context
def download(
    context,
    add_conditions_interactive,
    conditions_wait_time,
    extension,
    checksum_extension,
    disallow_licenses_interactive,
    disallow_packages_interactive,
    skip_checksum_validation,
    add_conditions_file,
    add_conditions_json,
    disallow_licenses,
    disallow_packages,
    **kwargs
):
    """
    Download image from OBS repository specified by `download-url`.
    """
    context.obj['conditions_wait_time'] = conditions_wait_time
    context.obj['checksum_extension'] = checksum_extension
    context.obj['extension'] = extension

    process_shared_options(context.obj, kwargs)
    config_data = get_config(context.obj)
    logger = get_logger(config_data.log_level)

    image_conditions = []
    if add_conditions_interactive:
        image_conditions = conditions_repl(config_data.no_color)

    if add_conditions_file:
        image_conditions.extend(
            get_condition_list_from_file(add_conditions_file, logger)
        )

    if add_conditions_json:
        image_conditions.extend(
            get_condition_list_from_arg(add_conditions_json, logger)
        )

    licenses = []
    if disallow_licenses_interactive:
        licenses = license_repl()

    if disallow_licenses:
        licenses.extend(disallow_licenses.split(','))

    package_names = []
    if disallow_packages_interactive:
        package_names = packages_repl()

    if disallow_packages:
        package_names.extend(disallow_packages.split(','))

    cli_report_callback = None
    if config_data.log_level < logging.WARNING:
        cli_report_callback = click_progress_callback

    with handle_errors(config_data.log_level, config_data.no_color):
        downloader = OBSImageUtil(
            config_data.download_url,
            context.obj['image_name'],
            conditions=image_conditions,
            arch=config_data.arch,
            target_directory=config_data.target_dir,
            profile=config_data.profile,
            log_level=config_data.log_level,
            conditions_wait_time=config_data.conditions_wait_time,
            log_callback=logger,
            report_callback=cli_report_callback,
            checksum_extension=config_data.checksum_extension,
            extension=config_data.extension,
            filter_licenses=licenses,
            filter_packages=package_names,
            signature_extension=config_data.signature_extension,
            skip_checksum_validation=skip_checksum_validation
        )
        image_source = downloader.get_image()

    logger.info(
        'Image downloaded: {img_source}'.format(img_source=image_source)
    )


@click.group()
def packages():
    """
    Package commands.
    """


@click.command(name='list')
@click.option(
    '--filter-licenses',
    is_flag=True,
    help='Invoke license REPL to specify license filters'
)
@click.option(
    '--filter-packages',
    is_flag=True,
    help='Invoke packages REPL to specify package name filters'
)
@click.option(
    '--output',
    type=click.Choice(['text', 'json']),
    help='The output format (text|json)',
    default='text'
)
@click.option(
    '--no-headers',
    is_flag=True,
    help='Do not print headers in text output',
    default=False
)
@add_options(shared_options)
@click.pass_context
def list_packages(
        context,
        filter_licenses,
        filter_packages,
        output,
        no_headers,
        **kwargs
):
    """
    Return a list of packages for the given image name.
    """
    process_shared_options(context.obj, kwargs)
    config_data = get_config(context.obj)
    logger = get_logger(config_data.log_level)

    licenses = []
    if filter_licenses:
        licenses = license_repl()

    package_names = []
    if filter_packages:
        package_names = packages_repl()

    with handle_errors(config_data.log_level, config_data.no_color):
        downloader = OBSImageUtil(
            config_data.download_url,
            config_data.image_name,
            arch=config_data.arch,
            target_directory=config_data.target_dir,
            profile=config_data.profile,
            log_level=config_data.log_level,
            log_callback=logger
        )
        packages_metadata = downloader.get_image_packages_metadata()

    if licenses:
        packages_metadata = filter_packages_by_licenses(
            packages_metadata,
            licenses
        )

    if package_names:
        matching_packages = {}
        for name in package_names:
            matching_packages.update(
                filter_packages_by_name(
                    packages_metadata,
                    name
                )
            )

        packages_metadata = matching_packages

    if output == 'json':
        echo_packages_json(
            packages_metadata,
            no_color=config_data.no_color
        )
    else:
        echo_packages_text(
            packages_metadata,
            no_color=config_data.no_color,
            no_headers=no_headers
        )


@click.command()
@click.option(
    '--package-name',
    type=click.STRING,
    required=True,
    help='Name of the package.'
)
@click.option(
    '--output',
    type=click.Choice(["text", "json"]),
    help='The output format (text|json)',
    default='text'
)
@click.option(
    '--no-headers',
    is_flag=True,
    help='Do not print headers in text output',
    default=False
)
@add_options(shared_options)
@click.pass_context
def show(context, package_name, output, no_headers, **kwargs):
    """
    Return information for the provided package name in the given image.
    """
    process_shared_options(context.obj, kwargs)
    config_data = get_config(context.obj)
    logger = get_logger(config_data.log_level)

    with handle_errors(config_data.log_level, config_data.no_color):
        downloader = OBSImageUtil(
            config_data.download_url,
            config_data.image_name,
            arch=config_data.arch,
            target_directory=config_data.target_dir,
            profile=config_data.profile,
            log_level=config_data.log_level,
            log_callback=logger
        )
        packages_metadata = downloader.get_image_packages_metadata()

    if output == 'json':
        echo_package_json(
            package_name,
            packages_metadata,
            no_color=config_data.no_color
        )
    else:
        echo_package_text(
            package_name,
            packages_metadata,
            no_color=config_data.no_color,
            no_headers=no_headers
        )


main.add_command(download)
packages.add_command(list_packages)
packages.add_command(show)
main.add_command(packages)
