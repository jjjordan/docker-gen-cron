#!/usr/bin/python3
import logging
import subprocess

import parser
import logconfig

RUN_JOB = "/opt/lib/runjob.py"
logger = logging.getLogger("reload")

def main():
    cfg = parser.parse_crontab()
    logconfig.setLevel(cfg)
    crontab, lirefs = generate_crontab(cfg)
    return install_crontab(crontab, lirefs)

def generate_crontab(cfg):
    output = []
    lirefs = {}
    for c in cfg.containers:
        output.append("# Container {name}".format(name=c.name))
        colls = [c.start_jobs, c.restart_jobs]
        if c.running:
            colls.append(c.jobs)
        for coll in colls:
            if len(coll) == 0: continue

            output.append("!reset,stdout(true)")
            for j in coll:
                if not filter_options(j):
                    continue
                
                output.append(serialize_job(j, c))
                lirefs[len(output)] = j

    return output, lirefs

def filter_options(job):
    for opt in ['n', 'nice', 'runas']:
        if opt in job.options:
            del job.options[opt]
    if job.assign is not None:
        if job.assign[0] == 'SHELL':
            return False
    return True

def serialize_job(job, container):
    if job.prefix == '!':
        return job.prefix + serialize_options(job.options)
    
    if job.assign is not None:
        return "{} = {}".format(job.assign[0], job.assign[1])
    
    s = "{prefix}{options} {timespec} {run} {name} ".format(
        prefix=job.prefix,
        options=serialize_options(job.options),
        timespec=job.timespec,
        run=RUN_JOB,
        name=container.name)

    if job.start:
        s += "start"
    elif job.restart:
        s += "restart"
    else:
        s += "job " + job.jobhash()
    
    return s

def serialize_options(opts):
    return ','.join(('{name}({value})' if v is not None else '{name}').format(name=k, value=v) for k, v in opts.items())

def install_crontab(crontab, lirefs):
    contents = '\n'.join(crontab) + '\n'

    logger.debug("Installing contents:")
    logger.debug(contents)

    # Get current crontab
    proc = subprocess.run(["fcrontab", "-l"], text=True, capture_output=True)
    if proc.returncode != 0:
        logger.error("fcrontab -l failed:")
        logger.error(proc.stderr)
        return False
    
    # Compare
    if proc.stdout == contents:
        logger.info("Crontab up-to-date, no change needed")
        return True
    
    # Update
    proc = subprocess.run(["fcrontab", "-"], input=contents, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error("Failed to install crontab:")
        logger.error(proc.stderr)
        return False
    
    logger.info("Crontab updated")
    return True

if __name__ == '__main__':
    import sys
    sys.exit(0 if main() else 1)
