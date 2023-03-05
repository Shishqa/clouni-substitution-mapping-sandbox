import os
import pickle

import instance_model

topologies = {}
nodes = {}


def init_database():
  global topologies

  if not os.path.exists('instances'):
    os.makedirs('instances')

  if not os.path.exists('instances/.topologies'):
    return

  with open('instances/.topologies', 'rb') as file:
    topologies = pickle.load(file)


def dump_database():
  with open('instances/.topologies', 'wb') as file:
    pickle.dump(topologies, file)


def add_topology(topology: instance_model.TopologyTemplateInstance):
  global topologies
  global nodes
  topologies[topology.name] = topology
  for node_name, node in topology.nodes.items():
    if node.type not in nodes.keys():
      nodes[node.type] = {}
    nodes[node.type][topology.name + '$' + node_name] = node
  dump_database()

def get_topology(name):
  return topologies[name]


def list_topologies():
  return topologies.keys()


def get_nodes_of_type(node_type):
  return list(nodes[node_type].values())
