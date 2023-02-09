import os
import pickle

import instance_model

topologies = {}

# nodes = {}
# nodes_by_type = {}


def init_database():
  global topologies

  if not os.path.exists('instances'):
    os.makedirs('instances')

  for filename in os.listdir('instances'):
    path = os.path.join('instances', filename)
    with open(path, 'rb') as file:
      topology_name = os.path.splitext(os.path.basename(path))[0]
      print(topology_name)
      topology = pickle.load(file)
      topologies[topology_name] = topology


def dump_database():
  for topology_name, topology in topologies.items():
    path = os.path.join('instances', f'{topology_name}.obj')
    with open(path, 'wb') as file:
      pickle.dump(topology, file)


def add_topology(topology: instance_model.TopologyTemplateInstance):
  global topologies
  topologies[topology.name] = topology


def get_topology(name):
  return topologies[name]


def list_topologies():
  return topologies.keys()



# for node_name, node_instance in topology_instance.nodes.items():
  #   add_node(f'{name}.{node_name}', node_instance)


# def add_node(name, instance: instance_model.NodeInstance):
#   global instances
#   global instance_by_name
#   global instance_by_type

#   instances.append(node)
#   node_idx = len(instances) - 1

#   if name not in instance_by_name:
#     instance_by_name[name] = set()
#   instance_by_name[name].add(node_idx)

#   for node_type in node['types'].keys():
#     if node_type not in instance_by_type.keys():
#       instance_by_type[node_type] = set()
#     instance_by_type[node_type].add(node_idx)

# def get_nodes_of_types(types):
#   options = set()
#   for node_type in types.keys():
#     if node_type in instance_by_type.keys():
#       options = options.union(instance_by_type[node_type])
#   return list(map(lambda opt_idx: instances[opt_idx], options))

