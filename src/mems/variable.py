import mems.utils as utils
import logging
from mems import utils

logger = logging.getLogger(__name__)

def add_subparser(subparsers):
    parser = subparsers.add_parser("variable", help="Set text variable")
    parser.add_argument("name", help="Variable name")
    parser.add_argument("value", help="Variable value")
    parser.set_defaults(func=utils.set_text_variable)

def set_text_variable(args):
    name = args["name"]
    value = args["value"]
    utils.set_text_variable(name, value)

