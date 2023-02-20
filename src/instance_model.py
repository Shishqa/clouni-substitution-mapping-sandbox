import copy
import uuid


def create_value(node, meta, primitive):
  # print(definition)
  # print(meta)
  # print(primitive)

  # if '$functionCall' in definition.keys():
  #   return create_function(node, type_def, definition)

  # if '$list' in definition or type_def['name'] == 'list':
  #   return List(node, type_def, definition)

  if meta['type'] == 'map':
    return Map(node, meta, primitive)

  if meta['type'] == 'version':
    return Version(node, meta, primitive)

  if meta['type'] in {'scalar-unit.time', 'scalar-unit.size'}:
    return ScalarUnit(node, meta, primitive)

  if meta['type'] in {'integer', 'string', 'boolean', 'tosca::PortDef'}:
    return Primitive(node, meta, primitive)

  raise RuntimeError('unknown primitive')
  #return String(node, type_def, definition['$value'])


def create_function(node, meta, function_call):
   #print(meta)
  # print(function_call)

  if function_call['name'] == 'tosca.function.get_input':
    return GetInput(node, meta, function_call['arguments'])

  if function_call['name'] == 'tosca.function.get_property':
    return GetProperty(node, meta, function_call['arguments'])

  if function_call['name'] == 'tosca.function.get_attribute':
    return GetAttribute(node, meta, function_call['arguments'])

  if function_call['name'] == 'tosca.function.concat':
    return Concat(node, meta, function_call['arguments'])

  raise RuntimeError('unknown function')


class ValueInstance:
  def __init__(self, node, meta):
    self.node = node
    self.meta = meta

  def get(self):
    raise RuntimeError('Unimplemented get')


class Primitive(ValueInstance):
  """
  Represents string, boolean
  """
  def __init__(self, node, meta, primitive):
    super().__init__(node, meta)
    self.value = primitive

  def get(self):
    return self.value


class Version(ValueInstance):
  def __init__(self, node, meta, primitive):
    super().__init__(node, meta)
    self.value = primitive['$string']

  def get(self):
    return self.value


class ScalarUnit(ValueInstance):
  def __init__(self, node, meta, primitive):
    super().__init__(node, meta)
    self.value = primitive['$number']

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
  def __init__(self, node, meta, primitive):
    super().__init__(node, meta)

    if primitive is None:
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
      values[key] = value.get()
    return values


class GetInput(ValueInstance):
  def __init__(self, node, meta, args):
    super().__init__(node, meta)
    self.input_name = args[0]['$primitive']

  def get(self):
    return self.node.topology.get_input(self.input_name)


class GetProperty(ValueInstance):
  def __init__(self, node, meta, args):
    super().__init__(node, meta)
    self.args = [e['$primitive'] for e in args]

  def get(self):
    # print('GETPROP', self.args)
    start = self.args[0]
    if start == 'SELF':
      return self.node.get_property(self.args[1:])
    else:
      return self.node.topology.nodes[start].get_property(self.args[1:])


class GetAttribute(ValueInstance):
  def __init__(self, node, meta, args):
    super().__init__(node, meta)
    self.args = [e['$primitive'] for e in args]

  def get(self):
    # print('GETATTR', self.args)
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
      if '$primitive' in arg.keys():
        self.args.append(Primitive(node, {}, arg['$primitive']))
      else:
        # print(arg)
        self.args.append(create_function(node, {}, arg['$functionCall']))

  def get(self):
    strings = [a.get() for a in self.args]
    return ''.join(strings)


class AttributeInstance:
  def __init__(self, node, definition, is_property=False):
    self.node = node
    self.is_property = is_property
    self.definition = copy.deepcopy(definition)

    self.value = None
    if '$primitive' in self.definition.keys():
      if self.definition['$primitive'] is None:
        self.value = Primitive(node, {}, None)
        return
      self.value = create_value(
        node,
        self.definition['$meta'],
        self.definition['$primitive']
      )
      return
    elif '$functionCall' in self.definition.keys():
      self.value = create_function(
        node,
        {},
        self.definition['$functionCall']
      )
      return
    
    raise RuntimeError(f'unknown attribute definition: {self.definition}')

  def get(self):
    return self.value.get()

  def set(self, value):
    self.value = value


class CapabilityInstance:
  def __init__(self, name, node, definition):
    self.name = copy.deepcopy(name)
    self.node = node

    self.definition = copy.deepcopy(definition)
    self.find_type()

    self.attributes = {}

    for prop_name, prop_def in self.definition['properties'].items():
      self.attributes[prop_name] = AttributeInstance(
        self.node,
        prop_def,
        is_property=True
      )

    for attr_name, attr_def in self.definition['attributes'].items():
      self.attributes[attr_name] = AttributeInstance(
        self.node,
        attr_def
      )

  def find_type(self):
    seen = set(self.definition['types'].keys())
    for type_name, type_body in self.definition['types'].items():
      if 'parent' in type_body.keys():
        seen.remove(type_body['parent'])
    self.type = seen.pop()

  def get_property(self, args):
    path = args[0]
    if path in self.attributes.keys():
      attr = self.attributes[path]
      if not attr.is_property:
        raise RuntimeError(f'there is the attribute with name {path}, but it is not a property')
      return attr.get()
    raise RuntimeError('no property')

  def get_attribute(self, args):
    path = args[0]
    if path in self.attributes.keys():
      return self.attributes[path].get()
    raise RuntimeError('no attribute')


