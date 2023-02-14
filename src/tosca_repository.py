import os
import parser


substitutions = {}

def init_database():
  if not os.path.exists('tosca'):
    os.makedirs('tosca')

  if not os.path.exists('tosca/templates'):
    os.makedirs('tosca/templates')

  if not os.path.exists('tosca/atoms'):
    os.makedirs('tosca/atoms')
  
  init_substitution_database('tosca/atoms')
  init_substitution_database('tosca/templates')
  

def init_substitution_database(template_root):
  global substitutions

  for filename in os.listdir(template_root):
    path = os.path.join(template_root, filename)

    normalized_template = parser.parse(path, phases=2)
    substitution = normalized_template['substitution']
    if substitution is None:
      continue

    substitution_type = substitution['type']
    if substitution_type not in substitutions:
      substitutions[substitution_type] = []

    substitutions[substitution_type].append({'file': path})


def get_substitutions_for_type(node_type):
  # TODO: handle parent types as well
  if node_type not in substitutions.keys():
    return []
  return substitutions[node_type]