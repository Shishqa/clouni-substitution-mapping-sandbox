import os
import argparse
import subprocess as sp
import yaml
import copy
import uuid

substitutions = {}
inventory = {}


selections = []


# visited = set()


idx = 0
instance_models = {}


def create_value(node, type_def, definition):
  print(definition)

  if '$functionCall' in definition.keys():
    return create_function(node, type_def, definition)

  if '$list' in definition or type_def['name'] == 'list':
    return List(node, type_def, definition)

  if '$map' in definition.keys() or type_def['name'] == 'map':
    return Map(node, type_def, definition)

  if type_def['name'] == 'version':
    return Version(node, type_def, definition['$value'])

  if type_def['name'] == 'scalar-unit.time':
    return ScalarUnitTime(node, type_def, definition['$value'])

  if type_def['name'] == 'scalar-unit.size':
    return ScalarUnitSize(node, type_def, definition['$value'])

  return String(node, type_def, definition['$value'])


def create_function(node, type_def, definition):
  func = definition['$functionCall']

  if func['name'] == 'tosca.function.get_input':
    return GetInput(node, type_def, func['arguments'])

  if func['name'] == 'tosca.function.get_property':
    return GetProperty(node, type_def, func['arguments'])

  if func['name'] == 'tosca.function.get_attribute':
    return GetAttribute(node, type_def, func['arguments'])

  if func['name'] == 'tosca.function.concat':
    return Concat(node, type_def, func['arguments'])

  raise RuntimeError('unknown function')


class ValueInstance:
  def __init__(self, node, type_def):
    self.node = node
    self.type = type_def

  def get(self):
    raise RuntimeError('Unimplemented get')


class String(ValueInstance):
  def __init__(self, node, type_def, value):
    super().__init__(node, type_def)
    self.value = value

  def get(self):
    return self.value


class Version(ValueInstance):
  def __init__(self, node, type_def, value):
    super().__init__(node, type_def)
    if value is None:
      self.value = None
      return
    self.value = value['$string']

  def get(self):
    return self.value


class ScalarUnitTime(ValueInstance):
  def __init__(self, node, type_def, value):
    super().__init__(node, type_def)
    if value is None:
      self.value = None
      return
    self.value = value['$string']

  def get(self):
    return self.value


class ScalarUnitSize(ValueInstance):
  def __init__(self, node, type_def, value):
    super().__init__(node, type_def)
    if value is None:
      self.value = None
      return
    self.value = value['$string']

  def get(self):
    return self.value


class List(ValueInstance):
  def __init__(self, node, type_def, definition):
    super().__init__(node, type_def)

    if '$value' in definition.keys() and definition['$value'] is None:
      self.values = None
      return

    self.entry_type = definition['$information']['entry']
    self.values = [create_value(node, self.entry_type, entry)
                   for entry in definition['$list']]

  def get(self):
    if self.values is None:
      return None

    values = [v.get() for v in self.values]
    return values


class Map(ValueInstance):
  def __init__(self, node, type_def, definition):
    super().__init__(node, type_def)

    if '$value' in definition.keys() and definition['$value'] is None:
      self.values = None
      return

    self.values = dict()
    for e in definition['$map']:
      key = e['$key']['$value']
      self.values[key] = create_value(node, e['$information']['type'], e)

  def get(self):
    if self.values is None:
      return None
    values = dict()
    for key, value in self.values.items():
      values = value.get()
    return values


class GetInput(ValueInstance):
  def __init__(self, node, type_def, args):
    super().__init__(node, type_def)
    self.input_name = args[0]['$value']

  def get(self):
    return self.node.topology.get_input(self.input_name)


class GetProperty(ValueInstance):
  def __init__(self, node, type_def, args):
    super().__init__(node, type_def)
    self.args = [e['$value'] for e in args]

  def get(self):
    print('GETPROP', self.args)
    start = self.args[0]
    if start == 'SELF':
      return self.node.get_property(self.args[1:])
    else:
      return self.node.topology.nodes[start].get_property(self.args[1:])