class OperationInstance:
  def __init__(self, node, definition):
    self.definition = copy.deepcopy(definition)
    self.implementation = None
    self.node = node

    if self.definition['implementation'] != '':
      self.implementation = self.definition['implementation']

    self.inputs = {}
    for input_name, input_def in self.definition['inputs'].items():
      self.inputs[input_name] = AttributeInstance(node, input_def, is_property=True)


class InterfaceInstance:
  def __init__(self, node, definition):
    self.definition = copy.deepcopy(definition)
    self.abstract = True
    self.node = node

    self.inputs = {}
    for input_name, input_def in self.definition['inputs'].items():
      self.inputs[input_name] = AttributeInstance(node, input_def, is_property=True)

    self.operations = {}
    for op_name, op_def in self.definition['operations'].items():
      self.operations[op_name] = OperationInstance(node, op_def)
      if self.operations[op_name].implementation is not None:
        self.abstract = False


class RelationshipInstance:
  def __init__(self, name, source, target, definition):
    self.name = name
    self.source = source
    self.target = target
    self.definition = copy.deepcopy(definition)

    self.types = copy.deepcopy(self.definition['types'])
    self.find_type()

    self.attributes = {}

    for prop_name, prop_def in self.definition['properties'].items():
      self.attributes[prop_name] = AttributeInstance(self, prop_def, is_property=True)

    for attr_name, attr_def in self.definition['attributes'].items():
      self.attributes[attr_name] = AttributeInstance(self, attr_def)

    self.interfaces = {}
    for interface_name, interface_def in self.definition['interfaces'].items():
      self.interfaces[interface_name] = InterfaceInstance(self, interface_def)


  def find_type(self):
    seen = set(self.types.keys())
    for type_name, type_body in self.types.items():
      if 'parent' in type_body.keys():
        seen.remove(type_body['parent'])
    self.type = seen.pop()


class NodeInstance:
  def __init__(self, name, topology, definition):
    self.name = copy.deepcopy(name)
    self.topology = topology
    self.abstract = True
    self.substitution = None

    self.definition = copy.deepcopy(definition)

    self.types = copy.deepcopy(self.definition['types'])
    self.find_type()

    self.directives = copy.deepcopy(self.definition['directives'])

    self.attributes = {}

    for prop_name, prop_def in self.definition['properties'].items():
      self.attributes[prop_name] = AttributeInstance(self, prop_def, is_property=True)

    for attr_name, attr_def in self.definition['attributes'].items():
      self.attributes[attr_name] = AttributeInstance(self, attr_def)

    self.capabilities = {}
    for cap_name, cap_def in self.definition['capabilities'].items():
      self.capabilities[cap_name] = CapabilityInstance(cap_name, self, cap_def)

    self.interfaces = {}
    for interface_name, interface_def in self.definition['interfaces'].items():
      self.interfaces[interface_name] = InterfaceInstance(self, interface_def)
      if not self.interfaces[interface_name].abstract:
        self.abstract = False

    self.requirements = []

  def find_type(self):
    seen = set(self.types.keys())
    for type_name, type_body in self.types.items():
      if 'parent' in type_body.keys():
        seen.remove(type_body['parent'])
    self.type = seen.pop()

  def get_property(self, args):
    path = args[0]
    rest = args[1:]

    if path in self.attributes.keys():
      attr = self.attributes[path]
      if not attr.is_property:
        raise RuntimeError(f'there is the attribute with name {path}, but it is not a property')
      return attr.get()

    if path in self.capabilities.keys():
      return self.capabilities[path].get_property(rest)

    for r in self.requirements:
      if r.name == path:
        return r.target.get_attribute(rest)

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
        return r.target.get_attribute(rest)

    raise RuntimeError('no attribute')


class TopologyTemplateInstance:
  def __init__(self, name, definition):
    self.name = copy.deepcopy(name)
    self.definition = copy.deepcopy(definition)

    self.inputs = {}
    for input_name, input_def in self.definition['inputs'].items():
      self.inputs[input_name] = AttributeInstance(
        self,
        input_def,
        is_property=True
      )

    self.nodes = {}
    for node_name, node_def in self.definition["nodeTemplates"].items():
      node = NodeInstance(node_name, self, node_def)
      node.attributes['tosca_name'].set(Primitive(self, {'type': 'string'}, node_name))
      node.attributes['tosca_id'].set(Primitive(self, {'type': 'string'}, uuid.uuid4().hex))
      self.nodes[node_name] = node

    for node_name, node in self.nodes.items():
      for req_def in node.definition['requirements']:
        # print(f"{node_name} - {req_def['name']}")
        target = None
        if req_def['nodeTemplateName'] != '':
          target = self.nodes[req_def['nodeTemplateName']]
        node.requirements.append(RelationshipInstance(
          req_def['name'],
          node,
          target,
          req_def['relationship']
        ))

  def get_input(self, input_name):
    if input_name not in self.inputs.keys():
      raise RuntimeError(f'no input named {input_name}')
    return self.inputs[input_name].get()