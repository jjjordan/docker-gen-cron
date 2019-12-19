#!/usr/bin/python3

import json

with open("/var/run/jobs.json", "r") as f:
    j = json.load(f)

for c in j["containers"]:
    if c is None:
        break
    
    print("Container {name} - {id}".format(name=c['name'], id=c['id']))
    for e in c['envs']:
        if e is None:
            break
        
        print("\t{key} = {cmd}".format(key=e["key"], cmd=e["cmd"]))
