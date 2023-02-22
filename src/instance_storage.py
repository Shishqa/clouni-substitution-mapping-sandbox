import os
import pickle

import instance_model

topologies = {}
nodes = {}


def init_database():
  global topologies

  if not os.path.exists('instances'):
    os.makedirs('instances')

  for filename in os.listdir('instances'):
    path = os.path.join('instances', filename)
    with open(path, 'rb') as file:
      topology_name = os.path.splitext(os.path.basename(path))[0]
      # print(topology_name)
      topology = pickle.load(file)
      add_topology(topology)


def dump_database():
  for topology_name, topology in topologies.items():
    path = os.path.join('instances', f'{topology_name}.obj')
    with open(path, 'wb') as file:
      pickle.dump(topology, file)


def add_topology(topology: instance_model.TopologyTemplateInstance):
  global topologies
  global nodes
  topologies[topology.name] = topology
  for node_name, node in topology.nodes.items():
    if node.type not in nodes.keys():
      nodes[node.type] = {}
    nodes[node.type][topology.name + '$' + node_name] = node


def get_topology(name):
  return topologies[name]


def list_topologies():
  return topologies.keys()


def get_nodes_of_type(node_type):
  return list(nodes[node_type].values())
