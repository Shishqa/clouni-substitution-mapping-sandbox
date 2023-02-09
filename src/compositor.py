
from instance_storage import get_nodes_of_type

def compose(clout):
  for name, node in clout['nodeTemplates'].items():
    print(node.keys())
    # if 'select' in node['directives']:
    #   selected_node = select()
    # print(node['directives'])

def select(node_type):
  options = get_nodes_of_type(node_type)

def substitute(node_type):
  pass

