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


class PropertyInstance:
  def __init__(self, name, node):
    self.node = node
    self.name = name
    self.definition = copy.deepcopy(node.definition['properties'][name])

  def get(self):
    print(self.definition.keys())
    return self.definition['$value']


class AttributeInstance:
  def __init__(self, name, node):
    self.node = node
    self.name = name
    self.definition = copy.deepcopy(node.definition['attributes'][name])


class CapabilityInstance:
  def __init__(self, name, node):
    self.node = node
    self.name = name
    self.definition = copy.deepcopy(node.definition['capabilities'][name])
    self.properties = {}
    for prop_name in self.definition['properties'].keys():
      self.properties[prop_name] = PropertyInstance(prop_name, self)

  def get_property(self, prop_name):
    return self.properties[prop_name].get()


class RequirementInstance:
  def __init__(self, idx, node):
    self.node = node
    self.idx = idx
    self.definition = copy.deepcopy(node.definition['requirements'][idx])


class NodeInstance:
  def __init__(self, name, topology):
    self.topology = topology
    self.substitution_index = None

    self.definition = copy.deepcopy(topology.definition["nodeTemplates"][name])
    self.name = copy.deepcopy(name)
    self.types = copy.deepcopy(self.definition['types'])
    self.directives = copy.deepcopy(self.definition['directives'])

    # self.requirements = copy.deepcopy(template['requirements'])
    # self.interfaces = copy.deepcopy(template['interfaces'])
    # self.properties = copy.deepcopy(template['properties'])

    if "substitute" in self.directives:
      self.init_substitution()
      # print(instance_models[self.substitution_index].substitution)
      # keys = ['capabilityMappings', 'requirementMappings', 'propertyMappings', 'attributeMappings', 'interfaceMappings']
    else:
      self.init()

  def init(self):
    self.properties = {}
    for prop_name in self.definition['properties'].keys():
      self.properties[prop_name] = PropertyInstance(prop_name, self)

    self.attributes = {}
    for attr_name in self.definition['attributes'].keys():
      self.attributes[attr_name] = AttributeInstance(attr_name, self)

    self.capabilities = {}
    for cap_name in self.definition['capabilities'].keys():
      self.capabilities[cap_name] = CapabilityInstance(cap_name, self)

    self.requirements = []
    for i in range(len(self.definition['requirements'])):
      self.requirements.append(RequirementInstance(i, self))

  def init_substitution(self):
    self.select_substitution()

  def select_substitution(self):
    print(f'\nnode {self.name} is marked substitutable')
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

  def get_property(self, path, args):
    if path != 'SELF':
      # try find in topology
      rest = len(args > 1) and args[1:] or []
      return self.node.topology.nodes['path'].get_property(args[0], rest)

  def graphviz(self):
    types = list(self.types.keys())
    props_label = ''
    if len(self.definition['properties']) > 0:
      props = []
      for p_name, p_body in self.definition['properties'].items():
        if '$value' in p_body.keys():
          value = p_body["$value"]
          if '$string' in value:
            value = value['$string']
          props.append(f'{p_name}: {value}')
        elif '$functionCall' in p_body.keys():
          props.append(f'{p_name}: {p_body["$functionCall"]["name"]}')
        else:
          props.append(p_name)
      props_label = '|'.join(props)

    return f'[label="{{ {self.name} | {types[0]} { f"| {props_label}" if props_label != "" else "" } }}",shape=record]'

  def deploy(self):
    print(f"\ndeploying {self.name}")
    if self.substitution_index is not None:
      print('TODO: parse substitution mapping interface')
      instance_models[self.substitution_index].deploy()
    else:
      ops = self.definition['interfaces']['Standard']['operations']
      ops_order = ['create', 'configure', 'start']
      for op_name in ops_order:
        if ops[op_name]["implementation"] != '':
          print(f'{op_name}: {ops[op_name]["implementation"]}')


