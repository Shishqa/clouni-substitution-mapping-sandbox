import os
import parser


substitutions = {}

def init_substitution_database():
  global substitutions

  for filename in os.listdir('templates'):
    path = os.path.join('templates', filename)

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