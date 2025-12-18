#!/bin/bash

echo "=== Smartshop Communication Core – Broker Installer ==="

PROJECT_DIR="$(pwd)"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_FILE="/etc/systemd/system/smartshop-broker.service"

echo "[1] Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"

echo "[2] Activating venv & installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install pyzmq

echo "[3] Creating systemd service file..."
sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Smartshop ZeroMQ Broker
After=network.target

[Service]
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_DIR/bin/python -m core.broker
Restart=always
User=$USER

[Install]
WantedBy=multi-user.target
EOF

echo "[4] Reloading systemd..."
sudo systemctl daemon-reload

echo "[5] Enabling broker service..."
sudo systemctl enable smartshop-broker

echo "[6] Starting broker service..."
sudo systemctl start smartshop-broker

echo ""
echo "==============================================="
echo " Smartshop Broker installation completed!"
echo " Service name: smartshop-broker"
echo " Check status: sudo systemctl status smartshop-broker"
echo " Logs: journalctl -u smartshop-broker -f"
echo "==============================================="
