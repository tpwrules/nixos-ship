import sys

from . import cli

def main():
    try:
        program = sys.argv[0]
        args = sys.argv[1:]
        cli.main(program, args)
    except KeyboardInterrupt:
        pass
