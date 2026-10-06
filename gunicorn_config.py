import multiprocessing

# Server socket
bind = "127.0.0.1:8001"

# Workers - 1GB RAM li server uchun optimallashtirilgan
workers = 2
threads = 2
worker_class = "gthread"
worker_connections = 1000

# Request handling
max_requests = 1000
max_requests_jitter = 100
timeout = 60
keepalive = 5

# Logging
accesslog = "/var/log/gunicorn/exclusive_crm_access.log"
errorlog = "/var/log/gunicorn/exclusive_crm_error.log"
loglevel = "info"

# Process naming
proc_name = "exclusive_crm"

# Debugging
reload = False
