#!/usr/bin/python3

import os.path
import unittest
import yaml

import parser
import reload
import runjob

class TestAll(unittest.TestCase):
    def test_basic(self):
        """Tests cases in test_cases.yml"""
        self.run_tests("test_cases.yml")

    def run_tests(self, file):
        """Runs the tests found in specified file"""
        path = os.path.realpath(os.path.dirname(__file__))
        with open(os.path.join(path, file), "r") as f:
            y = yaml.safe_load(f)

        for i, test in enumerate(y["tests"]):
            with self.subTest(test=i):
                j = convert_to_json(test["containers"])

                for container in test["containers"]:
                    with self.subTest(container=container["name"]):
                        p = parser.parse_crontab_json(j)
                        crontab, lirefs = reload.generate_crontab(p)
                        self.check_crontab(container, crontab, lirefs)

                        # The above mutates the input, do it again
                        p = parser.parse_crontab_json(j)
                        self.check_jobs(p, container)

    def check_crontab(self, container, crontab, lirefs):
        """Asserts the 'crontab'/'crontab_prefix' from test_cases matches generated crontab

        Args:
            container (dict): Container json object
            crontab (list): The crontab returned from reload.generate_crontab
            lirefs (dict): The lirefs returned from reload.generate_crontab
        """
        for case in container["cases"]:
            with self.subTest(case=case["index"]):
                line, job = find_crontab_line(container, crontab, lirefs, case)
                expected = case.get("crontab", None)
                if expected is None:
                    expected = case.get("crontab_prefix", None)
                    if expected is not None:
                        expected += " %s job <hash>" % container["name"]
                        suffix = case.get("crontab_suffix", None)
                        if suffix is not None:
                            expected += " " + suffix
                    else:
                        # Continue?
                        self.assertTrue(False, "cannot find crontab output")

                if expected and not job:
                    self.assertTrue(False, "cannot find job")

                self.assertEqual(massage_expected(expected, job), massage_crontab(line))

    def check_jobs(self, parsed, container):
        """Asserts whether 'docker' from test_cases matches the result from get_command.

        Args:
            parsed (parser.CronTab): Configuration
            container (dict): Container json object
        """
        for case in container["cases"]:
            if "docker" not in case:
                continue

            with self.subTest(case=case["index"]):
                job = find_parsed_job(parsed, container, case)
                self.assertIsNotNone(job, "Cannot find job")

                jobcfg = runjob.find_job(parsed, container["name"], job.jobhash())
                self.assertIsNotNone(jobcfg, "Cannot load job")

                cmdline = runjob.get_command(jobcfg, jobcfg.env)
                self.assertEqual(case["docker"], cmdline)

def convert_to_json(containers):
    """Converts data found in test_cases to the format found in jobs.json"""
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
    """Finds the output crontab line and Job object for a test case. This performs
    a reverse-search on lirefs.

    Args:
        container (dict): Container json object
        crontab (list): The crontab returned from reload.generate_crontab
        lirefs (dict): The lirefs returned from reload.generate_crontab
        case (dict): The test case from json

    Returns:
        str: The output line of the crontab
        parser.Job: The job object associated with the crontab line
    """
    for line, job in lirefs.items():
        if job.container.name == container["name"] and job.index == case["index"] and job.start == case.get("start", False) and job.restart == case.get("restart", False):
            return crontab[line - 1], job
    return None, None

def find_parsed_job(parsed, container, case):
    """Finds the Job object from the configuration for the specified case.
    This searches the configuration by index.

    Args:
        parsed (parser.CronTab): Input configuration
        container (dict): Container json object
        case (dict): The test case from json

    Returns:
        parser.Job: The job object associated with the crontab
    """
    for c in parsed.containers:
        if c.name == container["name"]:
            if case.get("start", False):
                coll = c.start_jobs
            elif case.get("restart", False):
                coll = c.restart_jobs
            else:
                coll = c.jobs
            for job in coll:
                if job.index == case["index"]:
                    return job
    return None

def massage_expected(expected, job):
    """Massages an 'expected' value so it can be matched cleanly."""
    if expected is None or job is None:
        return ""
    expected = expected.replace("<hash>", job.jobhash())
    return massage_crontab(expected)

def massage_crontab(line):
    """Massages crontab output so it can be matched cleanly (removes excess spaces)"""
    if line is None:
        return ""

    # Remove duplicate spaces, but preserve any space at the beginning
    parts = line.split(" ")
    return " ".join([parts[0]] + list(filter(lambda x: x != "", parts[1:])))

if __name__ == "__main__":
    unittest.main()
