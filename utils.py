import os
import pathlib


def get_main_sch():
    cwd = os.getcwd()
    path = pathlib.Path(cwd)
    sch = path / f"{path.stem}.kicad_sch"
    sch = sch.resolve()
    return str(sch)
