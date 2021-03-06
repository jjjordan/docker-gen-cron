#!/usr/bin/python3
# This file is part of docker-gen-cron
# Copyright (C) 2020 John J. Jordan
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA

import docker
import logging
import os
import sys
import time

import exec
import parser
import logconfig

logger = logging.getLogger("runjob")

def main(container_name, action, jobid = None):
    if not wait_for_jobs():
        logger.critical("Cannot load jobs file, aborting")
        return False

    cfg = parser.parse_crontab()
    logconfig.setLevel(cfg)

    logger.debug("uid={uid}, gid={gid}, euid={euid}, egid={egid}".format(uid=os.getuid(), gid=os.getgid(), euid=os.geteuid(), egid=os.getegid()))

    client = docker.from_env()
    try:
        container = client.containers.get(container_name)
    except:
        logger.exception("Error finding container: {}".format(container_name))
        return False

    if action == "start":
        return start_container(container)
    elif action == "restart":
        return restart_container(container)
    elif action == "job":
        return run_job(container, cfg, jobid)

    logger.error("Invalid arguments")
    return False

def start_container(container):
    """Starts the specified container

    Args:
        container (docker.Container): Container object

    Returns:
        bool: Whether the operation succeeded.
    """
    if container.status in ("created", "exited"):
        try:
            container.start()
            return True
        except:
            logger.exception("Unexpected exception starting container {}".format(container.name))
            return False

    logger.warning("Container {} is running, won't stop".format(container.name))
    return False

def restart_container(container):
    """Restarts the specified container

    Args:
        container (docker.Container): Container object

    Returns:
        bool: Whether the operation succeeded.
    """
    if container.status == "running":
        try:
            container.restart()
            return True
        except:
            logger.exception("Unexpected exception restarting container {}".format(container.name))
            return False

    logger.warning("Container {} is not running, won't restart".format(container.name))
    return False

def run_job(container, cfg, id):
    """Runs job by id on the specified container.

    Args:
        container (docker.Container): Container object
        cfg (parser.CronTab): Crontab configuration
        id (str): Job id

    Returns:
        bool/int: Whether the operation succeeds, and if so the exit code of the job.
    """
    if container.status != "running":
        logger.warning("Container {} is not running, won't run job".format(container_name))
        return False

    jobcfg = find_job(cfg, container.name, id)
    if not jobcfg:
        logger.error("Can't find job, aborting")
        return False

    logger.debug(">>> Command: {}".format(jobcfg.job.cmd))
    cmdline = get_command(jobcfg, os.environ)
    logger.debug("Executing command: {}".format(repr(cmdline)))
    try:
        return exec.docker_exec(container.client.api, container.name, cmdline, jobcfg.job.input)
    except:
        logger.exception("Unexpected exception running command")
        return -1

def get_command(jobcfg, env):
    """Gets the command to run for the specified job.

    Args:
        jobcfg (parser.Job): Job configuration
        env (dict): Input environment arguments

    Returns:
        dict: Named arguments to docker.exec_create
    """
    newenv = {k: env.get(k, "") for k in jobcfg.env}
    shell = jobcfg.shell or "/bin/sh"
    newenv["SHELL"] = shell

    result = {
        "cmd": [shell, "-c", jobcfg.job.cmd],
        "environment": newenv,
    }

    if "runas" in jobcfg.options:
        newenv["USER"] = jobcfg.options["runas"]
        result["user"] = jobcfg.options["runas"]

    return result

def find_job(config, container_name, id):
    """Finds a job by container and id, and evalutes option values along the way.

    Args:
        config (parser.CronTab): Input configuration
        container_name (str): Name of the container where the job exists
        id (str): Job id

    Returns:
        JobConfig: The job and its associated configuration.
    """
    for container in config.containers:
        if container.name != container_name:
            continue

        cfg = JobConfig()
        cfg.container = container_name
        for job in container.jobs:
            if job.assign is not None:
                if job.assign[0] == "SHELL":
                    cfg.shell = job.assign[1]
                else:
                    cfg.env[job.assign[0]] = job.assign[1]
            elif job.prefix == "!":
                cfg.add_options(job.options)
            elif job.jobhash() == id:
                cfg.add_options(job.options)
                cfg.job = job
                return cfg

        return None
    return None

class JobConfig:
    """
    JobConfig represents a job and its applied options and environment.

    Attributes:
        container (parser.Container): The container of the job.
        env (dict): The environment variables set leading up to this job.
        options (dict): The fcron options specified for this job.
        shell (str): The SHELL environment variable or None.
        job (parser.Job): The job object.
    """
    def __init__(self):
        self.container = None
        self.env = {}
        self.options = {}
        self.shell = None
        self.job = None

    def add_options(self, options):
        """Merges the specified options into this JobConfig"""
        for k, v in options.items():
            if k == "reset":
                self.options = {}
                self.env = {} # TODO: Correct?
                self.shell = None
            else:
                self.options[k] = v

def wait_for_jobs():
    """Waits for parser.JOB_FILE to exist and returns True on success, False on timeout"""
    for delay in [1, 2, 5, 10, 0]:
        if os.path.exists(parser.JOB_FILE):
            return True
        time.sleep(delay)
    return False

if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "-c":
        import shlex
        if "--" in args[1]:
            # What comes after '--' may not parse.
            args = shlex.split(args[1][:args[1].index("--")])
        else:
            args = shlex.split(args[1])
    elif "--" in args:
        args = args[:args.index("--")]
    res = main(*args)
    if type(res) == int:
        sys.exit(res)
    sys.exit(0 if res else 1)
