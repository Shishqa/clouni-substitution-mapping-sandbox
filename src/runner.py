


import errno
import os
import shutil
import subprocess  # nosec
import tempfile
import json
import sys
import tempfile

import yaml

# from opera.threading import utils as thread_utils
# from . import utils
from ansible_callbacks import json_ansible_callback


def _get_inventory(host):
    inventory = dict(
        ansible_host=host,
        ansible_ssh_common_args="-o StrictHostKeyChecking=no",
    )

    if host == "localhost":
        inventory["ansible_connection"] = "local"
        inventory["ansible_python_interpreter"] = sys.executable
    else:
        inventory["ansible_user"] = os.environ.get("OPERA_SSH_USER", "ubuntu")
        opera_ssh_identity_file = os.environ.get("OPERA_SSH_IDENTITY_FILE")
        if opera_ssh_identity_file is not None:
            inventory["ansible_ssh_private_key_file"] = opera_ssh_identity_file

    print('host:')
    print(yaml.safe_dump(dict(all=dict(hosts=dict(opera=inventory)))))
    print('')

    return yaml.safe_dump(dict(all=dict(hosts=dict(opera=inventory))))


def run_artifact(host, primary, variables, dependencies):
    # print(dependencies)
    # print(host)

    # pylint: disable=too-many-locals
    with tempfile.TemporaryDirectory() as dir_path:
        playbook = os.path.join(dir_path, os.path.basename(primary))
        ucopy(primary, playbook)

        for d in dependencies:
            ucopy(d['source'], os.path.join(dir_path, d['dest']))
        # for a in artifacts:
        #     utils.copy(os.path.join(workdir, a), os.path.join(dir_path, os.path.basename(a)))

        inventory = uwrite(dir_path, _get_inventory(host), suffix=".yaml")
        vars_file = uwrite(dir_path, yaml.safe_dump(variables), suffix=".yaml")

        with open(f"{dir_path}/ansible.cfg", "w", encoding="utf-8") as fd:
            fd.write("[defaults]\n")
            fd.write("retry_files_enabled = False\n")

            # opera_ssh_host_key_checking = os.environ.get("OPERA_SSH_HOST_KEY_CHECKING")
            # if opera_ssh_host_key_checking is not None:
            #     check = str(opera_ssh_host_key_checking).lower().strip()
            #     if check[:1] == "f" or check[:1] == "false":
            #         fd.write("host_key_checking = False\n")

        print(json.dumps({"inputs": {key: variables[key] for key in variables}}, indent=2, sort_keys=True))

        print('\nrunner_root:')
        for root, dirs, files in os.walk(dir_path):
            level = root.replace(dir_path, '').count(os.sep)
            indent = ' ' * 4 * (level)
            print('{}{}/'.format(indent, os.path.basename(root)))
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                print('{}{}'.format(subindent, f))

        print('')
        cmd = [
            "ansible-playbook",
            "-i", inventory,
            "-e", "@" + vars_file,
            playbook
        ]

        env = dict(
            ANSIBLE_SHOW_CUSTOM_STATS="1",
            ANSIBLE_CALLBACK_PLUGINS=f"~/.ansible/plugins/callback:/usr/share/ansible/plugins/callback:"
                                     f"{os.path.dirname(json_ansible_callback.__file__)}",
            ANSIBLE_STDOUT_CALLBACK="json_ansible_callback"
        )
        code, out, err = urun_in_directory(dir_path, cmd, env)
        if code != 0:
            #print('out')
            with open(out, encoding="utf-8") as fd:
                print(fd.read())
                # thread_utils.SafePrinter.print_lines(fd)
            #print('err')
            with open(err, encoding="utf-8") as fd:
                print(fd.read())
                # thread_utils.SafePrinter.print_lines(fd)
            # thread_utils.print_thread("============")

        if code != 0:
            return False, {}

        outputs = {}
        with open(out, encoding="utf-8") as fd:
            outputs = json.load(fd)["global_custom_stats"]

        return code == 0, outputs


def ucopy(source, target):
    try:
        shutil.copytree(source, target)
    except OSError as e:
        if e.errno == errno.ENOTDIR:
            shutil.copy(source, target)
        else:
            raise


def uwrite(dest_dir, content, suffix=None):
    with tempfile.NamedTemporaryFile(dir=dest_dir, delete=False, suffix=suffix) as dest:
        dest.write(content.encode("utf-8"))
        return dest.name


def urun_in_directory(dest_dir, cmd, env):
    with tempfile.NamedTemporaryFile(dir=dest_dir, delete=False, suffix=".stdout") as fstdout, \
            tempfile.NamedTemporaryFile(dir=dest_dir, delete=False, suffix=".stderr") as fstderr:
        result = subprocess.run(cmd, cwd=dest_dir, stdout=fstdout, stderr=fstderr,  # nosec
                                env=dict(os.environ, **env), check=False)
        return result.returncode, fstdout.name, fstderr.name


# from cotea.runner import runner
# from cotea.arguments_maker import argument_maker

# def run_artifact(address, artifact, inputs):
#   print(f'running {artifact}')

#   am = argument_maker()
#   am.add_arg("-i", f"{address},")
#   am.add_arg("-c", "local")
#   am.add_arg("--extra-vars", f"{inputs}")

#   r = runner(artifact, am)

#   while r.has_next_play():
#       current_play = r.get_cur_play_name()
#       print("PLAY:", current_play)

#       while r.has_next_task():
#           next_task = r.get_next_task_name()
#           print("\tTASK:", next_task)
              
#           res = r.run_next_task()
#           print(res)

  
#   r.finish_ansible()

  
#   print('OUTPUT')
#   print(facts)

#   #   ANSIBLE_CMD = f'ansible-playbook -c local -i {address}, --extra-vars {inputs} {artifact}'
#   # pipe = sp.Popen(
#   #     ANSIBLE_CMD,
#   #     shell=True,
#   #     stdout=sp.PIPE,
#   #     stderr=sp.PIPE
#   #   )
#   # res = pipe.communicate()

#   # if pipe.returncode != 0:
#   #   raise RuntimeError(res[1].decode())