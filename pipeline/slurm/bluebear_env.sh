# Shared BlueBEAR environment. Source it from the pipeline/ folder, after `module purge; module load bluebear`:
#   source slurm/bluebear_env.sh
# Loads the Python modules from slurm/bluebear.local.sh and activates the virtual environment for this
# node type (${BB_CPU}). The environment is built on first use, which needs internet and takes a few minutes.

if [ ! -f slurm/bluebear.local.sh ]; then
  echo "Missing slurm/bluebear.local.sh: copy slurm/bluebear.local.sh.example and edit it (run from pipeline/)" >&2
  return 1 2>/dev/null || exit 1
fi
source slurm/bluebear.local.sh
case "${BEAR_MODULES}${ASHWATCH_DATA}${VENV_DIR}" in
  *CHANGE_ME*|*/X/PROJECT/*)
    echo "slurm/bluebear.local.sh still has placeholder values: edit it first" >&2
    return 1 2>/dev/null || exit 1 ;;
esac

for _m in $BEAR_MODULES; do module load "$_m"; done
unset _m

export ASHWATCH_DATA
export PIP_CACHE_DIR="/scratch/${USER}/pip"          # home quota is small
VENV_PATH="${VENV_DIR}/ashwatch-${BB_CPU:-generic}"
mkdir -p "$ASHWATCH_DATA" "$VENV_DIR" logs

if [ ! -x "$VENV_PATH/bin/python" ]; then
  echo "Building virtual environment $VENV_PATH (first use on this node type)..."
  python3 -m venv "$VENV_PATH" \
    && "$VENV_PATH/bin/python" -m pip install --quiet --upgrade pip \
    && "$VENV_PATH/bin/python" -m pip install --quiet -r requirements.txt \
    || { echo "Could not build $VENV_PATH (no internet on this node? remove the folder and build it on a node that has it)" >&2
         rm -rf "$VENV_PATH"; return 1 2>/dev/null || exit 1; }
fi
source "$VENV_PATH/bin/activate"
echo "ashwatch env: $(python --version 2>&1), ${BB_CPU:-unknown cpu}, data in $ASHWATCH_DATA"
