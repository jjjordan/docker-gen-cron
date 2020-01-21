import logging

def setDefault():
    """Initializes default logging"""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    fmt = logging.Formatter(fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    ch.setFormatter(fmt)
    root.addHandler(ch)

def setLevel(cfg):
    """Updates the logging level based on the supplied configuration"""
    if "DOCKER_GEN_CRON_DEBUG" in cfg.environment:
        logging.getLogger().setLevel(logging.DEBUG)

setDefault()
