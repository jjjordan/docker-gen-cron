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

import hashlib
import json
import logging
import re

JOB_FILE = "/var/etc/jobs.json"
logger = logging.getLogger("parser")

class CronTab:
    """
    CronTab represents configuration extracted from environment variables on docker containers.

    Attributes:
        containers (list): List of Container objects
        environment (dict): Environment variables supplied to docker-gen specific to docker-gen-cron
    """
    def __init__(self):
        self.containers = []
        self.environment = {}

class Container:
    """
    Container represents information about a container on the system.

    Attributes:
        name (str): Container name
        running (bool): Whether the container is running
        options (dict): Options specified on the container
        jobs (list): List of jobs specified in the container environment
        start_jobs (list): List of start jobs specified in the container environment
        restart_jobs (list): List of restart jobs specified in the container environment
    """
    def __init__(self):
        self.name = None
        self.running = False
        self.options = {}
        self.jobs = []
        self.start_jobs = []
        self.restart_jobs = []

class Job:
    """
    Job represents a job specified in a container's environment

    Attributes:
        container (Container): Parent container
        index (int): Index of job environment variable
        orig (str): Original cronjob specified line
        options (Options): Options for fcron
        assign (tuple): Key and value for an assignment
        prefix (str): First character of job spec if %, @, &, or !
        timespec (str): Cron job time spec
        cmd (str): Command to run
        input (str): Data to supply to stdin of job
        start (bool): Whether this is a job to start the container
        restart (bool): Whether this is a job to restart the container
    """
    def __init__(self):
        self.container = None
        self.index = 0
        self.orig = ""
        self.options = Options()
        self.assign = None
        self.prefix = ""
        self.timespec = ""
        self.cmd = ""
        self.input = None
        self.start = False
        self.restart = False

    def jobhash(self):
        """Calculates the hash of the job index, cmd, and input"""
        m = hashlib.sha256()
        m.update("{}\n".format(self.index).encode("utf-8"))
        m.update(self.cmd.encode("utf-8"))
        if self.input is not None:
            m.update(b"\n")
            m.update(self.input.encode("utf-8"))
        return m.hexdigest()[0:10]

    def has_option(self, *options):
        """Returns true if any of the specified options exists on this job"""
        return self.options.has_any(*options)

    def is_empty(self):
        """Returns whether the job is "empty": whether it is malformed to the point that
        it can be omitted from the output.
        """
        if self.assign is not None:
            return False
        if self.prefix == "!" and len(self.options) > 0:
            return False
        if len(self.options) == 0 and not self.timespec:
            return True
        if self.start or self.restart:
            return False
        if self.cmd:
            return False
        return True


class Options:
    """
    Options is a dict-like object backed by an associative list.  Allows duplicates and maintains
    original item order.
    """
    def __init__(self):
        self._items = []

    def __getitem__(self, key):
        for i in range(len(self._items) - 1, -1, -1):
            if self._items[i][0] == key:
                return self._items[i][1]
        raise KeyError

    def __setitem__(self, key, value):
        for i in range(len(self._items) - 1, -1, -1):
            if self._items[i][0] == key:
                self._items[i] = (key, value)
                return
        self._items.append((key, value))

    def __delitem__(self, key):
        for i in range(len(self._items) - 1, -1, -1):
            if self._items[i][0] == key:
                self._items.pop(i)

    def __iter__(self):
        return self._items.map(lambda x: x[0])

    def __contains__(self, key):
        for k, v in self._items:
            if k == key:
                return True
        return False

    def __repr__(self):
        return repr({k: v for k, v in self._items})

    def __len__(self):
        return len(self._items)

    def items(self):
        return self._items[:]

    def has_any(self, *options):
        for opt in options:
            if opt in self:
                return True
        return False

def parse_crontab():
    """Parses the crontab from a jobs.json output file

    Returns:
        CronTab: Crontabs of all containers in jobs.json
    """
    with open(JOB_FILE, "r") as f:
        j = json.load(f)
    return parse_crontab_json(j)

