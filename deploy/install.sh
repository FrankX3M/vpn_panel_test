#!/usr/bin/env bash
# Bootstrap-скрипт для чистого Ubuntu/Debian сервера.
# Устанавливает sing-box, Caddy (кастомная сборка с forwardproxy через xcaddy),
# создаёт системного пользователя vpn-panel с ограниченными правами sudo.
#
# Использование: sudo bash deploy/install.sh
set -euo pipefail

echo "== 1. Системный пользователь для панели =="
if ! id -u vpn-panel >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin vpn-panel
fi

echo "== 2. sing-box (официальный репозиторий) =="
# Проверить актуальную инструкцию на https://sing-box.sagernet.org/installation/ перед запуском —
# способ установки (apt-репозиторий vs standalone-бинарник) может измениться.
curl -fsSL https://sing-box.app/install.sh | sh

echo "== 3. Caddy + модуль forwardproxy (через xcaddy) =="
if ! command -v xcaddy >/dev/null 2>&1; then
    curl -fsSL https://raw.githubusercontent.com/caddyserver/xcaddy/master/install.sh | sh
fi
xcaddy build --with github.com/caddyserver/forwardproxy@caddy2=github.com/klzgrad/forwardproxy@naive
mv ./caddy /usr/bin/caddy
chmod +x /usr/bin/caddy

echo "== 4. Директории конфигов =="
mkdir -p /etc/sing-box /etc/caddy
chown vpn-panel:vpn-panel /etc/sing-box /etc/caddy

echo "== 5. Ограниченные sudo-права для vpn-panel =="
cat > /etc/sudoers.d/vpn-panel <<'EOF'
vpn-panel ALL=(root) NOPASSWD: /usr/bin/systemctl restart sing-box, /usr/bin/systemctl reload sing-box, /usr/bin/systemctl status sing-box
vpn-panel ALL=(root) NOPASSWD: /usr/bin/systemctl restart caddy, /usr/bin/systemctl reload caddy, /usr/bin/systemctl status caddy
EOF
chmod 440 /etc/sudoers.d/vpn-panel
visudo -c

echo "== 6. systemd-юнит панели =="
cp "$(dirname "$0")/systemd/vpn-panel.service" /etc/systemd/system/vpn-panel.service
systemctl daemon-reload

echo "== Готово =="
echo "Дальше: положить код в /opt/vpn-panel, poetry/pip install, затем:"
echo "  systemctl enable --now vpn-panel"
echo "  systemctl enable --now sing-box"
echo "  systemctl enable --now caddy"
echo "Конфиги sing-box/caddy панель сгенерирует и применит сама при первом POST /api/setup + POST /api/users."
