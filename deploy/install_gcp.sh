#!/usr/bin/env bash
# Instala o bot como serviço no Ubuntu 24.04 (Google Cloud e2-micro).
# Uso (de dentro da pasta do projeto, como usuário normal, sem sudo):  bash deploy/install_gcp.sh
# Rode uma vez para preparar; edite o .env; rode de novo para ligar o serviço.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_USER="$(id -un)"
if [ "$(id -u)" -eq 0 ]; then
  echo "Rode sem sudo (o script pede sudo quando precisa)."; exit 1
fi

echo "1/5 Pacotes do sistema..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv >/dev/null

echo "2/5 Swap de 1 GB (a VM tem pouca memória)..."
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 1G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "3/5 Ambiente Python e dependências..."
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "4/5 Configuração (.env)..."
if [ ! -f "$APP_DIR/.env" ]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo
  echo "Preparei tudo. Agora edite o .env (token e ALLOWED_USER_IDS):"
  echo "    nano $APP_DIR/.env"
  echo "e rode este script de novo:  bash deploy/install_gcp.sh"
  exit 0
fi
chmod 600 "$APP_DIR/.env"
if ! grep -q '^TELEGRAM_BOT_TOKEN=.\+' "$APP_DIR/.env"; then
  echo "TELEGRAM_BOT_TOKEN está vazio no .env."; exit 1
fi

echo "5/5 Serviço (liga sozinho e reinicia se cair)..."
sudo tee /etc/systemd/system/toque-bot.service >/dev/null <<UNIT
[Unit]
Description=Toque da Fe - bot de artes
After=network-online.target
Wants=network-online.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python -m app.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable toque-bot >/dev/null 2>&1
sudo systemctl restart toque-bot
sleep 4
if systemctl is-active --quiet toque-bot; then
  echo "Bot no ar! Veja o log com:  journalctl -u toque-bot -f"
else
  echo "O serviço não subiu. Veja o motivo com:  journalctl -u toque-bot -n 30 --no-pager"; exit 1
fi
