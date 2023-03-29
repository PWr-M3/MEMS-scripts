# MEMS Scripts
This repository contains various scripts developed to help with MEMS Lab workflow. To setup on linux run `.\setup.sh`.
All scripts from the repository should be run from inside the virtual enviroment. Most of them are subscripts of main `mems` tool that is automatically added to path after setup. 
So for example, to run the bom tool, just execute `mems bom`. If you want to run a specific script , you need to enable virtual enviroment:
```
$ source .venv/bin/activate
```