#!/usr/bin/python3

import os.path
import unittest
import yaml

import parser
import reload
import runjob

class TestAll(unittest.TestCase):
    def test_basic(self):
        self.run_tests("test_cases.yml")
    
    def run_tests(self, file):
        path = os.path.realpath(os.path.dirname(__file__))
        with open(os.path.join(path, file), "r") as f:
            y = yaml.safe_load(f)

        for test in y["tests"]:
            j = convert_to_json(test["containers"])
            
            for container in test["containers"]:
                p = parser.parse_crontab_json(j)
                crontab, lirefs = reload.generate_crontab(p)
                self.check_crontab(container, crontab, lirefs)
                
                # The above mutates the input, do it again
                p = parser.parse_crontab_json(j)
                self.check_jobs(p, container)
    
    def check_crontab(self, container, crontab, lirefs):
        for case in container["cases"]:
            line, job = find_crontab_line(container, crontab, lirefs, case)
            expected = case.get("crontab", None)
            if expected is None:
                expected = case.get("crontab_prefix", None)
                if expected is not None:
                    expected += " <run> %s job <hash>" % container["name"]
                else:
                    self.assertTrue(False, "cannot find crontab output for case {}".format(case["index"]))

            if expected and not job:
                self.assertTrue(False, "cannot find job {}".format(case["index"]))
            self.assertEqual(massage_expected(expected, job), massage_crontab(line), "Index {}".format(case["index"]))
    
    def check_jobs(self, parsed, container):
        for case in container["cases"]:
            if "docker" not in case:
                continue

            job = find_parsed_job(parsed, container, case)
            self.assertIsNotNone(job, "Cannot find job {}".format(case["index"]))
            
            jobcfg = runjob.find_job(parsed, container["name"], job.jobhash())
            self.assertIsNotNone(jobcfg, "Cannot load job {}".format(case["index"]))
            
            cmdline = runjob.get_command(jobcfg, jobcfg.env)
            self.assertEqual([runjob.DOCKER] + case["docker"], cmdline, case["index"])

def convert_to_json(containers):
    result = {"containers": [], "env": {}}
    for c in containers:
        result["containers"].append({
            "name": c["name"],
            "running": c["running"],
            "envs": [{
                "key": parser.trim_prefix("CRON_", k),
                "cmd": v,
            } for k, v in c["env"].items() if k.startswith("CRON_")]
        })
    return result

def find_crontab_line(container, crontab, lirefs, case):
    for line, job in lirefs.items():
        if job.container.name == container['name'] and job.index == case['index'] and job.start == case.get('start', False) and job.restart == case.get('restart', False):
            return crontab[line - 1], job
    return None, None

def find_parsed_job(parsed, container, case):
    for c in parsed.containers:
        if c.name == container["name"]:
            if case.get('start', False):
                coll = c.start_jobs
            elif case.get('restart', False):
                coll = c.restart_jobs
            else:
                coll = c.jobs
            for job in coll:
                if job.index == case['index']:
                    return job
    return None

def massage_expected(expected, job):
    if expected is None or job is None:
        return ""
    expected = expected.replace("<run>", reload.RUN_JOB).replace("<hash>", job.jobhash())
    return massage_crontab(expected)

def massage_crontab(line):
    if line is None:
        return ""
    
    # Remove duplicate spaces, but preserve any space at the beginning
    parts = line.split(' ')
    return ' '.join([parts[0]] + list(filter(lambda x: x != "", parts[1:])))

if __name__ == '__main__':
    unittest.main()
