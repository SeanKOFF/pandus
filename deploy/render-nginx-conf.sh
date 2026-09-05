#!/bin/bash
# Подставляет DOMAIN и PROJECT_PREFIX из .env в шаблон nginx.
# Использование:  ./deploy/render-nginx-conf.sh > /куда/положить/site.conf
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
set -a; . ./.env; set +a

: "${DOMAIN:?DOMAIN не задан в .env}"
export PROJECT_PREFIX="${PROJECT_PREFIX:-pandus}"

# Подставляем только наши переменные: $host, $scheme и прочие
# переменные nginx должны остаться нетронутыми
envsubst '${DOMAIN} ${PROJECT_PREFIX}' < deploy/nginx-site.conf.template
