## Clouni substitution mapping proposal

### Сейчас clouni работает так:

1. Получает на вход TOSCA-шаблон с абстрактной `tosca.nodes.Compute` нодой
2. Зная, какой провайдер нужен (например `--provider openstack`), транслирует шаблон в ненормативные типы
  1. Пользуясь своей [конфигурацией маппинга](https://github.com/sadimer/clouni_provider_tool/blob/main/provider_tool/providers/openstack/tosca_elements_map_to_openstack.yaml), переводит одни параметры шаблона в другие
  2. Получает __ненормативный шаблон__, потому что внутри шаблона содержатся куски jinja вида:
  ```yaml
  tosca_server_example_security_group_rule:
    properties:
      direction: '{{ initiator[item | int] | default(omit) }}'
      port_range_max: '{{ port[item | int] | default(omit) }}'
      port_range_min: '{{ port[item | int] | default(omit) }}'
      protocol: '{{ protocol[item | int] | default(omit) }}'
      remote_ip_prefix: 0.0.0.0
    requirements:
    - security_group:
        node: tosca_server_example_security_group
    type: openstack.nodes.SecurityGroupRule
  ```
3. По полученному шаблону генерирует ansible скрипт, и запускает его

### Как clouni может работать:

1. Получает на вход TOSCA-шаблон с абстрактной `tosca.nodes.Compute` нодой, __которая помечена абстрактной с помощью `directives: [ substitute ]`__
2. На основе тегов, выбранных пользователем (см. `fake-orchestrator.py:9`), в том числе провайдера, подбирает подходящие шаблоны из тех, которые он знает (папка `templates`)
    1. С помощью описанной в стандарте TOSCA схемы substitution mapping сопоставляет параметры
    2. __Вообще не генерирует новый шаблон__. Это вопрос дискуссионный, т.к. понятен запрос на вариативность конфигурации. Но вот несколько примеров:
        - Пользователь хочет создать инстанс в опенстеке без публичного IP: __выбирает шаблон__, где floating ip не присваивается
        - Пользователь хочет создать инстанс в опенстеке с публичным IP: точно так же __выбирает__ шаблон, но уже другой, где есть floating ip
        - Пользователь хочет более глубокой конфигурации: он __создает__ новый шаблон для substitution mapping, пользуясь типами из профиля опенстека, а затем использует свой шаблон
3. Разворачивает через interfaces валидный TOSCA шаблон, который "был подставлен" на место абстрактного (на самом деле просто развёрнут как отдельный шаблон + оркестратор запомнил связь в instance model)

В чём clouni лучше:
- С точки зрения трансляции одних штук в другие clouni гораздо универсальнее, т.к. может, например, из одного property (например какой-нибудь сложный map) сделать 2 TOSCA-ноды (__или N TOSCA-нод__)
- __генерирует__ ansible скрипты

В чём clouni уступает:
- полученные шаблоны в промежуточном представлении ненормативны и могут быть развёрнуты только с помощью clouni
- полученный ansible невозможно дебажить и анализировать, потому что он сгенерирован

Предложенный подход может быть не менее универсальным, чем текущий в clouni, потому что:
- базовые конфигурации удовлетворяются парой substitution-шаблонов
- более сложные конфигурации удовлетворяются абстрактными `tosca.nodes.network.Port` и `tosca.nodes.network.Network`, которые __тоже можно перевести в ненормативные Openstack типы через substitution mapping__ (да, подстановок больше, но их можно решить через эффективный поиск подходящих шаблонов)
- в текущем [описании](https://github.com/oasis-open/tosca-community-contributions/blob/7751e22541845ec508afa9ba5d02d0f6f4342b6b/profiles/org.oasis-open/simple/1.3/node.yaml#L72-L117) нормативного типа `tosca.nodes.Compute` вообще нет properties. Можно только выставить параметры __одного__ Endpoint'а, который семантически вынесен как единственная точка доступа для администратора. А attributes, __по моему представлению (тут я могу ошибаться)__, лучше не выставлять руками: семантически они обозначают параметры, которые становятся известны в рантайме 
>   #### 3.6.10.1 Attribute and Property reflection
>   
>   The actual state of the entity, at any point in its lifecycle once instantiated, is reflected by [Attribute definitions](https://docs.oasis-open.org/tosca/TOSCA-Simple-Profile-YAML/v1.3/os/TOSCA-Simple-Profile-YAML-v1.3-os.html#DEFN_ELEMENT_ATTRIBUTE_DEFN).  TOSCA orchestrators automatically create an attribute for every declared property (with the same symbolic name) to allow introspection of both the desired state (property) and __actual state (attribute)__.
>   #### 3.6.12.4 Additional Requirements
>   
>   Values for the default keyname **MUST** be derived or calculated from other attribute or operation output values (that reflect the actual state of the instance of the corresponding resource) and __not hard-coded or derived from a property settings or inputs (i.e., desired state)__.