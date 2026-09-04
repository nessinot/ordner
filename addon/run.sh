#!/usr/bin/with-contenv bashio
export ORDNER_DATA=/share/ordner
export ORDNER_OCR_TALEN="$(bashio::config 'ocr_talen')"
export ORDNER_OCR_PARALLEL="$(bashio::config 'ocr_parallel')"
export ORDNER_RECONCILE_INTERVAL="$(bashio::config 'reconcile_interval')"
bashio::log.info "Ordner start, archief in ${ORDNER_DATA}"
exec /opt/venv/bin/uvicorn ordner.web.app:app --host 0.0.0.0 --port 8099 --proxy-headers --forwarded-allow-ips "*"
