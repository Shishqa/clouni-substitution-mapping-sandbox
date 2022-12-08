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
  def __init__(self, name, node, attr='properties'):
    self.node = node
    self.name = name
    self.definition = copy.deepcopy(node.definition[attr][name])

  def get(self):
    print(self.definition.keys())
    if '$value' in self.definition.keys():
      value = self.definition["$value"]
      if isinstance(value, dict):
        value = value['$string']
      return value
    elif '$functionCall' in self.definition.keys():
      return self.definition["$functionCall"]["name"]
    else:
      raise RuntimeError('Unknown property type')


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

    self.find_type()

    self.properties = {}
    for prop_name in self.definition['properties'].keys():
      self.properties[prop_name] = PropertyInstance(prop_name, self)

    self.attributes = {}
    for attr_name in self.definition['attributes'].keys():
      self.attributes[attr_name] = AttributeInstance(attr_name, self)

  def find_type(self):
    seen = set(self.definition['types'].keys())
    for type_name, type_body in self.definition['types'].items():
      if 'parent' in type_body.keys():
        seen.remove(type_body['parent'])
    self.type = seen.pop()

  def get_property(self, prop_name):
    return self.properties[prop_name].get()

  def graphviz(self):
    subgraph_name = f'cluster_{self.node.topology.idx}_{self.node.name}_capability_{self.name}'

    res = f'''
    subgraph {subgraph_name} {{
      color = black;
      graph [rankdir = "TB"];
      label = "{self.name} ({self.type})";
      "cap_{subgraph_name}" [shape=point,style=invis];
    '''

    if len(self.properties) > 0:
      res += f'''
      subgraph {subgraph_name}_properties {{
        color = black;
        graph [rankdir = "LR"];
        rank = same;
        label = "properties";
        rank = same;
      '''
      for p_name, p_body in self.properties.items():
        res += f'''
        "{subgraph_name}_prop_{p_name}" [label="{p_name} = {p_body.get()}"];
        '''
      res += '''
      }
      '''

    res += '''
    }
    '''

    return res


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

    self.find_type()

    if "substitute" in self.directives:
      self.init_substitution()
    else:
      self.init()

  def find_type(self):
    seen = set(self.types.keys())
    for type_name, type_body in self.types.items():
      if 'parent' in type_body.keys():
        seen.remove(type_body['parent'])
    self.type = seen.pop()

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

    self.properties = {}

    self.attributes = {}
    for attr_name in self.definition['attributes'].keys():
      self.attributes[attr_name] = AttributeInstance(attr_name, self)
      if attr_name in ['state', 'tosca_id', 'tosca_name']:
        continue
      mapping = instance_models[self.substitution_index].definition['substitution']['attributeMappings'][attr_name]
      instance_models[self.substitution_index]\
          .nodes[mapping['nodeTemplateName']]\
          .attributes[mapping['target']] = self.attributes[attr_name]

    self.capabilities = {}
    for cap_name in self.definition['capabilities'].keys():
      self.capabilities[cap_name] = CapabilityInstance(cap_name, self)
      if cap_name in ['feature']:
        continue
      mapping = instance_models[self.substitution_index].definition['substitution']['capabilityMappings'][cap_name]
      instance_models[self.substitution_index]\
        .nodes[mapping['nodeTemplateName']]\
        .capabilities[mapping['target']] = self.capabilities[cap_name]

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
    subgraph_name = f'cluster_{self.topology.idx}_{self.name}'

    res = f'''
    subgraph {subgraph_name} {{
      penwidth=3;
      color = black;
      graph [rankdir = "TB"];
      label = "{self.name} ({self.type})";
      "node_{subgraph_name}" [shape=point, style=invis];
    '''

    if len(self.properties) > 0:
      res += f'''
      subgraph {subgraph_name}_properties {{
        penwidth=1;
        color = black;
        graph [rankdir = "LR"];
        rank = same;
        label = "properties";
      '''
      for p_name, p_body in self.properties.items():
        res += f'''
        "{subgraph_name}_prop_{p_name}" [label="{p_name} = {p_body.get()}"];
        '''
      res += '''
      }
      '''

    res += f'''
    subgraph {subgraph_name}_capabilities {{
      penwidth=1;
      color = black;
      graph [rankdir = "TB"];
      label = "capabilities";
    '''
    for cap_name, cap in self.capabilities.items():
      if cap.node is not self:
        res += f'''
        subgraph {subgraph_name}_capability_{cap_name} {{
          label="{cap_name} ({cap.type})";
          "cap_{subgraph_name}_capability_{cap_name}" [shape=point,style=invis];
        }}
        "cap_{subgraph_name}_capability_{cap_name}" -> "cap_cluster_{cap.node.topology.idx}_{cap.node.name}_capability_{cap.name}" [
          label="substitute",
          penwidth=3,
          weight=1,
          color=red,
          ltail={subgraph_name}_capability_{cap_name},
          lhead=cluster_{cap.node.topology.idx}_{cap.node.name}_capability_{cap.name}
        ];
        '''
      else:
        res += cap.graphviz()
    res += '''
    }
    '''

    res += '''
    }
    '''

    if self.substitution_index is not None:
      res += instance_models[self.substitution_index].graphviz()


    return res

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

    self.inputs = {}
    for input_name in self.definition['inputs'].keys():
      self.inputs[input_name] = PropertyInstance(input_name, self, attr='inputs')

    self.instantiate_nodes()

  def instantiate_nodes(self):
    self.nodes = {}
    for name in self.definition["nodeTemplates"].keys():
      self.nodes[name] = NodeInstance(name, self)

  def graphviz(self):
    res = f'''
    subgraph cluster_{self.idx} {{
      penwidth=5;
      graph [rankdir = "TB"];
      color = green;
      label = "Instance {self.idx}";
    '''
    if len(self.inputs) > 0:
      res += f'''
      subgraph cluster_{self.idx}_inputs {{
        penwidth=1;
        style=filled;
        fillcolor = yellow;
        graph [rankdir = "LR"];
        rank = same;
        label = "inputs";
      '''
      for p_name, p_body in self.inputs.items():
        res += f'''
        "cluster_{self.idx}_inputs_prop_{p_name}" [label="{p_name} = {p_body.get()}"];
        '''
      res += '''
      }
      '''

    for name, node in self.nodes.items():
      res += f'''
        {node.graphviz()}
        '''

    for name, node in self.nodes.items():
      node_subgraph_name = f'cluster_{node.topology.idx}_{node.name}'
      for req in node.definition['requirements']:
        res += f'''
        "node_{node_subgraph_name}" -> "node_cluster_{node.topology.idx}_{req['nodeTemplateName']}" [
          penwidth=3,
          weight=1,
          ltail={node_subgraph_name}, 
          lhead=cluster_{node.topology.idx}_{req['nodeTemplateName']}
        ];
        '''
    res += '''
    }
    '''
    return res

  def dump_graphviz(self, path):
    res = f'''
    digraph G {{
      margin=10;
      compound=true;
      graph [ranksep=3];
      graph [rankdir = "TB"];
      node [shape = record];
      {self.graphviz()}
    }}
    '''

    f = open(f'{path}.dot', "w")
    f.write(res)
    f.close()

    f = open(f'{path}.svg', "w")
    pipe = sp.Popen(
        f'dot -Tsvg {path}.dot', shell=True, stdout=f, stderr=sp.PIPE)
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
      f'puccini-tosca parse -s 10 {input_str} {path}', shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
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
