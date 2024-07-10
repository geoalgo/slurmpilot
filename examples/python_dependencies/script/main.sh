#!/bin/bash
# launch a script that requires a library from another folder that is being copied over
# Note: Slurmpilot automatically adds the directory containing the scripts to PYTHONPATH which avoids the need to do
# `PYTHONPATH=. python script/script_using_custom_library.py`
python script/script_using_custom_library.py