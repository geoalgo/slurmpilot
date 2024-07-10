#!/bin/bash

# launch a script that requires a library from another folder that is being copied over
# and added to Python path by slurmpilot
# Note that we need to provide the current directory as Python path so that the library is found.
PYTHONPATH=. python script/script_using_custom_library.py