#!/bin/bash -e

REPO_ROOT=$(dirname $(realpath $0))

source ${REPO_ROOT}/.venv/bin/activate
rm -fr ${REPO_ROOT}/build ${REPO_ROOT}/dist
${REPO_ROOT}/.venv/bin/py2applet --make-setup ${REPO_ROOT}/scripts/voetstappen.py ${REPO_ROOT}/images/footsteps.icns
python3 ${REPO_ROOT}/setup.py py2app
