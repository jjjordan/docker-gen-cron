#!/usr/bin/python3
import docker
import os
import socket
import struct
import sys
import time

def docker_exec(client, container_name, args, input):
    has_input = not not input
    ec = client.exec_create(container_name, stdin=has_input, **args)
    id = ec["Id"]

    sock = client.exec_start(id, socket=True)
    if has_input:
        write_stdin(sock, input)
        close_stdin(sock)

    read_result(sock)
    inspect = client.exec_inspect(id)
    while inspect["Running"]:
        time.sleep(1)
        inspect = client.exec_inspect(id)

    return inspect["ExitCode"]

def read_result(sock):
    # Stolen from docker.utils.socket package
    # See also: https://docs.docker.com/engine/api/v1.24/#attach-to-a-container
    buf = bytearray(512)
    bufv = memoryview(buf)
    hdr = bufv[:8]
    while True:
        # Read header
        hdrv = hdr
        while len(hdrv) > 0:
            count = sock.readinto(hdrv)
            if count <= 0:
                return
            hdrv = hdrv[count:]

        # Parse header
        stream, datalen = struct.unpack(">BxxxL", hdr)
        if datalen <= 0:
            return

        # Pick stream, pipe data
        buf = sys.stderr.buffer if stream == 2 else sys.stdout.buffer
        while datalen > 0:
            count = sock.readinto(bufv[:datalen])
            if count <= 0:
                # Flush and let the header read fail and exit
                break
            buf.write(bufv[:count])
            datalen -= count
        buf.flush()

def write_stdin(sock, data):
    if type(data) == str:
        data = data.encode('utf-8')
    os.write(sock.fileno(), data)

def close_stdin(sock):
    sock._sock.shutdown(socket.SHUT_WR)
