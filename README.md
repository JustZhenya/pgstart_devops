# Развёртывание PostgreSQL на серверах Debian и Almalinux

## Подготовка
1. На серверах должен быть установлен sshd и python3 для работы ansible
2. Ваш публичный SSH ключ должен быть импортирован пользователю root на серверах
3. (необязательно) Должна быть установлена утилита psql для проверки подключения

Я проверял на двух виртуальных машинах с Debian 12 без графики и Almalinux 9 в серверной конфигурации.

## Как этим пользоваться
```shell
git clone https://github.com/JustZhenya/pgstart_devops.git
cd pgstart_devops
python3 install.py 10.0.0.1,10.0.0.2
```
Перед установкой скрипт спросит пароль для пользователя student, который будет создан в БД.

В конце установки скрипт спросит этот пароль снова для проверки подключения.

## Как оно работает
Вначале проверяем нагруженность серверов. Для получения нагрузки используется ansible с получением факта ansible_loadavg.1m, для сортировки серверов по нагруженности используется python (вообще теоретически это можно было бы сделать и в плейбуке ansible, но после нескольких часов безуспешных попыток я сдался. См. ниже.)

Выбираем также второй сервер для того, чтобы проверять соединение к первому.

Затем запускаем ansible-playbook на первом сервере, в него также передаём пароль от пользователя постгрес и адрес второго сервера.

В плейбуке происходит следующее:
- Устанавливаем postgresql-server и python-psycopg2, используя пакетный менеджер ОС
- (только на Альмалинукс) Инициализируем БД, запускаем сервис
- Разрешаем подключения из-вне через файл postgresql.conf
- (только на Альмалинукс) Разрешаем postgresql на файрволле
- Создаём базу, пользователя student, даём права пользователю на базу
- Добавляем в pg_hba.conf запись о том, что студенту можно подключаться со второго сервера
- Перезапускаем сервис, добавляем в автозапуск

В конце проходит подключение по ssh ко второму серверу и через него проверяется подключение к postgresql через psql.

## Что ещё можно улучшить
- Заменить все константы в плейбуке на переменные, передавать их через флаг `-e`
- Возможно отрефакторить плейбук, там много похожих действий
- Избавиться от запроса пароля при проверке доступности (однако по SSH передавать переменные среды сложно, а без них пароль может утечь)

## Какие возникли проблемы
Проблема возникла одна и довольно смешная: не получается отсортировать список серверов по нагруженности в ansible. Основной метод, через который я пытался это
```yaml
vars:
  lowest_cpu_host: '{{ hostvars.values() | sort(attribute=ansible_loadavg.1m) }}'
```
Это не полный код, там ещё дальше надо записать адрес хоста и всё такое, но судь должна быть понятна: вне зависимости как бы я не обращался к hostvars, оно всегда возвращает ошибку "неизвестный атрибут". Причём, если я внутри task попытаюсь обратиться сразу к hostvars `{{ hostvars.values() }}` все значения возвращаются, но попытка к ним обратиться сразу проваливается.

Затем я пробовал получать значение загруженности внутри task, а потом из всех значений выбирать наименьшее.

Как-то примерно так:
```yaml
  tasks:
  - name: Set fact for all hosts
    throttle: 1
    set_fact:
      host_loads: "{{ host_loads | default({}) | combine({inventory_hostname: ansible_loadavg['1m'] | float}) }}"

  - name: Wait for all hosts to report their loads
    meta: flush_handlers

  - name: Find the host with the lowest CPU load
    set_fact:
      target_host: "{{ item.key }}"
    loop: "{{ host_loads | dict2items }}"
    when: item.value == (host_loads | dict2items | map(attribute='value') | min)

  - name: Execute task on the host with the lowest CPU load
    when: ansible_loadavg['1m'] == host_loads.values() | min()
    debug:
      msg: '{{ ansible_loadavg["1m"] }}, {{ host_loads }}'
```
Но это тоже успеха не возымело, каждый хост видел только одного себя.

В итоге я сдался и просто взял python, 15 минут кодинга и готово.