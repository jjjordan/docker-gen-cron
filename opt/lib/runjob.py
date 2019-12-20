#!/usr/bin/python3

def main(container_name, action, *jobid):
    print("RUNNING: {action} -> {container_name}".format(action=action, container_name=container_name))
    return True

if __name__ == '__main__':
    import sys
    sys.exit(0 if main(*sys.argv[1:]) else 1)
