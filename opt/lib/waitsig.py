#!/usr/bin/python3
import logging
import os
import select
import signal
import time

import logconfig
import parser
import reload

logger = logging.getLogger("waitsig")
DEBOUNCE_TIME = 5 # seconds

def main():
    pr, pw = os.pipe()
    def sighand(sig, fr):
        os.write(pw, bytes((sig,)))

    signal.signal(signal.SIGHUP, sighand)

    debounce = time.time() + 2
    while True:
        timer = None
        if debounce is not None:
            now = time.time()
            if debounce > now:
                timer = debounce - now

        hr, _, _ = select.select([pr], [], [], timer)
        if len(hr) == 0:
            now = time.time()
            if now > debounce:
                # Run reload!
                logger.debug("Invoking reload after debounce")
                doreload()
                debounce = None
        else:
            sigbuf = os.read(pr, 1)
            if len(sigbuf) == 0:
                logger.debug("Read error from signal pipe")
                return False

            sig = sigbuf[0]
            logger.debug("Hanling signal {}".format(signal.getSignal(sig).name))

            if int(sigbuf[0]) == signal.SIGHUP:
                debounce = time.time() + 5
            else:
                logger.debug("Unexpected signal, exiting")
                return False

def doreload():
    logger.info("Reloading crontab")
    try:
        cfg = parser.parse_crontab()
        crontab, lirefs = reload.generate_crontab(cfg)
        reload.install_crontab(crontab, lirefs)
    except:
        logger.exception("Exception reloading crontab")

if __name__ == '__main__':
    import sys
    res = main()
    if type(res) == int:
        sys.exit(res)
    else:
        sys.exit(0 if res else 1)
