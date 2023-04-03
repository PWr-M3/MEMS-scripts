import argparse

import bom

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="MEMS Scripts")
    subparsers = parser.add_subparsers(required=True, help="Subcommand")
    parser_bom = subparsers.add_parser("bom", help="Generate bom and do bom checks")
    bom.add_subparser(parser_bom)

    args = parser.parse_args()
    args.func(args)
