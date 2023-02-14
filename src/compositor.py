import instance_model
import instance_storage
import parser
import tosca_repository


def compose(normalized_template, topology_name):
  print(f'composing {topology_name}')

  topology = instance_model.TopologyTemplateInstance(
    topology_name,
    normalized_template
  )

  for node_name, node in topology.nodes.items():
    print(node_name)
    if "substitute" in node.directives:
      substitute(node)
    elif 'select' in node.directives:
      select(node)

  instance_storage.add_topology(topology)
  return topology


def select(node_type):
  pass



def select_substitution(node_name, options):
  if len(options) == 0:
    raise RuntimeError('cannot substitute')
  elif len(options) == 1:
    return options[0]["file"]

  print(f'please choose desired substitution for node {node_name}')
  
  for i, item in enumerate(options):
    print(f' {i} - {item["file"]}')

  while True:  # blame on me
    choose = int(input('your choice: '))
    if choose in range(len(options)):
      print(f'chosen {options[choose]["file"]}')
      return options[choose]["file"]
    else:
      print('please, choose correct option')


def substitute(node):
  options = tosca_repository.get_substitutions_for_type(node.type)
  chosen_substitution = select_substitution(node.name, options)

  normalized_template = parser.parse(chosen_substitution)
  topology = compose(normalized_template, f'{node.topology.name}_sub_{node.name}')

  map_node(node, topology)


def map_node(node, topology):
  print(topology.definition['substitution'])

  for prop_name, mapping in topology.definition['substitution']['inputPointers'].items():
    if prop_name not in node.attributes.keys():
      continue
    topology.inputs[mapping['target']] = node.attributes[prop_name]

  for attr_name, mapping in topology.definition['substitution']['attributePointers'].items():
    print(mapping)
    if attr_name == 'tosca_name':
      # XXX: only name should be propagated forwards?
      topology\
        .nodes[mapping['nodeTemplateName']]\
        .attributes[mapping['target']] = node.attributes[attr_name]
      continue

    node.attributes[attr_name] = topology\
        .nodes[mapping['nodeTemplateName']]\
        .attributes[mapping['target']]

  for cap_name, mapping in topology.definition['substitution']['capabilityPointers'].items():
    print(mapping)
    topology\
      .nodes[mapping['nodeTemplateName']]\
      .capabilities[mapping['target']] = node.capabilities[cap_name]

  for req_name, mapping in topology.definition['substitution']['requirementPointers'].items():
    print(mapping)