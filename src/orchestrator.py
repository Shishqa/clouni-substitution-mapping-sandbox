import graphlib

import compositor
import instance_model


def traverse_topology(topology_name):
  topology_status = compositor.query(topology_name)
  if not topology_status['fulfilled']:
    raise RuntimeError('Cannot traverse incomplete topology')
  deploy(topology_status)
  

def traverse(topology_status):
  topology = topology_status['topology']

  ts = graphlib.TopologicalSorter()
  for node_name, node in topology.nodes.items():
    ts.add(node_name)
    for rel in node.requirements:
      if rel.target.topology.name != topology.name:
        continue
      ts.add(node_name, rel.target.name)

  for node_name in ts.static_order():
    node = topology.nodes[node_name]
    
    if node.substitution is not None:
      for sub_node in traverse(topology_status['subtopologies'][node.substitution]):
        yield sub_node
    else:
      yield node


def update_node_state(node, new_state):
  node.attributes['state'].set(instance_model.Primitive(node, {}, new_state))
  compositor.update(node.topology)


def deploy(topology_status):
  topology = topology_status['topology']

  for node in traverse(topology_status):
    print(node.name)
    update_node_state(node, 'creating')

    op = node.interfaces['Standard'].operations['create']
    print(op.definition)
    inputs = { name: inp.get() for name, inp in op.inputs.items() }
    print(inputs)

    update_node_state(node, 'created')
    update_node_state(node, 'configuring')

    op = node.interfaces['Standard'].operations['configure']
    print(op.definition)
    inputs = { name: inp.get() for name, inp in op.inputs.items() }
    print(inputs)

    update_node_state(node, 'configured')
    update_node_state(node, 'starting')

    op = node.interfaces['Standard'].operations['start']
    print(op.definition)
    inputs = { name: inp.get() for name, inp in op.inputs.items() }
    print(inputs)

    update_node_state(node, 'started')
