import argparse

import compositor
import dashboard
import instance_storage
import tosca_repository
import parser
import orchestrator


def create(args):
  normalized_template = parser.parse(args.template)
  topology_status = compositor.instantiate(normalized_template, args.name)
  if not topology_status['fulfilled']:
    fulfill(topology_status)


def fulfill(topology_status):
  print(f'FULFILLING {topology_status["name"]}')
  actions = []
  for issue in topology_status['issues']:
    if issue['type'] == 'substitute':
      print(f'please choose desired substitution for node {issue["target"]}')
      options = issue['options']

      substitution_template = None
      while substitution_template is None:
        if len(options) == 1:
          substitution_template = options[0]["file"]
          break

        for i, item in enumerate(options):
          print(f' {i} - {item["file"]}')

        choose = int(input('your choice: '))
        if choose in range(len(options)):
          print(f'chosen {options[choose]["file"]}')
          substitution_template = options[choose]["file"]
        else:
          print('please, choose correct option')

      actions.append({
        'type': 'substitute',
        'target': issue["target"],
        'template': substitution_template,
      })

  if len(actions) > 0:
    topology_status = compositor.fulfill(topology_status['name'], actions)

  for sub_name, sub_status in topology_status['subtopologies'].items():
    if not sub_status['fulfilled']:
      fulfill(sub_status)


def query(args):
  status = compositor.query(args.topology_name)
  print(status)


def display(args):
  dashboard.display_topology(args.topology_name)


def traverse(args):
  orchestrator.traverse_topology(args.topology_name)


def main():
  args = parse_arguments()
  try:
    tosca_repository.init_database()
    instance_storage.init_database()

    if args.subcommand == 'create':
      create(args)
    elif args.subcommand == 'query':
      query(args)
    elif args.subcommand == 'display':
      display(args)
    elif args.subcommand == 'traverse':
      traverse(args)

    instance_storage.dump_database()

  except RuntimeError as err:
    print(err.args[0])


def parse_arguments():
  parser = argparse.ArgumentParser(description='')
  parser.add_argument(
      '-r', '--root_path', help='path to the TOSCA template', type=str, default="./", required=False)

  subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')

  parser_create = subparsers.add_parser('create', help='create help')
  parser_create.add_argument('template', help='path to the TOSCA template')
  parser_create.add_argument('-n', '--name', help='name of the cluster', type=str)

  parser_display = subparsers.add_parser('query', help='query help')
  parser_display.add_argument('topology_name', help='name of the topology to query')

  parser_display = subparsers.add_parser('display', help='display help')
  parser_display.add_argument('topology_name', help='name of the topology to display')

  parser_display = subparsers.add_parser('traverse', help='traverse help')
  parser_display.add_argument('topology_name', help='name of the topology to traverse')

  return parser.parse_args()


if __name__ == "__main__":
  main()
