class TopologyTemplateInstance:
  def __init__(self, name, definition, path):
    self.name = name
    self.definition = copy.deepcopy(definition)
    self.path = path
    self.instance_models = {}

    self.inputs = {}
    for input_name in self.definition['inputs'].keys():
      self.inputs[input_name] = PropertyInstance(
          self, self.definition['inputs'][input_name])

    self.instantiate_nodes()

  def instantiate_nodes(self):
    global selections

    self.nodes = {}
    for name in self.definition["nodeTemplates"].keys():
      if "select" in self.definition["nodeTemplates"][name]["directives"]:
        selections.append({'instance': self, 'node': name})
        print("select", name)
        continue
      self.nodes[name] = NodeInstance(name, self)

  def get_input(self, input_name):
    return self.inputs[input_name].get()

  def graphviz(self):
    # global visited
    cluster_name = f'cluster_{self.name}'

    # if cluster_name in visited:
    #   print(visited)
    #   return ''

    # visited.add('TOPOLOGY'+cluster_name)

    res = f'''
    subgraph cluster_{self.name} {{
      penwidth=5;
      graph [rankdir = "TB"];
      color = green;
      label = "Instance {self.name} ({self.path})";
    '''
    if len(self.inputs) > 0:
      res += f'''
      subgraph cluster_{self.name}_inputs {{
        penwidth=1;
        style=filled;
        fillcolor = yellow;
        graph [rankdir = "LR"];
        rank = same;
        label = "inputs";
      '''
      for p_name, p_body in self.inputs.items():
        res += f'''
        "cluster_{self.name}_inputs_prop_{p_name}" [label="{p_name} = {p_body.get()}"];
        '''
      res += '''
      }
      '''

    for name, node in self.nodes.items():
      if node.topology.name != self.name:
        continue
      res += f'''
        {node.graphviz()}
        '''

    for name, node in self.nodes.items():
      node_subgraph_name = f'cluster_{node.topology.name}_{node.name}'
      for req in node.definition['requirements']:
        if req['nodeTemplateName'] == '':
          continue
        res += f'''
        "node_{node_subgraph_name}" -> "node_cluster_{node.topology.nodes[req['nodeTemplateName']].topology.name}_{req['nodeTemplateName']}" [
          penwidth=3,
          weight=1,
          ltail={node_subgraph_name}, 
          lhead=cluster_{node.topology.nodes[req['nodeTemplateName']].topology.name}_{req['nodeTemplateName']}
        ];
        '''
    res += '''
    }
    '''
    return res

  def dump_graphviz(self, path):
    res = f'''
    digraph G {{
      margin=10;
      compound=true;
      graph [ranksep=3];
      graph [rankdir = "TB"];
      node [shape = record];
      {self.graphviz()}
    }}
    '''

    f = open(f'{path}.dot', "w")
    f.write(res)
    f.close()

    f = open(f'{path}.svg', "w")
    pipe = sp.Popen(
        f'dot -Tsvg {path}.dot', shell=True, stdout=f, stderr=sp.PIPE)
    res = pipe.communicate()
    f.close()

    if pipe.returncode != 0:
      raise RuntimeError(res[1])

  def get_deploy_order(self):
    to_visit = set(self.nodes.keys())
    edges = {}
    for name, node in self.nodes.items():
      for req in node.definition['requirements']:
        if req['nodeTemplateName'] in to_visit:
          to_visit.remove(req['nodeTemplateName'])
        if req['nodeTemplateName'] not in edges.keys():
          edges[req['nodeTemplateName']] = set()
        edges[req['nodeTemplateName']].add(name)

    deploy_order = []
    while len(to_visit) > 0:
      n = to_visit.pop()
      deploy_order.append(n)
      for req in self.nodes[n].definition['requirements']:
        edges[req["nodeTemplateName"]].remove(n)
        if len(edges[req["nodeTemplateName"]]) == 0:
          to_visit.add(req["nodeTemplateName"])
          edges.pop(req["nodeTemplateName"])

    if len(edges.keys()) > 0:
      raise RuntimeError('deploy graph has a cycle!')

    deploy_order.reverse()
    return deploy_order

  def deploy(self):
    print(f'\ndeploying instance_{idx}')
    order = self.get_deploy_order()
    for n in order:
      self.nodes[n].deploy()