import argparse

from .create import create_handler

def build_create_parser(subparsers):
    create_parser = subparsers.add_parser(
        "create", help="create a shipfile")

    create_parser.add_argument(
        "dest_file", type=argparse.FileType("wb")
    )

    create_parser.set_defaults(handler=create_handler)
    return create_parser

def parse_args(program, args):
    main_parser = argparse.ArgumentParser(prog=program)

    subparsers = main_parser.add_subparsers(
        dest="action",
    )
    subparsers.required = True

    parsers = [
        build_create_parser(subparsers)
    ]

    return main_parser.parse_args(args)

def main(program, args):
    args = parse_args(program, args)

    return args.handler(args)
