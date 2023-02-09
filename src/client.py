import argparse

import compositor
import dashboard
import instance_storage
import tosca_repository
import parser


def create(args):
  normalized_template = parser.parse(args.template)
  compositor.compose(normalized_template, args.name)


def display(args):
  if args.topology_name == 'all':
    for topology_name in instance_storage.list_topologies():
      dashboard.display_topology(topology_name)

  dashboard.display_topology(args.topology_name)


def main():
  args = parse_arguments()
  try:
    tosca_repository.init_substitution_database()
    instance_storage.init_database()

    if args.subcommand == 'create':
      create(args)
    elif args.subcommand == 'display':
      display(args)

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

  parser_display = subparsers.add_parser('display', help='create help')
  parser_display.add_argument('topology_name', help='name of the topology to display')

  return parser.parse_args()


if __name__ == "__main__":
  main()
