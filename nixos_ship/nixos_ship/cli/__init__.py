import argparse

from .create import build_create_parser
from .import_cmd import build_import_parser
from .install import build_install_parser

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
