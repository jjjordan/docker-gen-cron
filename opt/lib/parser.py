import hashlib
import json
import logging
import re

JOB_FILE = "/var/run/jobs.json"
logger = logging.getLogger("parser")

class CronTab:
    def __init__(self):
        self.containers = []
        self.environment = {}

class Container:
    def __init__(self):
        self.name = None
        self.running = False
        self.options = {}
        self.jobs = []
        self.start_jobs = []
        self.restart_jobs = []

class Job:
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
        m = hashlib.sha256()
        m.update("{}\n".format(self.index).encode('utf-8'))
        m.update(self.cmd.encode('utf-8'))
        if self.input is not None:
            m.update(b"\n")
            m.update(self.input.encode('utf-8'))
        return m.hexdigest()[0:10]

    def has_option(self, *options):
        return self.options.has_any(*options)

class Options:
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
    with open(JOB_FILE, "r") as f:
        j = json.load(f)
    return parse_crontab_json(j)

def parse_crontab_json(j):
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
    jobs = [(int(k), v) for k, v in e if is_int(k)]
    startJobs = [(int(trim_prefix("START_", k)), v) for k, v in e if k.startswith("START_") and is_int(trim_prefix("START_", k))]
    restartJobs = [(int(trim_prefix("RESTART_", k)), v) for k, v in e if k.startswith("RESTART_") and is_int(trim_prefix("RESTART_", k))]
    c.options = {k: v for k, v in e if not is_int(k) and not k.startswith("START_") and not k.startswith("RESTART_")}

    for i, j in sorted(jobs):
        job = parse_job(j)
        if job is not None:
            job.container = c
            job.index = i
            if not is_empty(job):
                c.jobs.append(job)
    for i, j in sorted(startJobs):
        job = parse_job(j)
        if job is not None:
            job.container = c
            job.index = i
            job.start = True
            if not is_empty(job):
                c.start_jobs.append(job)
    for i, j in sorted(restartJobs):
        job = parse_job(j)
        if job is not None:
            job.container = c
            job.index = i
            job.restart = True
            if not is_empty(job):
                c.restart_jobs.append(job)

def parse_job(j):
    job = Job()
    job.orig = j

    j = j.lstrip()

    # Exit early for comments
    if j.startswith('#'):
        return None

    # If this looks like an assignment, then handle it and go
    m = re.match(r'[a-zA-Z]\w*\s*=', j)
    if m is not None:
        k, v = j.split('=', 2)
        k = k.strip()
        v = v.strip()
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]

        job.assign = (k, v)
        return job

    # Gather prefix
    if len(j) > 0 and j[0] in "%@!&":
        job.prefix = j[0]
        j = j[1:]

    # Find end of options
    m = re.match(r'(([a-zA-Z][a-zA-Z0-9]+)(\([^\)\s]+\))?,)*([a-zA-Z][a-zA-Z0-9]+)(\([^\)\s]+\))?', j)
    if m is not None:
        # Parse them.
        last = m.end()
        ok = parse_options(job, j[:last])
        if not ok:
            # error
            return None
        j = j[last:]

    if job.prefix == '!':
        # Options set only, we're done.
        return job

    # Parse the timespec
    j = parse_timespec(job, j)

    # This only leaves the command.
    job.cmd, job.input = split_input(j)

    return job

def parse_options(job, options):
    i = 0
    while i < len(options):
        nextComma = options.find(',', i)
        nextParen = options.find('(', i)
        arg = None

        if nextParen >= 0 and ((nextComma >= 0 and nextParen < nextComma) or (nextComma < 0)):
            # We have an argument to consume.
            endParen = options.find(')', i)
            if endParen < 0:
                logger.warning("Unmatched '('")
                return False
            job.options[options[i:nextParen]] = options[nextParen + 1:endParen]
            nextComma = options.find(',', endParen)
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
    # Parse the timespec.  The prefix and options determine how many fields it should contain.
    if job.prefix == '%':
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
    elif job.prefix == '@':
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

    job.timespec, rest = take_fields(line, N)
    return rest

def is_empty(job):
    if job.assign is not None:
        return False
    if job.prefix == '!' and len(job.options) > 0:
        return False
    if len(job.options) == 0 and not job.timespec:
        return True
    if job.start or job.restart:
        return False
    if job.cmd:
        return False
    return True

def split_input(line):
    i = 0
    bslash = False
    while i < len(line):
        c = line[i]
        if bslash:
            bslash = False
        elif c == '\\':
            bslash = True
        elif c == '%':
            # Start of input!
            return line[:i].strip(), line[i+1:].replace('%', '\n')
        i += 1

    # We didn't find input character.
    return line.strip(), None

def take_fields(line, n):
    line = line.lstrip()
    i = 0
    for _ in range(n):
        # Read non-whitespace
        while i < len(line) and not line[i].isspace():
            i += 1
        # Read whitespace
        while i < len(line) and line[i].isspace():
            i += 1

    return line[:i].rstrip(), line[i:]

def trim_prefix(pfx, s):
    return s[len(pfx):] if s.startswith(pfx) else s

def is_int(s):
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
    job = parseJob(j)
    if job is not None:
        printJob(job)
    else:
        print("parseJob returned None")
