

instances = []
instance_by_name = {}
instance_by_type = {}

def get_nodes_of_types(types):
  options = set()
  for node_type in types.keys():
    if node_type in instance_by_type.keys():
      options = options.union(instance_by_type[node_type])
  return list(map(lambda opt_idx: instances[opt_idx], options))


def add_instance(name, node):
  global instances
  global instance_by_name
  global instance_by_type

  instances.append(node)
  node_idx = len(instances) - 1

  if name not in instance_by_name:
    instance_by_name[name] = set()
  instance_by_name[name].add(node_idx)

  for node_type in node['types'].keys():
    if node_type not in instance_by_type.keys():
      instance_by_type[node_type] = set()
    instance_by_type[node_type].add(node_idx)
