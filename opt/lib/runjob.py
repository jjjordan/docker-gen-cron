#!/usr/bin/python3
import json
import logging
import os
import subprocess
import sys
import time

import parser
import logconfig

DOCKER = "/usr/local/bin/docker"
logger = logging.getLogger("runjob")

def main(container_name, action, jobid = None):
    if not wait_for_jobs():
        logger.critical("Cannot load jobs file, aborting")
        return False

    cfg = parser.parse_crontab()
    logconfig.setLevel(cfg)

    if action == 'start':
        return start_container(container_name)
    elif action == 'restart':
        return restart_container(container_name)
    elif action == 'job':
        return run_job(cfg, container_name, jobid)

    logger.error("Invalid arguments")
    return False

def start_container(name):
    status = container_status(name)
    if status in ('exited',):
        p = subprocess.run([DOCKER, "start", name], stdin=subprocess.DEVNULL, stdout=1, stderr=2)
        sys.exit(p.returncode)
    logger.warning("Container is running, won't stop")
    return False

def restart_container(name):
    status = container_status(name)
    if status == 'running':
        p = subprocess.run([DOCKER, "restart", name], stdin=subprocess.DEVNULL, stdout=1, stderr=2)
        sys.exit(p.returncode)
    logger.warning("Container is not running, won't restart")
    return False

def container_status(name):
    p = subprocess.run([DOCKER, "inspect", name], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    j = json.loads(p.stdout)
    if len(j) == 1:
        return j[0].get('State', {}).get('Status', None)
    else:
        return None

def run_job(cfg, name, id):
    jobcfg = find_job(cfg, name, id)
    if not jobcfg:
        logger.error("Can't find job, aborting")
        return False

    logger.info(">>> Command: {}".format(jobcfg.job.cmd))
    cmdline = get_command(jobcfg, os.environ)

    logger.debug("Executing command: {}".format(repr(cmdline)))
    stdin = subprocess.PIPE if jobcfg.job.input is not None else subprocess.DEVNULL
    proc = subprocess.Popen(cmdline, stdin=stdin, stdout=1, stderr=2)
    proc.communicate(jobcfg.job.input)
    return proc.returncode

def get_command(jobcfg, env):
    cmdline = [DOCKER, "exec", "-i"]
    if "runas" in jobcfg.options:
        cmdline += ["-u", jobcfg.options["runas"]]

    for k in jobcfg.env:
        cmdline += ["-e", "{}={}".format(k, env.get(k, ""))]

    cmdline.append(jobcfg.container)

    if jobcfg.shell is not None:
        cmdline.append(jobcfg.shell)
    else:
        cmdline.append("/bin/sh")

    cmdline.append("-c")
    cmdline.append(jobcfg.job.cmd)

    return cmdline

def find_job(config, container_name, id):
    for container in config.containers:
        if container.name != container_name:
            continue

        cfg = JobConfig()
        cfg.container = container_name
        for job in container.jobs:
            if job.assign is not None:
                if job.assign[0] == 'SHELL':
                    cfg.shell = job.assign[1]
                else:
                    cfg.env[job.assign[0]] = job.assign[1]
            elif job.prefix == '!':
                cfg.add_options(job.options)
            elif job.jobhash() == id:
                cfg.add_options(job.options)
                cfg.job = job
                return cfg

        return None
    return None

class JobConfig:
    def __init__(self):
        self.container = None
        self.env = {}
        self.options = {}
        self.shell = None
        self.job = None

    def add_options(self, options):
        for k, v in options.items():
            if k == 'reset':
                self.options = {}
                self.env = {} # TODO: Correct?
                self.shell = None
            else:
                self.options[k] = v

def wait_for_jobs():
    for delay in [1, 2, 5, 10, 0]:
        if os.path.exists(parser.JOB_FILE):
            return True
        time.sleep(delay)
    return False

if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == '-c':
        import shlex
        args = shlex.split(sys.argv[2])
        res = main(*args)
    else:
        res = main(*sys.argv[1:])
    if isinstance(res, int):
        sys.exit(res)
    sys.exit(0 if res else 1)
