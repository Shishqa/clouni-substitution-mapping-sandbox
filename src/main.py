import argparse

from compositor import compose
from parser import parse


def main():
  args = parse_arguments()
  try:
    clout = parse(args.template)
    compose(clout)
  except RuntimeError as err:
    print(err.args[0])


def parse_arguments():
  parser = argparse.ArgumentParser(description='')
  parser.add_argument('template', help='path to the TOSCA template')
  parser.add_argument(
      '-r', '--root_path', help='path to the TOSCA template', type=str, default="./", required=False)
  return parser.parse_args()


if __name__ == "__main__":
  main()
