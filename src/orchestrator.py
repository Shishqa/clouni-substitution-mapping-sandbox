import graphlib

import compositor
import instance_model
import instance_storage
import runner


def traverse_topology(topology_name):
  topology_status = compositor.query(topology_name)
  if not topology_status['fulfilled']:
    raise RuntimeError('Cannot traverse incomplete topology')
  deploy(topology_status)
  

def traverse(topology_status):
  topology = instance_storage.get_topology(topology_status['name'])

  ts = graphlib.TopologicalSorter()
  for node_name, node in topology.nodes.items():
    ts.add(node_name)
    for rel in node.requirements:
      if rel.target is None:
        continue
      if rel.target.topology.name != topology.name:
        continue
      ts.add(node_name, rel.target.name)

  for node_name in ts.static_order():
    node = topology.nodes[node_name]
    
    if node.substitution is not None:
      for sub_node in traverse(topology_status['subtopologies'][node.substitution]):
        yield sub_node
    
    yield (topology.name, node.name)


def get_node_state(node_name):
  topology = instance_storage.get_topology(node_name[0])
  node = topology.nodes[node_name[1]]
  return node.attributes['state'].get()


def update_node_state(node_name, new_state):
  topology = instance_storage.get_topology(node_name[0])
  node = topology.nodes[node_name[1]]
  node.attributes['state'].set(instance_model.Primitive(node, {}, new_state))
  instance_storage.add_topology(topology)


def deploy(topology_status):
  for node_name in traverse(topology_status):
    node_state = get_node_state(node_name)

    print(node_name, node_state)

    if node_state in ['creating', 'configuring', 'starting']:
      raise RuntimeError('somebody already operates on node')

    if node_state == 'initial':
      update_node_state(node_name, 'creating')

      print(f'creating {node_name}')
      run_operation(node_name, 'Standard', 'create')

      update_node_state(node_name, 'created')

    if node_state in ['initial', 'created']:
      update_node_state(node_name, 'configuring')

      print(f'configuring {node_name}')
      run_operation(node_name, 'Standard', 'configure')

      update_node_state(node_name, 'configured')

    if node_state in ['initial', 'created', 'configured']:
      update_node_state(node_name, 'starting')

      print(f'starting {node_name}')
      run_operation(node_name, 'Standard', 'start')

      update_node_state(node_name, 'started')


def run_operation(node_name, interface, operation):
  topology = instance_storage.get_topology(node_name[0])
  node = topology.nodes[node_name[1]]
  operation = node.interfaces[interface].operations[operation]

  if operation.implementation is None:
    return

  print(operation.definition)
  inputs = { name: inp.get() for name, inp in operation.inputs.items() }
  print(inputs)
  
  host = 'SELF'
  if 'host' in operation.definition.keys():
    host = operation.definition['host']

  if host != 'ORCHESTRATOR':
    raise RuntimeError(f'cannot run operation on {host}')

  address = 'localhost'

  ok, run_outputs = runner.run_artifact(
    address,
    operation.implementation,
    inputs,
    operation.definition['dependencies']
  )

  if not ok:
    update_node_state(node_name, 'failed')
    raise RuntimeError(f'failed operation {operation.definition}')

  for output_name, output in operation.outputs.items():
    if output_name not in run_outputs.keys():
      raise RuntimeError(f'output {output_name} not provided')
    output.set(instance_model.Primitive(node, {}, run_outputs[output_name]))
    instance_storage.add_topology(topology)
  
  