def parse_crontab_json(j):
    """Parses the crontab from the specified parsed JSON.

    Returns:
        CronTab: Crontabs of all containers found in data
    """
    result = CronTab()
    for cj in j["containers"]:
        if cj is None: continue
        kvs = [(e["key"], e["cmd"]) for e in cj["envs"] if e is not None]
        if len(kvs) == 0:
            continue

        container = Container()
        container.name = cj["name"]
        container.running = cj["running"]
        parse_container(container, kvs)
        result.containers.append(container)

    keys = ["DOCKER_GEN_CRON_DEBUG"]
    result.environment = {k: v for k, v in j["env"].items() if k in keys}

    result.containers.sort(key=lambda c: c.name)

    return result

def parse_container(c, e):
    """Parses the crontabs for the specified environment variables.

    Args:
        c (Container): Container object to write to
        e (dict): Environment variables for container
    """
    jobs = [(int(k), v) for k, v in e if is_int(k)]
    startJobs = [(int(trim_prefix("START_", k)), v) for k, v in e if k.startswith("START_") and is_int(trim_prefix("START_", k))]
    restartJobs = [(int(trim_prefix("RESTART_", k)), v) for k, v in e if k.startswith("RESTART_") and is_int(trim_prefix("RESTART_", k))]
    c.options = {k: v for k, v in e if not is_int(k) and not k.startswith("START_") and not k.startswith("RESTART_")}

    for i, j in sorted(jobs):
        job = parse_job(j)
        if job is not None:
            job.container = c
            job.index = i
            if not job.is_empty():
                c.jobs.append(job)
    for i, j in sorted(startJobs):
        job = parse_job(j)
        if job is not None:
            job.container = c
            job.index = i
            job.start = True
            if not job.is_empty():
                c.start_jobs.append(job)
    for i, j in sorted(restartJobs):
        job = parse_job(j)
        if job is not None:
            job.container = c
            job.index = i
            job.restart = True
            if not job.is_empty():
                c.restart_jobs.append(job)

def parse_job(j):
    """Parses the job string into a Job object."""
    job = Job()
    job.orig = j

    j = j.lstrip()

    # Exit early for comments
    if j.startswith("#"):
        return None

    # Deal with any potential funny business here, which would likely always involve newlines.
    # We'll add this back at the end after we've gotten past the point where stuff will be
    # written back out nearly unchanged.
    postlf = ""
    if "\n" in j:
        idx = j.index("\n")
        postlf, j = j[idx:], j[:idx]

    # If this looks like an assignment, then handle it and go
    m = re.match(r"[a-zA-Z]\w*\s*=", j)
    if m is not None:
        k, v = j.split("=", 2)
        k = k.strip()
        v = v.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]

        job.assign = (k, v)
        return job

    # Gather prefix
    if len(j) > 0 and j[0] in "%@!&":
        job.prefix = j[0]
        j = j[1:]

    # Find end of options
    m = re.match(r"(([a-zA-Z][a-zA-Z0-9]+)(\([^\)\s]+\))?,)*([a-zA-Z][a-zA-Z0-9]+)(\([^\)\s]+\))?", j)
    if m is not None:
        # Parse them.
        last = m.end()
        ok = parse_options(job, j[:last])
        if not ok:
            # error
            return None
        j = j[last:]

    if job.prefix == "!":
        # Options set only, we're done.
        return job

    # Parse the timespec
    j, ok = parse_timespec(job, j)
    if not ok:
        # We didn't get enough fields.
        return None

    # This only leaves the command.
    job.cmd, job.input = split_input(j + postlf)

    return job

