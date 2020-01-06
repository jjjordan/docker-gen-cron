#!/usr/bin/python3
import logging
import subprocess

import parser
import logconfig

logger = logging.getLogger("reload")
USER = "nobody"

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

            output.append("!reset,stdout(true),mail(false)")
            for j in coll:
                if not filter_options(j):
                    continue

                if not parser.is_empty(j):
                    output.append(serialize_job(j, c))
                    lirefs[len(output)] = j

    return output, lirefs

def filter_options(job):
    optcount = len(job.options)
    for opt in ['n', 'nice', 'runas']:
        if opt in job.options:
            del job.options[opt]
    if job.assign is not None:
        if job.assign[0] == 'SHELL':
            return False

    if job.prefix == '@' and optcount > 1 and len(job.options) == 1 and job.has_option('monthly', 'weekly', 'daily', 'hourly'):
        # Corner-case: we've removed options and changed the meaning of the options from
        # proper fcron options to Vixie cron-compatible shortcuts, which changes the number
        # of expected arguments in the timespec.  We need to add something back so we don't
        # confuse the parser.
        job.options['n'] = '0'

    return True

def serialize_job(job, container):
    if job.prefix == '!':
        return job.prefix + serialize_options(job.options)

    if job.assign is not None:
        return '{}="{}"'.format(job.assign[0], job.assign[1])

    s = "{prefix}{options} {timespec} {name} ".format(
        prefix=job.prefix,
        options=serialize_options(job.options),
        timespec=job.timespec,
        name=container.name)

    if job.start:
        s += "start"
    elif job.restart:
        s += "restart"
    else:
        s += "job " + job.jobhash()

        sane_cmd = sanitize_cmd(job.cmd)
        if sane_cmd:
            s += " -- " + sane_cmd

    return s.lstrip()

def serialize_options(opts):
    return ','.join(('{name}({value})' if v is not None else '{name}').format(name=k, value=v) for k, v in opts.items())

# Can't have nice things (3.8) on debian ...
#def sanitize_cmd(cmd):
#    try:
#        parts = shlex.split(cmd)
#    except ValueErrore:
#        logger.exception("Parsing cmd")
#        return None
#
#    last = None
#    for i, part in enumerate(parts):
#        if any(x in part for x in ('\\', '>', '#', '"', "'", '--', '\n')):
#            last = i
#            break
#    if last is not None:
#        parts = parts[:last]
#    return shlex.join(parts)

def sanitize_cmd(cmd):
    idxs = [cmd.index(c) for c in ('\\', '\n') if c in cmd]
    if len(idxs) > 0:
        cmd = cmd[:min(idxs)]
    return cmd

def install_crontab(crontab, lirefs):
    contents = '\n'.join(crontab) + '\n'

    logger.debug("Installing contents:\n" + contents)

    # Get current crontab
    proc = subprocess.run(["fcrontab", "-l", USER], text=True, capture_output=True)
    if proc.returncode != 0:
        logger.error("fcrontab -l {} failed:\n{}".format(USER, proc.stderr))
        return False
    else:
        if len(proc.stdout) > 0:
            logger.debug("fcrontab -l {} stdout:\n{}".format(USER, proc.stdout))
        if len(proc.stderr) > 0:
            logger.debug("fcrontab -l {} stderr:\n{}".format(USER, proc.stderr))

    # Compare
    if proc.stdout == contents:
        logger.info("Crontab up-to-date, no change needed")
        return True

    # Update
    proc = subprocess.run(["fcrontab", "-", USER], input=contents, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error("Failed to install crontab {}:\n{}".format(USER, proc.stderr))
        return False
    else:
        if len(proc.stdout) > 0:
            logger.debug("fcrontab - {} stdout:\n{}".format(USER, proc.stdout))
        if len(proc.stderr) > 0:
            logger.debug("fcrontab - {} stderr:\n{}".format(USER, proc.stderr))

    # Warn about syntax errors
    for line in proc.stderr.split('\n'):
        if ': Syntax error:' in line:
            parts = line.split(':')
            lineno = parts[1]
            if parser.is_int(lineno):
                num = int(lineno)
                if num in lirefs:
                    job = lirefs[num]
                    xformed = crontab[num - 1]
                    t = 'start' if job.start else 'restart' if job.restart else 'job'
                    logger.warning("Syntax error in {}:{} {}\nOriginal line: {}\nTransformed line: {}"
                        .format(job.container.name, t, job.index, job.orig, xformed))
                else:
                    logger.warning("Syntax error in auto-generated section:\n" + crontab[num - 1])
            else:
                logger.warning("Unexpected syntax error output:\n" + line)

    logger.info("Crontab updated")
    return True

if __name__ == '__main__':
    import sys
    sys.exit(0 if main() else 1)
