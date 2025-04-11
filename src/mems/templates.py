import json
import logging
import shutil
import sys
from pathlib import Path
from importlib import resources
from typing import override

from mems.utils import get_pro_filename, get_pro_json, set_pro_json, set_text_variable

logger = logging.getLogger(__name__)

def add_subparser(subparsers):

    parser = subparsers.add_parser("templates", help="Adding template elements")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    _ = subparsers.add_parser(name="layers", help="Layer presets, e.g. 'Front Silkscreen'")
    _ = subparsers.add_parser(name="tracks", help="Track widths")
    _ = subparsers.add_parser(name="vias", help="Via sizes")
    _ = subparsers.add_parser(name="gitignore", help="Hardware gitignore")
    _ = subparsers.add_parser(name="variables", help="Text variables")
    _ = subparsers.add_parser(name="all", help="Add all presets")

    parser.set_defaults(func=run)

def run(args) -> None:
    if args.subcommand == "layers" or args.subcommand == "all":
        add_layer_presets()
    if args.subcommand == "tracks" or args.subcommand == "all":
        add_tracks()
    if args.subcommand == "vias" or args.subcommand == "all":
        add_vias()
    if args.subcommand == "gitignore" or args.subcommand == "all":
        add_gitignore()
    if args.subcommand == "variables" or args.subcommand == "all":
        add_variables()


def add_layer_presets():
    pro_json = get_pro_json()
    if "layer_presets" not in pro_json["board"]:
        logger.debug("No layer_presets in .kicad_pro. Adding")
        pro_json["board"]["layer_presets"] = []
    pro_presets = pro_json["board"]["layer_presets"]
    template_json = json.load(resources.open_text("mems", "data/layer_presets_template.json"))
    for template in template_json:
        for i, preset in enumerate(pro_presets):
            if preset["name"] == template["name"]:
                logger.debug(f"Updating preset: {preset["name"]}")
                pro_presets[i] = template
                break
        else:
            logger.debug(f"Adding new preset: {template["name"]}")
            pro_presets.append(template)
    set_pro_json(pro_json)

def add_tracks():
    pro_json = get_pro_json()
    pro_json["board"]["design_settings"]["track_widths"] = [
        0.0,
        0.13,
        0.2,
        0.3,
        0.5,
        1
    ]
    set_pro_json(pro_json)

def add_vias():
    pro_json = get_pro_json()
    pro_json["board"]["design_settings"]["via_dimensions"] = [
        {
            "diameter": 0.0,
            "drill": 0.0
        },

        {
            "diameter": 0.45,
            "drill": 0.3
        },
        {
            "diameter": 0.7,
            "drill": 0.5
        },
        {
            "diameter": 1.2,
            "drill": 0.8
        }
    ]
    set_pro_json(pro_json)

def add_gitignore():
    pro = get_pro_filename()
    if pro is None:
        sys.exit(1)
    pro_path = pro.parent / ".gitignore"
    traversable = resources.files("mems.data")
    with resources.as_file(traversable) as path:
        shutil.copy(Path(path) / "hw.gitignore.template", pro_path)


def add_variables():
    set_text_variable("rev", "0.0")
    set_text_variable("sha", "0000000")
    set_text_variable("date", "0000-00-00")
    set_text_variable("title", "TITLE", override=False)
    set_text_variable("desc1", "Description line 1", override=False)
    set_text_variable("desc2", "Description line 2", override=False)
