import argparse

from .create import create_handler
from .import_cmd import import_handler
from .install import install_handler

def build_create_parser(subparsers):
    create_parser = subparsers.add_parser(
        "create", help="create a shipfile")

    create_parser.add_argument(
        "dest_file", type=argparse.FileType("wb")
    )

    create_parser.add_argument(
        "--rev", type=str, default="HEAD",
        help="rev to create the shipfile from (defaults to HEAD)"
    )

    create_parser.add_argument(
        "--delta", type=str,
        help="rev we assume the recipient already has"
    )

    create_parser.add_argument(
        "--level", type=str, choices=["ultra", "normal", "fast"],
        default="normal",
        help="tune compression level for your patience"
    )

    create_parser.set_defaults(handler=create_handler)
    return create_parser

def build_import_parser(subparsers):
    import_parser = subparsers.add_parser(
        "import", help="import a shipfile"
    )

    import_parser.add_argument(
        "src_file", type=argparse.FileType("rb")
    )

    import_parser.add_argument("-n", "--name",
        type=str, help="name of configuration to import",
        default=open("/proc/sys/kernel/hostname", "r").read().strip()
    )

    import_parser.add_argument("--root",
        type=str, help="root of system to import configuration into",
        default=""
    )

    import_parser.set_defaults(handler=import_handler)
    return import_parser

def build_install_parser(subparsers):
    install_parser = subparsers.add_parser(
        "install", help="install a shipfile"
    )

    install_parser.add_argument(
        "src_file", type=argparse.FileType("rb")
    )

    install_parser.add_argument("-n", "--name",
        type=str, help="name of configuration to install",
        default=open("/proc/sys/kernel/hostname", "r").read().strip()
    )

    install_parser.add_argument("--root",
        type=str, help="root of system to install configuration into",
        default=""
    )

    install_parser.add_argument("--install-bootloader",
        action="store_true", help="force install system bootloader")

    install_parser.set_defaults(handler=install_handler)
    return install_parser

def parse_args(program, args):
    main_parser = argparse.ArgumentParser(prog=program)

    subparsers = main_parser.add_subparsers(
        dest="action",
    )
    subparsers.required = True

    parsers = [
        build_create_parser(subparsers),
        build_import_parser(subparsers),
        build_install_parser(subparsers),
    ]

    return main_parser.parse_args(args)

def main(program, args):
    args = parse_args(program, args)

    return args.handler(args)
