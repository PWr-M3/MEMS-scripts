import os
import pathlib
import json
import sys
import termcolor
import requests


def get_main_sch():
    cwd = os.getcwd()
    path = pathlib.Path(cwd)
    sch = path / f"{path.stem}.kicad_sch"
    sch = sch.resolve()
    return str(sch)


def get_config():
    file_path = os.path.realpath(__file__)
    dir_path = pathlib.Path(file_path).parent
    config_path = dir_path / "config.json"
    if os.path.exists(config_path):
        with open(config_path) as fp:
            try:
                j = json.load(fp)
            except:
                sys.exit(termcolor.colored(f"Error: Couldn't parse config file", "red"))
    else:
        sys.exit(termcolor.colored(f"Error: Config file doesn't exist", "red"))

    return j


def search_mouser(val):
    api_key = get_api_key()
    data = json.dumps({"SearchByPartRequest": {"mouserPartNumber": val}})
    headers = {"Content-type": "application/json", "accept": "application/json"}
    r = requests.post(
        "https://api.mouser.com/api/v1/search/partnumber",
        params={"apiKey": api_key},
        data=data,
        headers=headers,
    )
    return r.json()


def get_api_key():
    config = get_config()
    if "api_key" in config.keys():
        return config["api_key"]
    else:
        sys.exit(termcolor.colored(f'Error: No "api_key" found in config', "red"))
