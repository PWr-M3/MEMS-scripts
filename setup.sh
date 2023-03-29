#!/usr/bin/env bash

# Create a virtual enviroment and install all required packages
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
deactivate

# Create a script to run mems.py with venv enabled
echo "#/usr/bin/env bash" > mems.sh
echo "source "`pwd`"/.venv/bin/activate">>mems.sh
echo 'python3 '`pwd`'/mems.py "$@"'>>mems.sh
echo 'deactivate'>>mems.sh
chmod +x mems.sh

# Symlink mems.sh to /usr/bin so that user will have it in PATH
sudo ln -sfn `pwd`/mems.sh /usr/bin/mems