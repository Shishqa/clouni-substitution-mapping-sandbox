import os
import argparse
import subprocess as sp
import yaml
import copy

substitutions = {
    'tosca::Compute': [
        {
            'file': 'templates/openstack-compute-public.yaml',
            # possibly, we can search by tags
            # tags are provided via 3.6.2 Metadata?
            'tags': ['openstack', 'floating-ip'],
        },
        {
            'file': 'templates/openstack-compute.yaml',
            'tags': ['openstack'],
        },
    ]
}


idx = 0
instance_models = {}


class NodeInstance:
  def __init__(self, name, template):
    self.substitution_index = None

    self.name = copy.deepcopy(name)
    self.types = copy.deepcopy(template['types'])
    self.directives = copy.deepcopy(template['directives'])
    self.requirements = copy.deepcopy(template['requirements'])
    self.interfaces = copy.deepcopy(template['interfaces'])

    if "substitute" in self.directives:
      print(f'node {self.name} is marked substitutable')
      print('please choose desired substitution')
      option_list = []

      for t in self.types.keys():
        if t not in substitutions.keys():
          continue
        option_list += substitutions[t]

      for i, item in enumerate(option_list):
        print(f' {i} - {item["file"]}')

      while True:  # blame on me
        choose = int(input('your choise: '))
        if choose in range(len(option_list)):
          print(f'chosen {option_list[choose]["file"]}')

          self.substitution_index = instantiate_template(
              option_list[choose]["file"])
          break

        else:
          print('please, choose correct option')

  def graphviz(self):
    if self.substitution_index is not None:
      return instance_models[self.substitution_index].graphviz()
    else:
      types = list(self.types.keys())
      return f'{self.name} [label="{{{self.name} | {types[0]}}}",shape=record]'

  def deploy(self):
    print(f"deploying {self.name}")
    if self.substitution_index is not None:
      print('sub')
      # instance_models[self.substitution_index].deploy()
    else:
      print(self.interfaces)


class TemplateInstance:
  def __init__(self, idx, template):
    self.idx = idx
    self.template = copy.deepcopy(template)
    self.substitution = copy.deepcopy(template['substitution'])
    self.nodes = {}
    for name, node in template["nodeTemplates"].items():
      self.nodes[name] = NodeInstance(name, node)

  def __repr__(self):
    return ','.join([n.name for n in self.nodes.values()])

  def graphviz(self):
    res = f'''
    subgraph cluster_{self.idx} {{
      color = black;
      label = "Instance {self.idx}";
    '''
    for name, node in self.nodes.items():
      if node.substitution_index is not None:
        res += node.graphviz()
      else:
        res += f'''
        instance_{self.idx}_{node.graphviz()};
        '''
    res += '''
    }
    '''
    return res

  def dump_graphviz(self, path):
    res = f'''
    digraph G {{
      {self.graphviz()}
    }}
    '''

    f = open(f'{path}.dot', "w")
    f.write(res)
    f.close()

    f = open(f'{path}.png', "w")
    pipe = sp.Popen(
      f'dot -Tpng {path}.dot', shell=True, stdout=f, stderr=sp.PIPE)
    res = pipe.communicate()
    f.close()

    if pipe.returncode != 0:
      raise RuntimeError(res[1])


def instantiate_template(path):
  global idx
  global instance_models

  print(f'parsing {path}...')

  inputs = {}

  pipe = sp.Popen(
      f'puccini-tosca parse -s 1 {path}', shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
  res = pipe.communicate()

  if pipe.returncode != 0:
    raise RuntimeError(res[1])

  template = yaml.safe_load(res[0])

  print('please, fill inputs')
  for input_name, input_body in template['inputs'].items():
    if input_body['$value'] is None:
      value = input(f'{input_name}: ')
      inputs[input_name] = value
    else:
      inputs[input_name] = input_body['$value']

  input_str = ''
  if len(inputs.keys()) > 0:
    input_str = '-i "' + \
        ','.join([f'{item[0]}={item[1]}' for item in inputs.items()]) + '"'

  pipe = sp.Popen(
      f'puccini-tosca parse {input_str} {path}', shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
  res = pipe.communicate()

  if pipe.returncode != 0:
    raise RuntimeError(res[1])

  template = yaml.safe_load(res[0])
  template_id = idx + 1
  idx += 1
  template_instance = TemplateInstance(template_id, copy.deepcopy(template))
  instance_models[template_id] = template_instance
  return template_instance.idx


def parse_arguments():
  parser = argparse.ArgumentParser(description='')
  parser.add_argument('template', help='path to the TOSCA template')
  return parser.parse_args()


def main():
  args = parse_arguments()
  try:
    root = instantiate_template(args.template)
    instance_models[root].dump_graphviz('test')
  except RuntimeError as err:
    print(err.args[0].decode())


if __name__ == "__main__":
  main()
