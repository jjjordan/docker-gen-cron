from collections import OrderedDict
import json
import re

RUN_JOB = "/opt/lib/runjob.py"
JOB_FILE = "/var/run/jobs.json"

class CronTab:
    def __init__(self):
        self.containers = []
    
    def serialize(self, out):
        for c in self.containers:
            c.serialize(out)

class Container:
    def __init__(self):
        self.id = None
        self.name = None
        self.running = False
        self.jobs = []
        self.start_jobs = []
        self.restart_jobs = []
    
    def serialize(self, out):
        out.append("# Container {name}".format(name=self.name))
        out.append("!reset")
        for l in self.jobs:
            l.serialize(self, out)
        for l in self.start_jobs:
            l.serialize(self, out)
        for l in self.restart_jobs:
            l.serialize(self, out)

class Job:
    def __init__(self):
        self.index = 0
        self.orig = ""
        self.options = OrderedDict()
        self.assign = None
        self.prefix = ""
        self.timespec = ""
        self.cmd = ""
        self.input = None
        self.start = False
        self.restart = False
    
    def serialize(self, container, out):
        s = "{prefix}{options} {timespec} {run} {name} ".format(
            prefix=self.prefix,
            options=self.serialize_options(),
            timespec=self.timespec,
            run=RUN_JOB,
            name=container.name)

        if self.start:
            s += "start"
        elif self.restart:
            s += "restart"
        else:
            s += "job " + self.cmdhash()
        
        out.append(s)
    
    def serialize_options(self):
        return ','.join(('{name}({value})' if v is not None else '{name}').format(name=k, value=v) for k, v in self.options.items())

def parseJobs():
    with open(JOB_FILE, "r") as f:
        j = json.load(f)
    
    result = CronTab()
    for cj in j["containers"]:
        if cj is None: continue
        kvs = ((e["key"], e["value"]) for e in cj["envs"] if e is not None)
        if len(kvs) == 0:
            continue

        container = Container()
        container.id = cj["id"]
        container.name = cj["name"]
        container.running = cj["running"]
        parseContainer(container, kvs)
        result.containers.append(container)
    
    return result

def parseContainer(c, e):
    jobs = [(int(k), v) for k, v in e if isInt(k)]
    startJobs = [(int(trimPrefix("START_", k)), v) for k, v in e if isInt(trimPrefix("START_", k))]
    restartJobs = [(int(trimPrefix("RESTART_", k)), v) for k, v in e if isInt(trimPrefix("RESTART_", k))]
    
    for i, j in sorted(jobs):
        job = parseJob(j)
        if job is not None:
            job.index = i
            c.jobs.append(job)
    for i, j in sorted(startJobs):
        job = parseJob(j)
        if job is not None:
            job.index = i
            job.start = True
            c.start_jobs.append(job)
    for i, j in sorted(restartJobs):
        job = parseJob(j)
        if job is not None:
            job.index = i
            job.restart = True
            c.restart_jobs.append(job)

def parseJob(j):
    job = Job()
    job.orig = j

    j = j.lstrip()

    # If this looks like an assignment, then handle it and go
    m = re.match(r'\w+\s*=', j)
    if m is not None:
        k, v = j.split('=', 2)
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
        ok = parseOptions(job, j[:last])
        if not ok:
            # error
            return None
        j = j[last:]
    
    if job.prefix == '!':
        # Options set only, we're done.
        return job
    
    # Parse the timespec
    rest = parseTimespec(job, j)
    
    # This only leaves the command.
    pct = rest.find('%')
    if pct >= 0:
        job.cmd = rest[:pct]
        job.input = rest[pct+1:]
    else:
        job.cmd = rest.strip()
    
    return job

def parseOptions(job, options):
    i = 0
    while i < len(options):
        nextComma = options.find(',', i)
        nextParen = options.find('(', i)
        arg = None
        
        if nextParen >= 0 and ((nextComma >= 0 and nextParen < nextComma) or (nextComma < 0)):
            # We have an argument to consume.
            endParen = options.find(')', i)
            if endParen < 0:
                print("Unmatched '('")
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

def parseTimespec(job, line):
    # Parse the timespec.  The prefix and options determine how many fields it should contain.
    if job.prefix == '%':
        if hasOption(job, "hourly", "midhourly"):
            # minutes
            N = 1
        elif hasOption(job, "daily", "middaily", "nightly", "weekly", "midweekly"):
            # minutes, hours
            N = 2
        elif hasOption(job, "monthly", "midmonthly"):
            # minutes, hours, days
            N = 3
        else:
            # "normal" entry
            N = 5
    elif job.prefix == '@':
        if hasOption(job, "reboot", "resume", "yearly", "annually", "midnight"):
            # These can only ever be replacements
            N = 0
        elif hasOption(job, "monthly", "weekly", "daily", "hourly") and len(job.options) == 1:
            # If it's the only option, then zero fields.
            N = 0
        elif hasOption(job, "hourly", "midhourly"):
            # minutes
            N = 1
        elif hasOption(job, "daily", "middaily", "nightly", "weekly", "midweekly"):
            # minutes, hours
            N = 2
        elif hasOption(job, "monthly", "midmonthly"):
            # minutes, hours, days
            N = 3
        else:
            # One field (period)
            N = 1
    else:
        # This should be a "normal" entry.
        N = 5
    
    job.timespec, rest = takeFields(line, N)
    return rest

def takeFields(line, n):
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

def hasOption(job, *options):
    for opt in options:
        if opt in job.options:
            return True
    return False

def trimPrefix(pfx, s):
    return s[len(pfx):] if s.startswith(pfx) else s

def isInt(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def printJob(j):
    print("prefix=" + j.prefix)
    print("options=" + repr(j.options))
    print("timespec=" + j.timespec)
    print("cmd=" + j.cmd)

def testParse(j):
    job = parseJob(j)
    if job is not None:
        printJob(job)
    else:
        print("parseJob returned None")
