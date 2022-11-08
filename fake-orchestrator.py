import os

substitutions = {
  'tosca.nodes.Compute': [
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

def fill_inputs(template):
  print('please, fill inputs')
  inputs = {}
  for inpt in template['inputs']:
    inputs[inpt] = input(f'{inpt}: ')
  return ' '.join([f'-i {i[0]}={i[1]}'for i in inputs.items()])

def main():
  print('parsing tosca-server-example.yaml...')
  os.system('puccini-tosca parse tosca-server-example.yaml')
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

if __name__ == "__main__":
  main()