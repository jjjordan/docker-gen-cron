#!/usr/bin/python3
import subprocess
import parser

def main():
    containers = parser.parseJobs()
    crontab, lirefs = generateCrontab(containers)
    return installCrontab(crontab, lirefs)

def generateCrontab(containers):
    output = []
    lirefs = {}
    for c in containers.containers:
        output.append("# Container {name}".format(name=c.name))
        for coll in [c.jobs, c.start_jobs, c.restart_jobs]:
            if len(coll) == 0: continue

            output.append("!reset,stdout(true)")
            for j in coll:
                if not filterOptions(j):
                    continue
                
                output.append(j.serialize(c))
                lirefs[len(output)] = j

    return output, lirefs

def filterOptions(job):
    for opt in ['n', 'nice', 'runas']:
        if opt in job.options:
            del job.options[opt]
    if job.assign is not None:
        if job.assign[0] == 'SHELL':
            return False
    return True

def installCrontab(crontab, lirefs):
    contents = '\n'.join(crontab) + '\n'

    print("Installing contents:")
    print(contents)

    # Get current crontab
    proc = subprocess.run(["fcrontab", "-l"], text=True, capture_output=True)
    if proc.returncode != 0:
        print("fcrontab -l failed:")
        print(proc.stderr)
        return False
    
    # Compare
    if proc.stdout == contents:
        print("Crontab up-to-date, no change needed")
        return True
    
    # Update
    proc = subprocess.run(["fcrontab", "-"], input=contents, capture_output=True, text=True)
    if proc.returncode != 0:
        print("Failed to install crontab:")
        print(proc.stderr)
        return False
    
    print("Crontab updated")
    return True

if __name__ == '__main__':
    import sys
    sys.exit(0 if main() else 1)
