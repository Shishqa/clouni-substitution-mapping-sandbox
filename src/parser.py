import os
import argparse
import subprocess as sp
import yaml
import copy
import uuid
import io

PUCCINI_CMD = 'puccini-tosca parse'

def parse(path, phases=5):
  pipe = sp.Popen(
      f'{PUCCINI_CMD} -s {phases} {path}',
      shell=True,
      stdout=sp.PIPE,
      stderr=sp.PIPE
    )
  res = pipe.communicate()

  if pipe.returncode != 0:
    raise RuntimeError(res[1].decode())

  return yaml.safe_load(res[0])