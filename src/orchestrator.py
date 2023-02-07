import os
import subprocess as sp
import yaml

class Orchestrator:
  def __init__(self, root_path):
    self.root_path = root_path
    self.instances = {}
    self.substitutions = {}

  def init(self):
    self.init_substitutions()
    self.init_instances()

  def init_substitutions(self):
    templates_path = f'{self.root_path}/templates'

    for filename in os.listdir(templates_path):
      path = os.path.join(templates_path, filename)

      pipe = sp.Popen(
          f'puccini-tosca parse -s 2 {path}', shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
      res = pipe.communicate()

      if pipe.returncode != 0:
        raise RuntimeError(res[1].decode())

      definition = yaml.safe_load(res[0])
      substitution = definition['substitution']
      if substitution is None:
        continue

      substitution_type = substitution['type']
      if substitution_type not in self.substitutions:
        self.substitutions[substitution_type] = []

      self.substitutions[substitution_type].append({
          'file': path,
      })

  def instantiate(self, template_path, instance_name, inputs={}):
    if instance_name in self.instances.keys():
      raise RuntimeError(f'{instance_name} already exists')

    print(f'\nparsing {template_path}...')

    input_str = ''
    if len(inputs.keys()) > 0:
      input_str = '-i "' + \
          ','.join([f'{item[0]}={item[1]}' for item in inputs.items()]) + '"'

    pipe = sp.Popen(
        f'puccini-tosca compile {input_str} {template_path}', shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    res = pipe.communicate()

    if pipe.returncode != 0:
      raise RuntimeError(res[1].decode())

    clout = yaml.safe_load(res[0])

    self.instances[instance_name] = TopologyTemplateInstance(name, clout, path)


  def init_instances(self):
    pass
