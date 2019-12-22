#!/usr/bin/python3
import json
import os
import subprocess
import sys
import time

import parser

def main(container_name, action, jobid = None):
    print("RUNNING: {action} -> {container_name}".format(action=action, container_name=container_name))
    if action == 'start':
        return start_container(container_name)
    elif action == 'restart':
        return restart_container(container_name)
    elif action == 'job':
        return run_job(container_name, jobid)
    print("Invalid arguments")
    return False

def start_container(name):
    status = container_status(name)
    if status in ('exited',):
        p = subprocess.run(["docker", "start", name], stdin=subprocess.DEVNULL, stdout=1, stderr=2)
        sys.exit(p.returncode)
    print("Container is running, won't stop")
    return False

def restart_container(name):
    status = container_status(name)
    if status == 'running':
        p = subprocess.run(["docker", "restart", name], stdin=subprocess.DEVNULL, stdout=1, stderr=2)
        sys.exit(p.returncode)
    print("Container is not running, won't restart")
    return False

def container_status(name):
    p = subprocess.run(["docker", "inspect", name], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    j = json.loads(p.stdout)
    if len(j) == 1:
        return j[0].get('State', {}).get('Status', None)
    else:
        return None

def run_job(name, id):
    if not wait_for_jobs():
        print("Can't load jobs file, aborting")
        return False

    cfg = parser.parse_crontab()
    job = find_job(cfg, name, id)
    if not job:
        print("Can't find job, aborting")
        return False
    
    cmdline = ["docker", "exec", "-i"]
    if "runas" in job.options:
        cmdline += ["-u", job.options["runas"]]
    
    for k in job.env:
        cmdline += ["-e", "{}={}".format(k, os.environ.get(k, ""))]
    
    cmdline.append(name)
    
    if job.shell is not None:
        cmdline.append(job.shell)
    else:
        cmdline.append("/bin/sh")
    
    cmdline.append("-c")
    cmdline.append(job.job.cmd)
    
    stdin = subprocess.PIPE if job.job.input is not None else subprocess.DEVNULL
    proc = subprocess.Popen(cmdline, stdin=stdin, stdout=1, stderr=2)
    proc.communicate(job.job.input)
    sys.exit(proc.returncode)

def find_job(config, container_name, id):
    for container in config.containers:
        if container.name != container_name:
            continue
        
        cfg = JobConfig()
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
    sys.exit(0 if main(*sys.argv[1:]) else 1)