class TopologyTemplateInstance:
  def __init__(self, idx, definition):
    self.idx = idx
    self.definition = copy.deepcopy(definition)
    # self.substitution = copy.deepcopy(template['substitution'])
    # self.inputs = copy.deepcopy(inputs)
    # for input_name, input_body in self.template['inputs'].items():
    #   print(input_name)
    #   print(input_body)

    self.instantiate_nodes()

  def instantiate_nodes(self):
    self.nodes = {}
    for name in self.definition["nodeTemplates"].keys():
      self.nodes[name] = NodeInstance(name, self)

  def graphviz(self):
    res = f'''
    subgraph cluster_{self.idx} {{
      color = black;
      label = "Instance {self.idx}";
    '''
    # if len(self.definition['inputs']) > 0:
    #   res += f'''
    #     instance_{self.idx}_inputs [label="{{ inputs | { '|'.join(f"{x[0]}: {x[1]}" for x in self.inputs.items()) } }}", shape=record];
    #   '''
    for name, node in self.nodes.items():
      if node.substitution_index is not None:
        res += f'''
        instance_{self.idx}_{name} {node.graphviz()};
        {instance_models[node.substitution_index].graphviz()}
        '''
      else:
        res += f'''
        instance_{self.idx}_{name} {node.graphviz()};
        '''
    for name, node in self.nodes.items():
      if node.substitution_index is not None:
        sub_template = instance_models[node.substitution_index]
        sub_nodes = list(sub_template.nodes.keys())
        res += f'''
        instance_{self.idx}_{node.name} -> instance_{sub_template.idx}_{sub_nodes[0]} [label="substituted with", lhead="cluster_{sub_template.idx}"];
        '''

      for req in node.definition['requirements']:
        res += f'''
        instance_{self.idx}_{node.name} -> instance_{self.idx}_{req['nodeTemplateName']};
        '''

    res += '''
    }
    '''
    return res

  def dump_graphviz(self, path):
    res = f'''
    digraph G {{
      compound=true;
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

  def get_deploy_order(self):
    to_visit = set(self.nodes.keys())
    edges = {}
    for name, node in self.nodes.items():
      for req in node.definition['requirements']:
        if req['nodeTemplateName'] in to_visit:
          to_visit.remove(req['nodeTemplateName'])
        if req['nodeTemplateName'] not in edges.keys():
          edges[req['nodeTemplateName']] = set()
        edges[req['nodeTemplateName']].add(name)

    deploy_order = []
    while len(to_visit) > 0:
      n = to_visit.pop()
      deploy_order.append(n)
      for req in self.nodes[n].definition['requirements']:
        edges[req["nodeTemplateName"]].remove(n)
        if len(edges[req["nodeTemplateName"]]) == 0:
          to_visit.add(req["nodeTemplateName"])
          edges.pop(req["nodeTemplateName"])

    if len(edges.keys()) > 0:
      raise RuntimeError('deploy graph has a cycle!')

    deploy_order.reverse()
    return deploy_order

  def deploy(self):
    print(f'\ndeploying instance_{idx}')
    order = self.get_deploy_order()
    for n in order:
      self.nodes[n].deploy()


def instantiate_template(path):
  global idx
  global instance_models

  print(f'\nparsing {path}...')

  inputs = {}

  pipe = sp.Popen(
      f'puccini-tosca parse -s 1 {path}', shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
  res = pipe.communicate()

  if pipe.returncode != 0:
    raise RuntimeError(res[1])

  template = yaml.safe_load(res[0])

  if len(template['inputs']) > 0:
    print('\nplease, fill inputs')
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

  definition = yaml.safe_load(res[0])
  instance_id = idx + 1
  idx += 1
  instance_models[instance_id] = TopologyTemplateInstance(
      instance_id, definition)
  return instance_id


def parse_arguments():
  parser = argparse.ArgumentParser(description='')
  parser.add_argument('template', help='path to the TOSCA template')
  return parser.parse_args()


def main():
  args = parse_arguments()
  try:
    root = instantiate_template(args.template)
    instance_models[root].dump_graphviz('test')
    instance_models[root].deploy()
  except RuntimeError as err:
    print(err.args[0].decode())


if __name__ == "__main__":
  main()
