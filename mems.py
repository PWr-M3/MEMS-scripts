import argparse

import bom
import library

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="MEMS Scripts")
    subparsers = parser.add_subparsers(required=True, help="Subcommand")

    parser_bom = subparsers.add_parser("bom", help="Generate bom and do bom checks")
    bom.add_subparser(parser_bom)
    parser_library = subparsers.add_parser(
        "library", help="Helper functions for library maintanance"
    )
    library.add_subparser(parser_library)

    args = parser.parse_args()
    args.func(args)
