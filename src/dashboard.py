import os
import subprocess as sp

import instance_storage


def display_topology(name, engine='graphviz'):
  if not os.path.exists('dashboard'):
    os.makedirs('dashboard')

  topology = instance_storage.get_topology(name)
  if engine == 'graphviz':
    dump_graphviz(topology)
  else:
    raise RuntimeError('unsupported display engine')


def dump_graphviz(topology):
    res = f'''
    digraph G {{
      margin=10;
      compound=true;
      graph [ranksep=3];
      graph [rankdir = "TB"];
      node [shape = record];
      {topology_graphviz(topology)}
    }}
    '''

    f = open(f'dashboard/{topology.name}.dot', "w")
    f.write(res)
    f.close()

    f = open(f'dashboard/{topology.name}.svg', "w")
    pipe = sp.Popen(
        f'dot -Tsvg dashboard/{topology.name}.dot', shell=True, stdout=f, stderr=sp.PIPE)
    res = pipe.communicate()
    f.close()

    if pipe.returncode != 0:
      raise RuntimeError(res[1])


def topology_graphviz(topology):
  subgraph_name = f'cluster_{topology.name}'

  res = f'''
  subgraph {subgraph_name} {{
    penwidth=5;
    graph [rankdir = "TB"];
    color = green;
    label = "Instance {topology.name}";
  '''
  if len(topology.inputs) > 0:
    res += f'''
    subgraph {subgraph_name}_inputs {{
      penwidth=1;
      style=filled;
      fillcolor = yellow;
      graph [rankdir = "LR"];
      rank = same;
      label = "inputs";
    '''
    for prop_name, prop in topology.inputs.items():
      res += f'''
      "{subgraph_name}_inputs_prop_{prop_name}" [label="{prop_name} = {prop.get()}"];
      '''
    res += '''
    }
    '''

  for name, node in topology.nodes.items():
    if node.topology.name != topology.name:
      continue
    res += f'''
      {node_graphviz(subgraph_name, node)}
      '''

  for name, node in topology.nodes.items():
    node_subgraph_name = f'{subgraph_name}_node_{node.name}'
    for relationship in node.requirements:
      if relationship.target is None:
        # TODO: display this
        continue
      else:
        res += f'''
        "node_{node_subgraph_name}" -> "node_cluster_{relationship.target.topology.name}_node_{relationship.target.name}" [
          penwidth=3,
          weight=1,
          ltail={node_subgraph_name}, 
          lhead=cluster_{relationship.target.topology.name}_node_{relationship.target.name}
        ];
        '''
  res += '''
  }
  '''
  return res


def node_graphviz(cluster_prefix, node):

  subgraph_name = f'{cluster_prefix}_node_{node.name}'

  res = f'''
  subgraph {subgraph_name} {{
    penwidth=3;
    color = black;
    graph [rankdir = "TB"];
    label = "{node.name} ({node.type})";
    "node_{subgraph_name}" [shape=point, style=invis];
  '''

  if len(node.properties) > 0:
    res += f'''
    subgraph {subgraph_name}_properties {{
      penwidth=1;
      color = black;
      graph [rankdir = "LR"];
      rank = same;
      label = "properties";
    '''
    for p_name, p_body in node.properties.items():
      res += f'''
      "{subgraph_name}_prop_{p_name}" [label="{p_name} = {p_body.get()}"];
      '''
    res += '''
    }
    '''

  if len(node.attributes) > 0:
    res += f'''
    subgraph {subgraph_name}_attributes {{
      penwidth=1;
      color = black;
      graph [rankdir = "LR"];
      rank = same;
      label = "attributes";
    '''
    for a_name, a_body in node.attributes.items():
      res += f'''
      "{subgraph_name}_attr_{a_name}" [label="{a_name} = {a_body.get()}"];
      '''
    res += '''
    }
    '''

  res += f'''
  subgraph {subgraph_name}_capabilities {{
    penwidth=1;
    color = black;
    graph [rankdir = "TB"];
    label = "capabilities";
  '''
  for cap_name, cap in node.capabilities.items():
    # if cap.node is not self:
    #   res += f'''
    #   subgraph {subgraph_name}_capability_{cap_name} {{
    #     label="{cap_name} ({cap.type})";
    #     "cap_{subgraph_name}_capability_{cap_name}" [shape=point,style=invis];
    #   }}
    #   "cap_{subgraph_name}_capability_{cap_name}" -> "cap_cluster_{cap.node.topology.name}_{cap.node.name}_capability_{cap.name}" [
    #     label="substitute",
    #     penwidth=3,
    #     weight=1,
    #     color=red,
    #     ltail={subgraph_name}_capability_{cap_name},
    #     lhead=cluster_{cap.node.topology.name}_{cap.node.name}_capability_{cap.name}
    #   ];
    #   '''
    # else:
    res += capability_graphviz(subgraph_name, cap)
  res += '''
  }
  '''

  res += '''
  }
  '''

  # if self.substitution is not None:
  #   res += self.substitution.graphviz()

  return res


def capability_graphviz(cluster_prefix, capability):
  subgraph_name = f'{cluster_prefix}_capability_{capability.name}'

  res = f'''
  subgraph {subgraph_name} {{
    color = black;
    graph [rankdir = "TB"];
    label = "{capability.name} ({capability.type})";
    "cap_{subgraph_name}" [shape=point,style=invis];
  '''

  if len(capability.properties) > 0:
    res += f'''
    subgraph {subgraph_name}_properties {{
      color = black;
      graph [rankdir = "LR"];
      rank = same;
      label = "properties";
      rank = same;
    '''
    for p_name, p_body in capability.properties.items():
      res += f'''
      "{subgraph_name}_prop_{p_name}" [label="{p_name} = {p_body.get()}"];
      '''
    res += '''
    }
    '''

  res += '''
  }
  '''

  return res