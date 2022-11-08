# Clouni substitution mapping sandbox

## Рекомендуется прочесть >> [Proposal](./docs/proposal.md) <<

## Документация к примеру

### Prerequisites

- Для того, чтобы парсить TOSCA шаблоны я использовал парсер [puccini](https://github.com/tliron/puccini)
    Его необходимо установить:
    1. Скачать с github release: https://github.com/tliron/puccini/releases/download/v0.20.1/puccini_0.20.1_linux_amd64.tar.gz
    2. Распаковать архив: `tar -xf puccini_0.20.1_linux_amd64.tar.gz`
    3. Поместить бинарники из архива в `~/.local/bin` и добавить этот путь в `$PATH`

- Для того, чтобы запускать плейбуки в `profiles/openstack/artifacts`, нужен ansible и openstack.cloud collection:
  ```
  pip install "ansible>=2.9" "openstacksdk==0.61.0"
  ansible-galaxy collection install openstack.cloud
  ```

### Содержимое репозитория

1. `profiles/openstack` - TOSCA профиль для openstack, который я взял у того же tliron и немного расширил: https://github.com/oasis-open/tosca-community-contributions/tree/master/profiles/cloud.puccini/openstack/1.0
2. `profiles/openstack/artifacts` - ansible скрипты, необходимые для развёртывания определённых узлов
3. `templates` - папка с TOSCA шаблонами, которые могут подменить `tosca.nodes.Compute`
4. `tosca-server-example.yaml` - шаблон, аналогичный тому, что приводится в базовых примерах clouni
5. `fake-orchestrator.py` - очень примитивный python скрипт, показывающий, как может работать оркестратор

### Запуск

- Запустить `python fake-orchestrator.py`
  1. Сначала он спарсит `tosca-server-example.yaml` с помощью puccini (никакой магии пока, просто `os.system(...)`)
  2. Потом "посмотрит" на все вершины, помеченные `substutute` и предложит выбрать подходящие реализации (примитивный пример хранения таких шаблонов для TOSCA-типов) можно найти в самом скрипте: `substitutions = {...}`
  3. Для выбранной вершины нужно будет удовлетворить неудовлетворённые inputs (не уверен, что это нормативно, но вроде стандарту не противоречит)
  4. Далее "оркестратор" запускает puccini на подставленном шаблоне
- Отдельно можно натравить puccini на любой из TOSCA-файлов:
  ```
  puccini-tosca parse openstack-compute-public.yaml -i instance_name=test-instance -i key_name=my_key
  ```
- Можно запускать плейбуки в `profiles/openstack/artifacts` (но лучше сначала посмотреть, что они делают. лучше запускать немутирующие)
  ```
  ansible-playbook profiles/openstack/artifacts/os_flavor_find.yaml
  ```