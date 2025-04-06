import json
import subprocess
import sys
from getpass import getpass

if len(sys.argv) < 2:
    print("Синтаксис: " + sys.argv[0] + " [список адресов серверов, разделённых запятой]")
    sys.exit(1)

password = getpass('Пароль для будущего пользователя student: ')
password2 = getpass('Подтвердите пароль: ')
if password != password2:
    print("Пароли не совпадают, попробуйте ещё раз")
    sys.exit(2)

with open("hosts", "w") as f:
    f.write("[servers]\n")
    for server in sys.argv[1].split(','):
        f.write(server + "\n")

print("Проверяем нагрузку на сервера...")

ret = bytes()
try:
    ret = subprocess.check_output(
        env={'ANSIBLE_LOAD_CALLBACK_PLUGINS': '1', 'ANSIBLE_CALLBACKS_ENABLED': 'json', 'ANSIBLE_STDOUT_CALLBACK': 'json'},
        args=["ansible", "-m", "setup", "-i", "hosts", "servers", "-a", "filter=ansible_loadavg"])               
except subprocess.CalledProcessError as e:                                                                                                   
    print("Не удалось проверить нагруженность. Все ли сервера доступны?")
    print(e.output.decode('utf-8'))
    sys.exit(3)

j = json.loads(ret.decode('utf-8'))

servers = []
for hostname, host in j['plays'][0]['tasks'][0]['hosts'].items():
    load_1m = host['ansible_facts']['ansible_loadavg']['1m']
    servers.append((hostname, load_1m))
servers.sort(key=lambda x: x[1])

if len(servers) < 2:
    print("Укажите хотя бы 2 сервера")
    sys.exit(4)

print("Менее нагруженный сервер:", servers[0][0], "с нагрузкой:", servers[0][1])
print("Второй сервер:", servers[1][0])

print("Развёртываем postgresql...")
ret2 = subprocess.call(
    args=["ansible-playbook", "install.yml", "-i", "hosts", "--limit=" + servers[0][0], "-e", "second_srv_addr=" + servers[1][0]],
    env={'POSTGRES_STUDENT_PASSWORD': password})
if ret2 == 0:
    print("Установка и настройка успешно завершена")
else:
    print("Ошибка во время установки и настройки. Все ли сервера доступны?")
    sys.exit(5)

print("Проверка доступности postgresql...")
ret3 = subprocess.call(args=["ssh", "root@" + servers[1][0], "psql -h " + servers[0][0] + " student student -c 'SELECT 1'"])
if ret3 == 0:
    print("Соединение с БД успешно проверено")
else:
    print("Ошибка при соединении с БД")
    sys.exit(6)
