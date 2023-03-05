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
  return new_state


def deploy(topology_status):
  for node_name in traverse(topology_status):
    node_state = get_node_state(node_name)

    print(node_name, node_state)

    if node_state in ['creating', 'failed']:
      print('rescuing from failed create operation')
      node_state = update_node_state(node_name, 'initial')

    if node_state == 'configuring':
      print('rescuing from failed configure operation')
      node_state = update_node_state(node_name, 'created')

    if node_state == 'starting':
      print('rescuing from failed start operation')
      node_state = update_node_state(node_name, 'configured')

    if node_state == 'initial':
      update_node_state(node_name, 'creating')

      print(f'creating {node_name}')
      run_operation(node_name, 'Standard', 'create')

      node_state = update_node_state(node_name, 'created')

    if node_state == 'created':
      update_node_state(node_name, 'configuring')

      print(f'configuring {node_name}')
      run_operation(node_name, 'Standard', 'configure')

      node_state = update_node_state(node_name, 'configured')

    if node_state == 'configured':
      update_node_state(node_name, 'starting')

      print(f'starting {node_name}')
      run_operation(node_name, 'Standard', 'start')

      node_state = update_node_state(node_name, 'started')


def get_address_by_host(node_name, host):
  topology = instance_storage.get_topology(node_name[0])
  node = topology.nodes[node_name[1]]

  address = None
  if host == 'HOST':
    for req in node.requirements:
      print(req.type)
      if req.type != 'tosca::HostedOn':
        continue
      
      address = req.target.attributes['public_address'].get()
      break

  if host == 'ORCHESTRATOR':
    address = 'localhost'
  
  return address


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

  address = get_address_by_host(node_name, host)
  if address is None:
    raise RuntimeError(f'cannot run operation, no valid address for {host}')

  dependencies = []
  print(node.definition['artifacts'].keys())
  for dependency_name in operation.definition['dependencies']:
    if dependency_name in node.definition['artifacts'].keys():
      dependencies.append({
        'source': dependency_name,
        'dest': node.definition['artifacts'][dependency_name]['targetPath']
      })
    else:
      dependencies.append({
        'source': dependency_name,
        'dest': os.path.basename(d)
      })

  ok, run_outputs = runner.run_artifact(
    address,
    operation.implementation,
    inputs,
    dependencies
  )

  if not ok:
    update_node_state(node_name, 'failed')
    raise RuntimeError(f'failed operation {operation.definition}')

  for output_name, output in operation.outputs.items():
    if output_name not in run_outputs.keys():
      raise RuntimeError(f'output {output_name} not provided')
    output.set(instance_model.Primitive(node, {}, run_outputs[output_name]))
    instance_storage.add_topology(topology)
  
  