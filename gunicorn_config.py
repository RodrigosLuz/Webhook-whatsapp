# gunicorn_config.py

# Quantidade de workers (processos) baseados em CPUs disponíveis
import multiprocessing
import os
from app.settings import load_settings

try:
    settings = load_settings()
    PORT = int(settings.get("PORT", os.getenv("PORT", 3000)))
    CONFIG_NAME = settings.get("CONFIG_NAME", os.getenv("CONFIG_NAME"))
except Exception:
    PORT = int(os.getenv("PORT", 3000))
    CONFIG_NAME = os.getenv("CONFIG_NAME")

bind = f"0.0.0.0:{PORT}"         # Endereço e porta onde a aplicação será exposta
workers = multiprocessing.cpu_count() * 2 + 1  # Número ideal de workers
worker_class = "sync"         # Pode ser "gevent" ou "uvicorn.workers.UvicornWorker" se usar async
timeout = 120                 # Tempo máximo para uma requisição (em segundos)
keepalive = 5                 # Mantém conexões HTTP abertas por alguns segundos
errorlog = "-"                # "-" envia logs de erro para stderr
accesslog = "-"               # "-" envia logs de acesso para stdout
loglevel = "info"             # Pode ser: debug, info, warning, error, critical

# Ativa reload automático apenas em desenvolvimento
reload = CONFIG_NAME == "dev"
print(f"Reload is set to: {reload}")
