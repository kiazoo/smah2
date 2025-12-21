#!/bin/bash
PROJECT_ROOT="/home/dtcaiot/SMART-SHOP-APP"
VENV_PYTHON="$PROJECT_ROOT/venv/bin/python"

cd "$PROJECT_ROOT" || exit 1

exec "$VENV_PYTHON" -m services.comm-core.core.broker
