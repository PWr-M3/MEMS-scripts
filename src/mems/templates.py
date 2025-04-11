import json
from importlib import resources
import logging

from mems.utils import set_pro_json, get_pro_json

logger = logging.getLogger(__name__)

def add_subparser(subparsers):

    parser = subparsers.add_parser("templates", help="Adding template elements")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    _ = subparsers.add_parser(name="layers", help="Add layer presets, e.g. 'Front Silkscreen'")


    parser.set_defaults(func=run)

def run(args) -> None:
    if args.subcommand == "layers":
        add_presets()


def add_presets():
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



