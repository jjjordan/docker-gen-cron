#!/usr/bin/python3
import docker
import os
import socket
import struct
import sys
import time

def docker_exec(client, container_name, args, input):
    """Executes a command in a container, writes output to stdout/stderr and returns the exit code.

    Args:
        client (docker.APIClient): Docker client
        container_name (str): Container to run the command in
        args (dict): Keyword arguments to pass to client.exec_create
        input (str): Text to write to stdin of exec process, or None to close stdin.

    Returns:
        int: Exit code of process
    """

    has_input = not not input
    ec = client.exec_create(container_name, stdin=has_input, **args)
    id = ec["Id"]

    sock = client.exec_start(id, socket=True)
    if has_input:
        write_stdin(sock, input)

    read_result(sock)
    inspect = client.exec_inspect(id)
    while inspect["Running"]:
        time.sleep(1)
        inspect = client.exec_inspect(id)

    return inspect["ExitCode"]

def read_result(sock):
    """Reads multiplexed stdin+stdout from a socket and writes it to sys.stdout and sys.stderr"""

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
    """Writes data to the socket and then shuts down the write side"""

    if type(data) == str:
        data = data.encode("utf-8")
    os.write(sock.fileno(), data)
    sock._sock.shutdown(socket.SHUT_WR)
