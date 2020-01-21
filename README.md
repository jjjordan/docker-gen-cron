# docker-gen-cron
The `jjjordan/docker-gen-cron` image runs a cron daemon that can be used by
other containers running on the host.  It is useful for smaller
installations (e.g.  set up with `docker-compose`) that don't have
high-level job scheduling capabilities.  Jobs are specified in environment
variables on the containers where they will run.  `docker-gen-cron` will
pick up changes (via [docker-gen](https://github.com/jwilder/docker-gen))
and the jobs will be executed via `docker exec`.

A typical installation may look like this:

```yaml
# docker-compose.yml
version: '3'
services:
  cron:
    image: jjjordan/docker-gen-cron
    environment:
      TZ: America/Los_Angeles
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock

  some_other_container:
    # ...
    environment:
      CRON_0: '0 */1 * * * hourly-backup.sh'
      CRON_1: '*/1 * * * * touch /tmp/minutely'

  another_container:
    # ...
    environment:
      CRON_0: '@daily a-daily-job.sh'
```

`docker-gen-cron` uses [fcron](http://fcron.free.fr/) internally, so all of
the extra [options](http://fcron.free.fr/doc/en/fcrontab.5.html) available
in fcron can be used here.

## Job specification
Jobs are read from all environment variables of the form `CRON_###` where
`###` is an integer.  Lines will be processed in numeric (not lexical)
order.  Additionally, `CRON_START_###` can be used to set a schedule for the
container to be started if they have exited and similarly `CRON_RESTART_###`
will restart containers.  In these cases, no command needs to be specified. 
The prefix can be changed by supplying a `PREFIX` environment variable to
the cron container (an underscore will be added to this value).

### fcron options
`fcron` is flexible and many options can be set on jobs.  Most of these are
untouched, but a couple are handled specially:

| Option | Behavior |
| ------ | ------------- |
| **runas** | Translated to the `-u` option in `docker exec`, no effect in the cron container. (This should be the intuitive behavior) |
| **n**, **nice** | `nice` value. Ignored. |
| **SHELL=value** | If this environment variable is set in the job specification, then it will be used to execute the command in the target container. |
| *Other environment variables* | Passed to the job via `-e` options to `docker exec` |

## Advanced usage

### Output
Job output can be found in the logs of the cron container.  This is a
departure from the standard behavior of mailing output, but the normal
behavior can be restored.  `docker-gen-cron` has
[msmtp](https://marlam.de/msmtp/) installed as the system mailer, which can
be configured to deliver mail to a remote SMTP server by volume mounting a
[configuration file](https://marlam.de/msmtp/msmtprc.txt) to
`/etc/msmtprc` and explicitly telling fcron to mail output.  To
illustrate:

```yaml
# docker-compose.yml
version: '3'
services:
  cron:
    image: jjjordan/docker-gen-cron
    environment:
      TZ: America/Los_Angeles
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /etc/secret/msmtprc:/root/.msmtprc

  some_other_container:
    # ...
    environment:
      CRON_0: '!mail(true),mailto(your@address.com),erroronlymail(true)'
      CRON_1: '@ 1d daily-job.sh'
```

### More configuration
```yaml
# docker-compose.yml
version: '3'
services:
  cron:
    image: jjjordan/docker-gen-cron
    environment:
      # Optional: defaults to Etc/UTC
      TZ: America/Los_Angeles
      # Optional: Read environment variables with this prefix. Default: CRON
      #PREFIX: CRON
      # Optional: Much more output for troubleshooting
      #DEBUG: 1
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      # Optional: Keep fcron spool on local host
      #- /var/spool/docker-gen-cron:/var/spool/fcron
```

## References
* [fcron](http://fcron.free.fr/) is the cron daemon used in this container.
  * [crontab format](http://fcron.free.fr/doc/en/fcrontab.5.html) manual page
  * [User manual](http://fcron.free.fr/doc/en/index.html) in English
* [msmtp](https://marlam.de/msmtp/) is installed in this container as the default mailer.
  * [User manual](https://marlam.de/msmtp/msmtp.html)
  * [Example configuration file](https://marlam.de/msmtp/msmtp.html#Examples)
* [docker-gen](https://github.com/jwilder/docker-gen) is used to monitor containers, though you will likely not need to interface with it directly.
