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
if ! command -v sing-box >/dev/null 2>&1; then
    curl -fsSL https://sing-box.app/install.sh | sh
fi

echo "== 3. Go-тулчейн (нужен xcaddy для сборки Caddy из исходников) =="
if ! command -v go >/dev/null 2>&1; then
    apt-get install -y golang-go
    # Debian/Ubuntu стабильный репозиторий иногда отстаёт от версии, которую требует свежий
    # Caddy/forwardproxy (нужен Go 1.21+). Проверить командой ниже; если версия слишком старая —
    # поставить вручную с https://go.dev/dl/ (tar.gz в /usr/local/go, PATH=$PATH:/usr/local/go/bin).
    go version
fi

echo "== 4. Caddy + модуль forwardproxy (через xcaddy) =="
# xcaddy ставится через apt-репозиторий Cloudsmith (официальный способ на момент написания —
# сверить актуальность на https://github.com/caddyserver/xcaddy перед запуском, если снова упадёт).
if ! command -v xcaddy >/dev/null 2>&1; then
    apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/xcaddy/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-xcaddy-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/xcaddy/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-xcaddy.list
    apt-get update
    apt-get install -y xcaddy
fi
if [ ! -x /usr/bin/caddy ]; then
    xcaddy build --with github.com/caddyserver/forwardproxy@caddy2=github.com/klzgrad/forwardproxy@naive
    mv ./caddy /usr/bin/caddy
    chmod +x /usr/bin/caddy
fi

echo "== 5. Директории конфигов =="
mkdir -p /etc/sing-box /etc/caddy
chown vpn-panel:vpn-panel /etc/sing-box /etc/caddy
chmod 755 /etc/sing-box /etc/caddy
# Права 755 + владелец vpn-panel: панель может писать конфиги (см. core/apply.py), а сервисы
# sing-box/caddy читают их от своих системных пользователей за счёт world-readable файлов
# (стандартный umask при os.replace даёт 644) — это проще, чем городить общие группы.

echo "== 5b. Системный пользователь caddy + systemd-юнит =="
# Официальный apt-пакет Caddy сам создаёт юзера caddy и systemd-юнит — при установке через
# xcaddy build (наш случай, нужен ради модуля forwardproxy) этого не происходит, делаем руками.
if ! id -u caddy >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/caddy --create-home --shell /usr/sbin/nologin caddy
fi
cp "$(dirname "$0")/systemd/caddy.service" /etc/systemd/system/caddy.service

echo "== 6. Ограниченные sudo-права для vpn-panel =="
cat > /etc/sudoers.d/vpn-panel <<'EOF'
vpn-panel ALL=(root) NOPASSWD: /usr/bin/systemctl restart sing-box, /usr/bin/systemctl reload sing-box, /usr/bin/systemctl status sing-box
vpn-panel ALL=(root) NOPASSWD: /usr/bin/systemctl restart caddy, /usr/bin/systemctl reload caddy, /usr/bin/systemctl status caddy
EOF
chmod 440 /etc/sudoers.d/vpn-panel
visudo -c

echo "== 7. systemd-юнит панели =="
cp "$(dirname "$0")/systemd/vpn-panel.service" /etc/systemd/system/vpn-panel.service
systemctl daemon-reload

echo "== Готово =="
echo "Дальше: положить код в /opt/vpn-panel, poetry/pip install, затем:"
echo "  systemctl enable --now vpn-panel"
echo "  systemctl enable --now sing-box"
echo "  systemctl enable --now caddy"
echo "Конфиги sing-box/caddy панель сгенерирует и применит сама при первом POST /api/setup + POST /api/users."
