import copy

import instance_model
import instance_storage
import tosca_repository


def instantiate(normalized_template, topology_name):
  # print(f'composing {topology_name}')

  topology = instance_model.TopologyTemplateInstance(
    topology_name,
    normalized_template
  )
  instance_storage.add_topology(topology)
  return query(topology_name)


def query(topology_name):
  topology = instance_storage.get_topology(topology_name)
  result = {
    'name': topology_name,
    'topology': copy.deepcopy(topology),
    'subtopologies': {},
    'fulfilled': True,
    'issues': [],
  }

  for node_name, node in topology.nodes.items():
    if 'substitute' in node.directives:
      if node.substitution is None:
        options = tosca_repository.get_substitutions_for_type(node.type)
        result['issues'].append({
          'type': 'substitute',
          'target': node_name,
          'options': options
        })
        result['fulfilled'] = False
        continue
      
      substitution = query(node.substitution)
      result['subtopologies'][node.substitution] = substitution
      if not substitution['fulfilled']:
        result['fulfilled'] = False

    elif 'select' in node.directives:
      result['fulfilled'] = False

  return result


def fulfill(topology_name, actions):
  topology = instance_storage.get_topology(topology_name)

  for action in actions:
    if action['type'] == 'substitute':
      normalized_template = tosca_repository.get_template(action['template'])
      substitution = instantiate(
        normalized_template,
        f'{topology_name}_sub_{action["target"]}'
      )
      map_node(topology.nodes[action["target"]], substitution['topology'])
    elif action['type'] == 'select':
      pass

  return query(topology_name)


def update(topology):
  instance_storage.add_topology(topology)
  return query(topology.name)


def map_node(node, topology):
  # print(topology.definition['substitution'])

  for prop_name, mapping in topology.definition['substitution']['inputPointers'].items():
    if prop_name not in node.attributes.keys():
      # TODO: better propagation
      continue
    topology.inputs[mapping['target']] = node.attributes[prop_name]

  for attr_name, mapping in topology.definition['substitution']['attributePointers'].items():
    # print(mapping)
    node.attributes[attr_name] = topology\
        .nodes[mapping['nodeTemplateName']]\
        .attributes[mapping['target']]

  for cap_name, mapping in topology.definition['substitution']['capabilityPointers'].items():
    # print(mapping)
    abstract_capability = node.capabilities[cap_name]
    topology_capability = topology\
      .nodes[mapping['nodeTemplateName']]\
      .capabilities[mapping['target']]
    for attr_name in abstract_capability.attributes.keys():
      attr = abstract_capability.attributes[attr_name]
      if attr.is_property:
        topology_capability.attributes[attr_name] = attr
      else:
        abstract_capability.attributes[attr_name] = topology_capability.attributes[attr_name]
      

    # topology\
    #   .nodes[mapping['nodeTemplateName']]\
    #   .capabilities[mapping['target']] = node.capabilities[cap_name]

  for req_name, mapping in topology.definition['substitution']['requirementPointers'].items():
    # print('REQUIREMENTS')
    # print(mapping)
    nodeTarget = topology.nodes[mapping['nodeTemplateName']]
    reqTargetId = None
    for i in range(len(nodeTarget.requirements)):
      node_relationship = nodeTarget.requirements[i]
      if node_relationship.name == mapping['target']:
        reqTargetId = i
        break
    nodeTarget.requirements.pop(reqTargetId)

    for relationship in node.requirements:
      if relationship.name != req_name:
        continue
      topology\
        .nodes[mapping['nodeTemplateName']]\
        .requirements.append(relationship)

  node.substitution = topology.name

  instance_storage.add_topology(node.topology)
  instance_storage.add_topology(topology)
