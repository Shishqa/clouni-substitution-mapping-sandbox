from cotea.runner import runner
from cotea.arguments_maker import argument_maker

def run_artifact(address, artifact, inputs):
  print(f'running {artifact}')

  am = argument_maker()
  am.add_arg("-i", f"{address},")
  am.add_arg("-c", "local")
  am.add_arg("--extra-vars", f"{inputs}")

  r = runner(artifact, am)

  while r.has_next_play():
      current_play = r.get_cur_play_name()
      print("PLAY:", current_play)

      while r.has_next_task():
          next_task = r.get_next_task_name()
          print("\tTASK:", next_task)
              
          r.run_next_task()

  r.finish_ansible()

  #   ANSIBLE_CMD = f'ansible-playbook -c local -i {address}, --extra-vars {inputs} {artifact}'
  # pipe = sp.Popen(
  #     ANSIBLE_CMD,
  #     shell=True,
  #     stdout=sp.PIPE,
  #     stderr=sp.PIPE
  #   )
  # res = pipe.communicate()

  # if pipe.returncode != 0:
  #   raise RuntimeError(res[1].decode())