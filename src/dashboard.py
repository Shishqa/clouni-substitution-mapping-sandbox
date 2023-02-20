import os
import subprocess as sp

import compositor


def display_topology(name):
  if not os.path.exists('dashboard'):
    os.makedirs('dashboard')

  topology_status = compositor.query(name)
  display(topology_status)


def display(topology_status):
  topology_name = topology_status['name']
  print(f'displaying {topology_name}')

  res = dump_topology(topology_status['topology'])

  f = open(f'dashboard/{topology_name}.d2', "w")
  f.write(res)
  f.close()

  pipe = sp.Popen(
    f'd2 dashboard/{topology_name}.d2 dashboard/{topology_name}.svg',
    shell=True,
    stdout=sp.PIPE,
    stderr=sp.PIPE
  )
  res = pipe.communicate()

  if pipe.returncode != 0:
    raise RuntimeError(res[1])
  
  for subtopology in topology_status['subtopologies'].values():
    display(subtopology)


def dump_topology(topology):
  res = f'''
  {topology.name}: "Topology {topology.name}" {{
  '''
  if len(topology.inputs) > 0:
    res += dump_attributes(topology.inputs, 'inputs')

  for name, node in topology.nodes.items():
    res += dump_node(node)
  res += '''
  }
  '''
  for name, node in topology.nodes.items():
    for relationship in node.requirements:
      if relationship.target is None:
        continue
      target_topology = relationship.target.topology.name
      res += f'''
      {target_topology} {{ link: "./{target_topology}.svg" }}
      {topology.name}.node_{name}.rel_{relationship.name} -> {target_topology}.node_{relationship.target.name}
      '''
  return res


def dump_attributes(attributes, title):
  res = f'''
  {title} {{
    shape: class
  '''
  for a_name, a_body in attributes.items():
    mark = '+'
    if a_body.is_property:
      mark = '\#'
    res += f'''
    {mark}{a_name}: "{a_body.get()}"
    '''
  res += '''
  }
  '''
  return res


def dump_node(node):
  res = f'''
  node_{node.name}: "{node.name}\\n({node.type})" {{
  '''
  if node.substitution is not None:
    res += f'''
    link: "./{node.substitution}.svg"
    '''
  if not node.abstract:
    res += '''
    style { fill: honeydew }
    '''
  if len(node.attributes) > 0:
    res += dump_attributes(node.attributes, 'attributes')

  for cap_name, cap in node.capabilities.items():
    res += dump_capability(cap)

  for relationship in node.requirements:
    res += dump_relationship(relationship)

  res += '''
  }
  '''
  return res


def dump_relationship(relationship):
  res = f'''
  rel_{relationship.name}: "{relationship.name}\\n({relationship.type})" {{
    shape: parallelogram
  '''
  if len(relationship.attributes) > 0:
    res += dump_attributes(relationship.attributes, 'attributes')
  res += '''
  }
  '''
  if relationship.target is None:
    res += f'''
    rel_{relationship.name}.style.fill: red
    '''
  return res


def dump_capability(capability):
  res = f'''
  {capability.name}: "{capability.name}\\n({capability.type})" {{
  '''
  if len(capability.attributes) > 0:
    res += dump_attributes(capability.attributes, 'attributes')
  res += '''
  }
  '''
  return res
