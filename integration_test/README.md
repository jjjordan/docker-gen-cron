# docker-gen-cron integration test
This tests the integration between docker-gen-cron and docker, fcron, and
docker-gen.  It compliments the unit tests found in `../opt/lib`, which
covers docker-gen-cron more extensively.

## Running
The test is invoked with `runtest.sh`, and depends on docker-gen-fcron
*already running*.  Like with docker-gen-cron, the prefix can be set with
the `PREFIX` environment variable.  It's easiest to start the dev version in
`docker-compose.yml` in the root and point the tests at that:

```sh
docker-compose up -d -f ../docker-compose.yml
PREFIX=TEST_CRON ./runtest.sh
```

## Architecture
`runtest.sh` sets up test containers, asserts that each test passes, reports
the result and cleans up when it's finished.  The environment variables that
are input to docker-gen-cron are set here.  Most of the rest of the magic
happens in...

`helper.py` tracks and reports the status of each test case (job).  Each job
actually invokes `helper.py`, which in turn runs a script in `checks/` and
tracks whether or not it succeeds.  (It does this rather naively, in text
files in /tmp).  It also serves as the entrypoint to the container, and
spawns an HTTP server that `runtest.sh` cURL's from in order to check results.

`checks` contains scripts that assert things about the environment in which
the job is invoked.  Each sets its exit code if these checks pass, which
surfaces through the above components.
