#!/usr/bin/env bash

# Create a virtual enviroment and install all required packages
python3 -m venv .venv
source .venv/bin/activate
pip3 install -e .
deactivate

# Symlink script so that user will have it in PATH
ln -sfn $(pwd)/.venv/bin/mems ~/.local/bin/mems

