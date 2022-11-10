import os
import argparse
import subprocess as sp
import yaml

substitutions = {
  'tosca::Compute': [
    { 
      'file': 'templates/openstack-compute-public.yaml',
      # possibly, we can search by tags
      # tags are provided via 3.6.2 Metadata?
      'tags': [ 'openstack', 'floating-ip' ],
      # these are parsed
      'inputs': [ 'instance_name', 'key_name', 'floating_ip_pool' ]
    },
    { 
      'file': 'templates/openstack-compute.yaml',
      'tags': [ 'openstack' ],
      'inputs': [ 'instance_name', 'key_name' ]
    },
  ]
}

instance_models = []

def foo():
  print('')
  print('node tosca_server_example is marked substitutable')
  print('please choose desired substitution')
  for i, item in enumerate(substitutions['tosca.nodes.Compute']):
    print(f' {i} - {item["file"]}')
  print(f' {len(substitutions["tosca.nodes.Compute"])} - create new')

  while True: # blame on me
    choose = int(input('your choise: '))
    if choose in range(len(substitutions["tosca.nodes.Compute"])):
      print(f'chosen {substitutions["tosca.nodes.Compute"][choose]["file"]}')
      
      inputs = fill_inputs(substitutions["tosca.nodes.Compute"][choose])
      # use string below to see behavior without inputs
      # inputs = ''

      os.system(f'puccini-tosca parse {inputs} {substitutions["tosca.nodes.Compute"][choose]["file"]}')
      return
    elif choose == len(substitutions["tosca.nodes.Compute"]):
      print('creating new template ... (simply create empty template)')
      return
    else:
      print('please, choose correct option')


def fill_inputs(template):
  print('please, fill inputs')
  inputs = {}
  for inpt in template['inputs']:
    inputs[inpt] = input(f'{inpt}: ')
  return ' '.join([f'-i {i[0]}={i[1]}'for i in inputs.items()])

def parse_template(path):
  print(f'parsing {path}...')
  pipe = sp.Popen(f'puccini-tosca parse {path}', shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
  res = pipe.communicate()
  if pipe.returncode != 0:
    raise RuntimeError(res[1])
  return yaml.safe_load(res[0])

def find_substitutions(template):
  for name, node in template["nodeTemplates"].items():
    if "substitute" in node["directives"]:
      print(f'node {name} is marked substitutable')
      print('please choose desired substitution')
      option_list = []
      
      for t in node["types"].keys():
        if t not in substitutions.keys():
          continue
        option_list += substitutions[t]

      for i, item in enumerate(option_list):
        print(f' {i} - {item["file"]}')
      
      while True: # blame on me
        choose = int(input('your choise: '))
        if choose in range(len(option_list)):
          print(f'chosen {option_list[choose]["file"]}')
          
          tmp = parse_template(option_list[choose]["file"])
          find_substitutions(tmp)

        else:
          print('please, choose correct option')


def parse_arguments():
  parser = argparse.ArgumentParser(description='')
  parser.add_argument('template', help='path to the TOSCA template')
  return parser.parse_args()

def main():
  args = parse_arguments()
  try:
    template = parse_template(args.template)
    find_substitutions(template)
  except RuntimeError as err:
    print(err.args[0])

if __name__ == "__main__":
  main()