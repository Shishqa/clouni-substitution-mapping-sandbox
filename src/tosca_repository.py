import os
import argparse
import subprocess as sp
import yaml
import copy
import uuid
import io


templates = {}
substitutions = {}


def init_database():
  global templates
  global substitutions

  if not os.path.exists('tosca'):
    os.makedirs('tosca')

  if not os.path.exists('tosca/templates'):
    os.makedirs('tosca/templates')

  for filename in os.listdir('tosca/templates'):
    path = os.path.join('tosca/templates', filename)

    normalized_template = parse(path)
    templates[filename] = normalized_template

    substitution = normalized_template['substitution']
    if substitution is None:
      continue

    substitution_type = substitution['type']
    if substitution_type not in substitutions:
      substitutions[substitution_type] = []

    substitutions[substitution_type].append({'file': filename})


def parse(path, phases=5):
  PUCCINI_CMD = 'puccini-tosca parse'
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


def get_template(path):
  return templates[path]


def get_substitutions_for_type(node_type):
  # TODO: handle parent types as well
  if node_type not in substitutions.keys():
    return []
  return substitutions[node_type]