class GetAttribute(ValueInstance):
  def __init__(self, node, type_def, args):
    super().__init__(node, type_def)
    self.args = [e['$value'] for e in args]

  def get(self):
    print('GETATTR', self.args)
    start = self.args[0]
    if start == 'SELF':
      return self.node.get_attribute(self.args[1:])
    else:
      return self.node.topology.nodes[start].get_attribute(self.args[1:])


class Concat(ValueInstance):
  def __init__(self, node, type_def, args):
    super().__init__(node, type_def)
    self.args = []
    for arg in args:
      if '$value' in arg.keys():
        self.args.append(String(node, {}, arg['$value']))
      else:
        self.args.append(create_function(node, {}, arg))

  def get(self):
    strings = [a.get() for a in self.args]
    return ''.join(strings)


class PropertyInstance:
  def __init__(self, node, definition):
    self.node = node
    self.definition = copy.deepcopy(definition)

    self.type = self.definition['$information']['type']
    self.value = create_value(node, self.type, self.definition)

  def get(self):
    return self.value.get()


class AttributeInstance:
  def __init__(self, node, definition):
    self.node = node
    self.definition = copy.deepcopy(definition)

    self.type = self.definition['$information']['type']
    self.value = create_value(node, self.type, self.definition)

  def get(self):
    return self.value.get()

  def set(self, value):
    self.value = value


class CapabilityInstance:
  def __init__(self, name, node):
    self.node = node
    self.name = name
    self.definition = copy.deepcopy(node.definition['capabilities'][name])

    self.find_type()

    self.properties = {}
    for prop_name in self.definition['properties'].keys():
      self.properties[prop_name] = PropertyInstance(
          self, self.definition['properties'][prop_name])

    self.attributes = {}
    for attr_name in self.definition['attributes'].keys():
      self.attributes[attr_name] = AttributeInstance(
          self, self.definition['attributes'][attr_name])

  def find_type(self):
    seen = set(self.definition['types'].keys())
    for type_name, type_body in self.definition['types'].items():
      if 'parent' in type_body.keys():
        seen.remove(type_body['parent'])
    self.type = seen.pop()

  def get_property(self, args):
    path = args[0]
    if path in self.properties.keys():
      return self.properties[path].get()
    raise RuntimeError('no property')

  def get_attribute(self, args):
    path = args[0]
    if path in self.attributes.keys():
      return self.attributes[path].get()
    raise RuntimeError('no attribute')

  def graphviz(self):
    # global visited

    subgraph_name = f'cluster_{self.node.topology.name}_{self.node.name}_capability_{self.name}'
    # if subgraph_name in visited:
    #   print(visited)
    #   return ''

    # visited.add('CAP'+subgraph_name)

    res = f'''
    subgraph {subgraph_name} {{
      color = black;
      graph [rankdir = "TB"];
      label = "{self.name} ({self.type})";
      "cap_{subgraph_name}" [shape=point,style=invis];
    '''

    # if len(self.properties) > 0:
    #   res += f'''
    #   subgraph {subgraph_name}_properties {{
    #     color = black;
    #     graph [rankdir = "LR"];
    #     rank = same;
    #     label = "properties";
    #     rank = same;
    #   '''
    #   for p_name, p_body in self.properties.items():
    #     res += f'''
    #     "{subgraph_name}_prop_{p_name}" [label="{p_name} = {p_body.get()}"];
    #     '''
    #   res += '''
    #   }
    #   '''

    res += '''
    }
    '''

    return res


class RequirementInstance:
  def __init__(self, idx, node):
    self.node = node
    self.idx = idx
    self.definition = copy.deepcopy(node.definition['requirements'][idx])
    self.name = self.definition['name']


