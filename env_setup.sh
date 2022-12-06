#!/bin/bash

python3 -m venv family-tree-env

source ./family-tree-env/bin/activate

python3 -m pip install -r requirements.txt

deactivate
