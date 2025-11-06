import sys

from .. import shipfile

def build_show_parser(subparsers):
    import argparse

    show_parser = subparsers.add_parser(
        "show", help="show shipfile contents"
    )

    show_parser.add_argument(
        "src_file", type=str
    )

    show_parser.set_defaults(handler=show_handler)
    return show_parser

def show_handler(args):
    sf = shipfile.ShipfileReader(args.src_file)
    sf.check_version_info()

    sf.read_metadata()

    opts = ", ".join(sorted(sf.config_info.keys()))
    print(f"configurations: {opts}")