class NodeInstance:
  def __init__(self, name, topology):
    self.topology = topology
    self.substitution = None

    self.definition = copy.deepcopy(topology.definition["nodeTemplates"][name])
    self.name = copy.deepcopy(name)
    self.types = copy.deepcopy(self.definition['types'])
    self.directives = copy.deepcopy(self.definition['directives'])

    self.find_type()

    if "substitute" in self.directives:
      self.init_substitution()
    else:
      self.init()

    global inventory
    if self.type not in inventory.keys():
      inventory[self.type] = []
    inventory[self.type].append(self)

  def find_type(self):
    seen = set(self.types.keys())
    for type_name, type_body in self.types.items():
      if 'parent' in type_body.keys():
        seen.remove(type_body['parent'])
    self.type = seen.pop()

  def init(self):
    self.properties = {}
    for prop_name in self.definition['properties'].keys():
      self.properties[prop_name] = PropertyInstance(
          self, self.definition['properties'][prop_name])

    self.attributes = {}
    for attr_name in self.definition['attributes'].keys():
      self.attributes[attr_name] = AttributeInstance(
          self, self.definition['attributes'][attr_name])

      if attr_name == 'tosca_name':
        self.attributes[attr_name].set(String(self, {}, self.name))
      elif attr_name == 'tosca_id':
        self.attributes[attr_name].set(String(self, {}, uuid.uuid4().hex))

    self.capabilities = {}
    for cap_name in self.definition['capabilities'].keys():
      self.capabilities[cap_name] = CapabilityInstance(cap_name, self)

    self.requirements = []
    for i in range(len(self.definition['requirements'])):
      self.requirements.append(RequirementInstance(i, self))

  def init_substitution(self):
    self.select_substitution()

    self.properties = {}
    for prop_name in self.definition['properties'].keys():
      self.properties[prop_name] = PropertyInstance(
          self, self.definition['properties'][prop_name])

    self.attributes = {}
    for attr_name in self.definition['attributes'].keys():
      self.attributes[attr_name] = AttributeInstance(
          self, self.definition['attributes'][attr_name])

      if attr_name == 'tosca_name':
        self.attributes[attr_name].set(String(self, {}, self.name))
      elif attr_name == 'tosca_id':
        self.attributes[attr_name].set(String(self, {}, uuid.uuid4().hex))

      if attr_name in ['state', 'tosca_id', 'tosca_name'] and attr_name not in self.substitution.definition['substitution']['attributeMappings'].keys():
        continue

      mapping = self.substitution.definition['substitution']['attributeMappings'][attr_name]

      if attr_name == 'tosca_name':
        # XXX: only name should be propagated forwards?
        self.substitution\
            .nodes[mapping['nodeTemplateName']]\
            .attributes[mapping['target']] = self.attributes[attr_name]
        continue

      self.attributes[attr_name] = self.substitution\
          .nodes[mapping['nodeTemplateName']]\
          .attributes[mapping['target']]

    self.capabilities = {}
    for cap_name in self.definition['capabilities'].keys():
      self.capabilities[cap_name] = CapabilityInstance(cap_name, self)
      if cap_name in ['feature']:
        continue
      mapping = self.substitution.definition['substitution']['capabilityMappings'][cap_name]
      self.substitution\
          .nodes[mapping['nodeTemplateName']]\
          .capabilities[mapping['target']] = self.capabilities[cap_name]

    self.requirements = {}

  def select_substitution(self):
    print(
        f'\nnode {self.name} is marked substitutable\nin {self.topology.name}\n└({self.topology.path})\n')
    print('please choose desired substitution')

    if self.type not in substitutions.keys():
      raise RuntimeError('cannot substitute')
    option_list = substitutions[self.type]

    if len(option_list) == 1:
      self.substitution = instantiate_template(
          f'{self.topology.name}_{self.name}', option_list[0]["file"])
      return

    for i, item in enumerate(option_list):
      print(f' {i} - {item["file"]}')

    while True:  # blame on me
      choose = int(input('your choice: '))
      if choose in range(len(option_list)):
        print(f'chosen {option_list[choose]["file"]}')

        self.substitution = instantiate_template(
            f'{self.topology.name}_{self.name}', option_list[choose]["file"])
        break

      else:
        print('please, choose correct option')

  def get_property(self, args):
    path = args[0]
    rest = args[1:]

    if path in self.properties.keys():
      return self.properties[path].get()

    if path in self.capabilities.keys():
      return self.capabilities[path].get_property(rest)

    for r in self.requirements:
      if r.name == path:
        return self.topology.nodes[r.definition['nodeTemplateName']].get_property(rest)

    raise RuntimeError('no property')

  def get_attribute(self, args):
    path = args[0]
    rest = args[1:]

    if path in self.attributes.keys():
      return self.attributes[path].get()

    if path in self.capabilities.keys():
      return self.capabilities[path].get_attribute(rest)

    for r in self.requirements:
      if r.name == path:
        return self.topology.nodes[r.definition['nodeTemplateName']].get_attribute(rest)

    raise RuntimeError('no attribute')

  def graphviz(self):
    # global visited

    subgraph_name = f'cluster_{self.topology.name}_{self.name}'
    # if subgraph_name in visited:
    #   print(visited)
    #   return ''

    # visited.add('NODE'+subgraph_name)

    res = f'''
    subgraph {subgraph_name} {{
      penwidth=3;
      color = black;
      graph [rankdir = "TB"];
      label = "{self.name} ({self.type})";
      "node_{subgraph_name}" [shape=point, style=invis];
    '''

    # if len(self.properties) > 0:
    #   res += f'''
    #   subgraph {subgraph_name}_properties {{
    #     penwidth=1;
    #     color = black;
    #     graph [rankdir = "LR"];
    #     rank = same;
    #     label = "properties";
    #   '''
    #   for p_name, p_body in self.properties.items():
    #     res += f'''
    #     "{subgraph_name}_prop_{p_name}" [label="{p_name} = {p_body.get()}"];
    #     '''
    #   res += '''
    #   }
    #   '''

    # if len(self.attributes) > 0:
    #   res += f'''
    #   subgraph {subgraph_name}_attributes {{
    #     penwidth=1;
    #     color = black;
    #     graph [rankdir = "LR"];
    #     rank = same;
    #     label = "attributes";
    #   '''
    #   for a_name, a_body in self.attributes.items():
    #     res += f'''
    #     "{subgraph_name}_attr_{a_name}" [label="{a_name} = {a_body.get()}"];
    #     '''
    #   res += '''
    #   }
    #   '''

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
        "cap_{subgraph_name}_capability_{cap_name}" -> "cap_cluster_{cap.node.topology.name}_{cap.node.name}_capability_{cap.name}" [
          label="substitute",
          penwidth=3,
          weight=1,
          color=red,
          ltail={subgraph_name}_capability_{cap_name},
          lhead=cluster_{cap.node.topology.name}_{cap.node.name}_capability_{cap.name}
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

    if self.substitution is not None:
      res += self.substitution.graphviz()

    return res

  def deploy(self):
    print(f"\ndeploying {self.name}")
    if self.substitution is not None:
      self.substitution.deploy()
    else:
      ops = self.definition['interfaces']['Standard']['operations']
      ops_order = ['create', 'configure', 'start']
      for op_name in ops_order:
        if ops[op_name]["implementation"] != '':
          print(f'{op_name}: {ops[op_name]["implementation"]}')
          print(ops[op_name]['inputs'])
          op_inputs = {}
          for input_name in ops[op_name]['inputs'].keys():
            print(input_name)
            op_inputs[input_name] = PropertyInstance(
                self, ops[op_name]['inputs'][input_name])

            value = op_inputs[input_name].get()
            print('\t', value)


class TopologyTemplateInstance:
  def __init__(self, name, definition, path):
    self.name = name
    self.definition = copy.deepcopy(definition)
    self.path = path
    self.instance_models = {}

    self.inputs = {}
    for input_name in self.definition['inputs'].keys():
      self.inputs[input_name] = PropertyInstance(
          self, self.definition['inputs'][input_name])

    self.instantiate_nodes()

  def instantiate_nodes(self):
    global selections

    self.nodes = {}
    for name in self.definition["nodeTemplates"].keys():
      if "select" in self.definition["nodeTemplates"][name]["directives"]:
        selections.append({'instance': self, 'node': name})
        print("select", name)
        continue
      self.nodes[name] = NodeInstance(name, self)

  def get_input(self, input_name):
    return self.inputs[input_name].get()

  def graphviz(self):
    # global visited
    cluster_name = f'cluster_{self.name}'

    # if cluster_name in visited:
    #   print(visited)
    #   return ''

    # visited.add('TOPOLOGY'+cluster_name)

    res = f'''
    subgraph cluster_{self.name} {{
      penwidth=5;
      graph [rankdir = "TB"];
      color = green;
      label = "Instance {self.name} ({self.path})";
    '''
    if len(self.inputs) > 0:
      res += f'''
      subgraph cluster_{self.name}_inputs {{
        penwidth=1;
        style=filled;
        fillcolor = yellow;
        graph [rankdir = "LR"];
        rank = same;
        label = "inputs";
      '''
      for p_name, p_body in self.inputs.items():
        res += f'''
        "cluster_{self.name}_inputs_prop_{p_name}" [label="{p_name} = {p_body.get()}"];
        '''
      res += '''
      }
      '''

    for name, node in self.nodes.items():
      if node.topology.name != self.name:
        continue
      res += f'''
        {node.graphviz()}
        '''

    for name, node in self.nodes.items():
      node_subgraph_name = f'cluster_{node.topology.name}_{node.name}'
      for req in node.definition['requirements']:
        if req['nodeTemplateName'] == '':
          continue
        res += f'''
        "node_{node_subgraph_name}" -> "node_cluster_{node.topology.nodes[req['nodeTemplateName']].topology.name}_{req['nodeTemplateName']}" [
          penwidth=3,
          weight=1,
          ltail={node_subgraph_name}, 
          lhead=cluster_{node.topology.nodes[req['nodeTemplateName']].topology.name}_{req['nodeTemplateName']}
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


def instantiate_template(name, path, inputs={}):
  # global idx
  # global instance_models

  print(f'\nparsing {path}...')

  inputs = {}

  pipe = sp.Popen(
      f'puccini-tosca parse -s 1 {path}', shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
  res = pipe.communicate()

  if pipe.returncode != 0:
    raise RuntimeError(res[1].decode())

  template = yaml.safe_load(res[0])

  # if len(template['inputs']) > 0:
  #   print('\nplease, fill inputs')
  # for input_name, input_body in template['inputs'].items():
  #   if input_body['$value'] is None:
  #     value = input(f'{input_name}: ')
  #     inputs[input_name] = value
  #   else:
  #     inputs[input_name] = input_body['$value']

  input_str = ''
  # if len(inputs.keys()) > 0:
  #   input_str = '-i "' + \
  #       ','.join([f'{item[0]}={item[1]}' for item in inputs.items()]) + '"'

  pipe = sp.Popen(
      f'puccini-tosca parse -s 10 {input_str} {path}', shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
  res = pipe.communicate()

  if pipe.returncode != 0:
    raise RuntimeError(res[1].decode())

  definition = yaml.safe_load(res[0])
  return TopologyTemplateInstance(name, definition, path)


def parse_arguments():
  parser = argparse.ArgumentParser(description='')
  parser.add_argument('template', help='path to the TOSCA template')
  return parser.parse_args()


def init_substitution_database():
  global substitutions

  for filename in os.listdir('templates'):
    path = os.path.join('templates', filename)

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
    if substitution_type not in substitutions:
      substitutions[substitution_type] = []

    substitutions[substitution_type].append({'file': path})


def main():
  args = parse_arguments()
  try:
    init_substitution_database()

    root = instantiate_template(os.path.basename(os.path.splitext(args.template)[0]), args.template)

    for selection in selections:
      name = selection['node']
      topology = selection['instance']

      print(
          f'\nnode {name} is marked selectable\nin instance {topology.name}\n└({topology.path})\n')
      print('please choose desired node from inventory')

      types = topology.definition["nodeTemplates"][name]["types"]
      seen = set(types.keys())
      for type_name, type_body in types.items():
        if 'parent' in type_body.keys():
          seen.remove(type_body['parent'])
      node_type = seen.pop()

      if node_type not in inventory.keys():
        raise RuntimeError('cannot select')
      option_list = inventory[node_type]

      if len(option_list) == 1:
        topology.nodes[name] = option_list[0]
        continue

      for i, node in enumerate(option_list):
        print(
            f' {i} - instance {node.topology.name} ({node.topology.path}) : {node.name}')

      while True:  # blame on me
        choose = int(input('your choice: '))
        if choose in range(len(option_list)):
          print(f'chosen {choose}')
          topology.nodes[name] = option_list[choose]
          break
        else:
          print('please, choose correct option')

    root.dump_graphviz('test')

    # instance_models[root].deploy()
  except RuntimeError as err:
    print(err.args[0])


if __name__ == "__main__":
  main()