def parse_options(job, options):
    """Parses fcron options into the specified job."""
    i = 0
    while i < len(options):
        nextComma = options.find(",", i)
        nextParen = options.find("(", i)
        arg = None

        if nextParen >= 0 and ((nextComma >= 0 and nextParen < nextComma) or (nextComma < 0)):
            # We have an argument to consume.
            endParen = options.find(")", i)
            if endParen < 0:
                logger.warning("Unmatched '('")
                return False
            job.options[options[i:nextParen]] = options[nextParen + 1:endParen]
            nextComma = options.find(",", endParen)
            if nextComma < 0:
                break
            i = nextComma + 1
        elif nextComma < 0:
            # Just a name to the end
            job.options[options[i:]] = None
            break
        else:
            # Just a name to the comma
            job.options[options[i:nextComma]] = None
            i = nextComma + 1

    return True

def parse_timespec(job, line):
    """Parses the timespec into the specified job.

    Args:
        job (Job): Job object
        line (str): The portion of the line beginning with the timespec.

    Returns:
        str: The remainder of the line following the timespec
        bool: Whether the timespec was valid (contains the correct number of elements)
    """
    # Parse the timespec.  The prefix and options determine how many fields it should contain.
    if job.prefix == "%":
        if job.has_option("hourly", "midhourly"):
            # minutes
            N = 1
        elif job.has_option("daily", "middaily", "nightly", "weekly", "midweekly"):
            # minutes, hours
            N = 2
        elif job.has_option("monthly", "midmonthly"):
            # minutes, hours, days
            N = 3
        else:
            # "normal" entry
            N = 5
    elif job.prefix == "@":
        if job.has_option("reboot", "resume", "yearly", "annually", "midnight"):
            # These can only ever be replacements
            N = 0
        elif job.has_option("monthly", "weekly", "daily", "hourly") and len(job.options) == 1:
            # If it's the only option, then zero fields.
            N = 0
        elif job.has_option("hourly", "midhourly"):
            # minutes
            N = 1
        elif job.has_option("daily", "middaily", "nightly", "weekly", "midweekly"):
            # minutes, hours
            N = 2
        elif job.has_option("monthly", "midmonthly"):
            # minutes, hours, days
            N = 3
        else:
            # One field (period)
            N = 1
    else:
        # This should be a "normal" entry.
        N = 5

    job.timespec, rest, ok = take_fields(line, N)
    return rest, ok

def split_input(line):
    """Splits the command into command and input.

    Args:
        line (str): The cronjob line after the timespec.

    Returns:
        str: The command
        str: The input or None
    """
    i = 0
    bslash = False
    while i < len(line):
        c = line[i]
        if bslash:
            bslash = False
        elif c == "\\":
            bslash = True
        elif c == "%":
            # Start of input!
            return line[:i].strip(), line[i+1:].replace("%", "\n")
        i += 1

    # We didn't find input character.
    return line.strip(), None

def take_fields(line, n):
    """Splits the specified line into two pieces, with the first containing n fields.

    Args:
        line (str): A crontab line
        n (int): The number of fields to return in the first half.

    Returns:
        str: The first n fields of line
        str: The remainder of the line
        bool: Whether at least n fields were found
    """
    line = line.lstrip()
    i = 0
    taken = 0
    for _ in range(n):
        last = i
        # Read non-whitespace
        while i < len(line) and not line[i].isspace():
            i += 1
        # Read whitespace
        while i < len(line) and line[i].isspace():
            i += 1
        if i > last:
            taken += 1

    return line[:i].rstrip(), line[i:], (taken == n)

def trim_prefix(pfx, s):
    """Trims a prefix from a string if the string starts with that prefix.

    Args:
        pfx (str): Prefix
        s (str): String

    Returns:
        str: s with the specified prefix removed if it is a prefix. Otherwise,
            s is returned.
    """
    return s[len(pfx):] if s.startswith(pfx) else s

def is_int(s):
    """Returns true if the specified string is an integer."""
    try:
        int(s)
        return True
    except ValueError:
        return False

def print_job(j):
    print("prefix=" + j.prefix)
    print("options=" + repr(j.options))
    print("timespec=" + j.timespec)
    print("cmd=" + j.cmd)

def test_parse(j):
    job = parse_job(j)
    if job is not None:
        print_job(job)
    else:
        print("parseJob returned None")
