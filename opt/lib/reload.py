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
    """Generates a crontab file from the specified config.

    Args:
        cfg (parser.CronTab): The crontab configuration.

    Returns:
        list: A list of the lines of the output crontab.
        dict: A map of lines in the output (1-indexed) to input Job objects.
    """
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

                if not j.is_empty():
                    output.append(serialize_job(j))
                    lirefs[len(output)] = j

    return output, lirefs

def filter_options(job):
    """Removes options from the input Job that are not supported."""
    optcount = len(job.options)
    for opt in ["n", "nice", "runas"]:
        if opt in job.options:
            del job.options[opt]
    if job.assign is not None:
        if job.assign[0] == "SHELL":
            return False

    if job.prefix == "@" and optcount > 1 and len(job.options) == 1 and job.has_option("monthly", "weekly", "daily", "hourly"):
        # Corner-case: we've removed options and changed the meaning of the options from
        # proper fcron options to Vixie cron-compatible shortcuts, which changes the number
        # of expected arguments in the timespec.  We need to add something back so we don't
        # confuse the parser.
        job.options["n"] = "0"

    return True

def serialize_job(job):
    """Serializes the specified Job to a string"""
    if job.prefix == "!":
        return job.prefix + serialize_options(job.options)

    if job.assign is not None:
        return '{}="{}"'.format(job.assign[0], job.assign[1])

    s = "{prefix}{options} {timespec} {name} ".format(
        prefix=job.prefix,
        options=serialize_options(job.options),
        timespec=job.timespec,
        name=job.container.name)

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
    """Serializes an Options object"""
    return ",".join(("{name}({value})" if v is not None else "{name}").format(name=k, value=v) for k, v in opts.items())

def sanitize_cmd(cmd):
    """Sanitizes the specified cmd so that it can be safely included in the
    command line as reminder text (following --).
    """
    idxs = [cmd.index(c) for c in ("\\", "\n") if c in cmd]
    if len(idxs) > 0:
        cmd = cmd[:min(idxs)]
    return cmd

def install_crontab(crontab, lirefs):
    """Invokes fcrontab to install the specified crontab"""
    contents = "\n".join(crontab) + "\n"

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

    logger.debug("Installing contents:\n\n{}\n".format(contents))

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
    for line in proc.stderr.split("\n"):
        if ": Syntax error:" in line:
            parts = line.split(":")
            lineno = parts[1]
            if parser.is_int(lineno):
                num = int(lineno)
                if num in lirefs:
                    job = lirefs[num]
                    xformed = crontab[num - 1]
                    t = "start" if job.start else "restart" if job.restart else "job"
                    logger.warning("Syntax error in {}:{} {}\nOriginal line: {}\nTransformed line: {}"
                        .format(job.container.name, t, job.index, job.orig, xformed))
                else:
                    logger.warning("Syntax error in auto-generated section:\n" + crontab[num - 1])
            else:
                logger.warning("Unexpected syntax error output:\n" + line)

    logger.info("Crontab updated")
    return True

if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
