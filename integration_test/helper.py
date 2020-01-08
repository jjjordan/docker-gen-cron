#!/usr/bin/python3
import fcntl
import http.server
import os
import subprocess
import sys

from argparse import ArgumentParser

LOCK_FILE = "/tmp/file.lock"
RESULTS = "/tmp"

SUCCESS = 1
FAILURE = 2
NORESULT = 3

def main():
    parser = ArgumentParser()
    parser.add_argument("--root", help="Run root process (with test ids)")
    parser.add_argument("--test", help="Run test id")
    args = parser.parse_args()

    if args.root is not None:
        tests = args.root.split(',')
        if 'restart' in tests:
            mark_test('restart', True)
            run_server(test_restart)
        elif 'start' in tests:
            mark_test('start', True)
            run_server(test_results(tests))
        else:
            run_server(test_results(tests))
    elif args.test is not None:
        v = run_test(args.test)
        mark_test(args.test, v)
        return v
    else:
        print("Need --root or --test")

def run_test(test):
    p = subprocess.run(["/mnt/checks/{}".format(test)], stdin=0, stdout=1, stderr=2)
    return p.returncode == 0

def mark_test(test, result):
    print("Test {} {}".format(test, "succeeded" if result else "FAILED"))
    with FileLock():
        path = get_result_path(test, result)
        if os.path.exists(path):
            with open(path, "r") as f:
                count = int(f.read())
        else:
            count = 0
        with open(path, "w") as f:
            f.write(str(count + 1))

def get_result_path(test, result):
    fname = "result.{}.success" if result else "result.{}.err"
    return os.path.join(RESULTS, fname.format(test))

def test_restart():
    with FileLock():
        path = get_result_path('restart', True)
        if os.path.exists(path):
            with open(path, "r") as f:
                count = int(f.read())
            if count > 2:
                return SUCCESS
    return NORESULT

def test_results(tests):
    def tester():
        with FileLock():
            for test in tests:
                if os.path.exists(get_result_path(test, False)):
                    print("Case {} failed".format(test))
                    return FAILURE
                if not os.path.exists(get_result_path(test, True)):
                    print("Case {} unresolved".format(test))
                    return NORESULT
            print("All passed")
            return SUCCESS
    return tester

def run_server(tester):
    server = Server(tester)
    server.serve_forever()

class Server(http.server.ThreadingHTTPServer):
    def __init__(self, tester):
        super().__init__(('', 80), Handler)
        self.tester = tester

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        n = self.server.tester()
        if n == SUCCESS:
            self.send_response(200, b"OK")
            self.end_headers()
            self.wfile.write(b"OK")
        elif n == FAILURE:
            self.send_response(500, b"Error")
            self.end_headers()
            self.wfile.write(b"Error encountered")
        elif n == NORESULT:
            self.send_response(418, b"Teapot")
            self.end_headers()
            self.wfile.write(b"Waiting on result")
        else:
            print("Unexpected code = {}".format(n))
            self.send_response(404, b"IDK")
            self.end_headers()
            self.wfile.write(b"Unexpected result")

class FileLock:
    def __init__(self, file=LOCK_FILE):
        self.acquired = 0
        old = os.umask(0)
        self.fd = open(file, "w")
        os.umask(old)

    def __enter__(self):
        if self.fd is None:
            raise Exception("File closed")
        if self.acquired > 0:
            self.acquired += 1
        else:
            fcntl.flock(self.fd, fcntl.LOCK_EX)
            self.acquired += 1

    def __exit__(self, type, value, tb):
        if self.fd is None:
            raise Exception("File closed")
        if self.acquired > 1:
            self.acquired -= 1
        else:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            self.fd.close()

if __name__ == '__main__':
    res = main()
    if type(res) == int:
        sys.exit(res)
    else:
        sys.exit(0 if res else 1)
