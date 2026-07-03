# Задание 9. Приложение, systemd, Docker, мониторинг, NAT, Kubernetes

Всё делал на своём Proxmox (`ssh pve`, 192.168.0.15). Дальше по пунктам, как в задании (a-h).

## a. Веб-приложение (FastAPI)

Код лежит в [app/main.py](app/main.py), зависимости в [app/requirements.txt](app/requirements.txt).

Логика простая:
- `POST /` смотрит на заголовок `Test`. Если там `Hello` - отдаёт `200` и `Hello, World!`. Если нет - `403`.
- `GET /health` пингует `77.88.8.8` (`ping -c 1 -W 2`). Пинг прошёл - `200 OK`, не прошёл - `503`.

Ещё подключил `prometheus-fastapi-instrumentator`, чтобы был эндпоинт `/metrics` - он пригодится дальше для мониторинга.

Проверял локально вот так:
```bash
pip install -r app/requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir app
curl -i -X POST http://127.0.0.1:8000/                    # должно быть 403
curl -i -X POST -H "Test: Hello" http://127.0.0.1:8000/   # должно быть 200 Hello, World!
curl -i http://127.0.0.1:8000/health                      # должно быть 200 OK
```

## b. VM + systemd-сервис от отдельного пользователя

Взял VM `ubuntu-clean` (vmid 105), Ubuntu Server 22.04, адрес `10.10.10.20` (позже перенёс её в отдельную сеть, см. пункт e).

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin webapp
sudo mkdir -p /opt/webapp
sudo cp -r app/* /opt/webapp/
sudo python3 -m venv /opt/webapp/venv
sudo /opt/webapp/venv/bin/pip install -r /opt/webapp/requirements.txt
sudo chown -R webapp:webapp /opt/webapp
```

Unit-файл лежит в [systemd/webapp.service](systemd/webapp.service), кладётся в `/etc/systemd/system/webapp.service`.

Сервис слушает порт 8000, не 8080 - на этой VM порт 8080 уже занят Jenkins с восьмого задания, пришлось подвинуться.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now webapp
sudo systemctl status webapp
```

Проверил: без заголовка получаю 403, с заголовком `Hello, World!`, `/health` отдаёт 200. Сервис при этом крутится от системного пользователя `webapp`, у которого нет ни домашней папки, ни шелла.

## c. Dockerfile и образ

[app/Dockerfile](app/Dockerfile) - взял `python:3.12-slim` и добавил туда `iputils-ping`, без него `/health` работать не будет.

```bash
cd app
docker build -t webapp:1.0 .
docker run -d --name webapp-test -p 8001:8000 webapp:1.0
curl -i -X POST -H "Test: Hello" http://127.0.0.1:8001/
```

Собирал и проверял прямо на VM 105 - Docker на своей машине не держу, поставил его через `get.docker.com`.

## d. docker-compose + Prometheus + Alertmanager

Всё в папке [monitoring/](monitoring):
- [monitoring/docker-compose.yml](monitoring/docker-compose.yml) - тут `webapp`, `prometheus` и `alertmanager` в одной сети. Приложение отдал наружу через порт 8001, потому что 8000 уже занят systemd-сервисом из пункта b, а 8080 - Jenkins.
- [monitoring/prometheus/prometheus.yml](monitoring/prometheus/prometheus.yml) - job `webapp`, который снимает метрики с `webapp:8000/metrics`, плюс подключение к Alertmanager.
- [monitoring/prometheus/alert.rules.yml](monitoring/prometheus/alert.rules.yml) - два алерта: `WebappDown` (если приложение не отвечает 30 секунд) и `WebappHighErrorRate` (если больше 10% ответов 5xx за последние 5 минут).
- [monitoring/alertmanager/alertmanager.yml](monitoring/alertmanager/alertmanager.yml) - receiver через webhook на `http://webapp:8000/alerts`. Это заглушка для демонстрации, в реальном проекте сюда встал бы Slack или почта.

```bash
cd monitoring
docker compose up -d --build
curl -s http://localhost:9090/api/v1/targets   # webapp и prometheus должны быть up
curl -s http://localhost:9090/api/v1/rules     # группа "webapp" должна быть на месте
curl -s http://localhost:9093/api/v2/status    # Alertmanager должен ответить
```

Проверил на VM 105 - все три контейнера подняты, Prometheus видит webapp как up, правила подгрузились.

### Отдельная VM с NAT (два сетевых интерфейса)

Тут решил не трогать сеть, в которой уже крутится кластер (`vmbr0`, 10.10.10.0/24) - незачем рисковать рабочей инфраструктурой ради демонстрационной задачи. Вместо этого поднял отдельную изолированную сеть:

- Добавил на Proxmox новый bridge `vmbr1` - без IP на хосте, просто L2-коммутатор для VM. Применил через `ifreload -a`, чтобы не оборвать уже работающие интерфейсы.
- Склонировал из своего шаблона `ubuntu-k8s-template` новую VM `nat-gateway` (vmid 106) с двумя сетевыми картами:
  - `net0` смотрит в `vmbr0`, адрес `10.10.10.30/24` - это внешняя сторона, отсюда есть выход в интернет через NAT, который уже настроен на самом хосте pve.
  - `net1` смотрит в `vmbr1`, адрес `10.20.20.1/24` - это внутренняя сторона, шлюз для внутренней сети.

```bash
# на Proxmox
qm clone 9000 106 --name nat-gateway --full
qm set 106 --net0 virtio,bridge=vmbr0 --net1 virtio,bridge=vmbr1
qm set 106 --ipconfig0 gw=10.10.10.1,ip=10.10.10.30/24 --ipconfig1 ip=10.20.20.1/24
qm start 106
```

```bash
# на самой nat-gateway (10.10.10.30)
echo "net.ipv4.ip_forward=1" | sudo tee /etc/sysctl.d/99-nat-gateway.conf
sudo sysctl --system
sudo iptables -t nat -A POSTROUTING -s 10.20.20.0/24 -o eth0 -j MASQUERADE
sudo iptables -A FORWARD -i eth1 -o eth0 -j ACCEPT
sudo iptables -A FORWARD -i eth0 -o eth1 -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo netfilter-persistent save
```

## e. Перенос app-VM во внутреннюю сеть

VM 105 с приложением (из пунктов b, c, d) переключил с `vmbr0` на `vmbr1` и дал ей адрес во внутренней сети, а шлюзом указал nat-gateway:

```bash
qm set 105 --net0 virtio=BC:24:11:E3:E9:1C,bridge=vmbr1
qm set 105 --ipconfig0 gw=10.20.20.1,ip=10.20.20.20/24
qm stop 105 && qm start 105
```

Теперь достучаться до неё можно только через nat-gateway как прыжок:
```bash
ssh -J pve,ubuntu@10.10.10.30 ubuntu@10.20.20.20 \
  "curl -s -o /dev/null -w 'http: %{http_code}\n' http://example.com; ping -c2 8.8.8.8"
```

Получил `http: 200` и рабочий пинг - значит трафик из внутренней сети действительно уходит наружу через nat-gateway. Само приложение (и systemd-сервис, и docker compose стек) при этом продолжило работать без каких-либо изменений, просто по другому адресу.

## f. Кластер Kubernetes

Кластер kubeadm у меня уже был поднят и работал на момент выполнения этого задания:

| VM | vmid | IP | роль |
|---|---|---|---|
| master01 | 101 | 10.10.10.10 | control-plane |
| worker01 | 102 | 10.10.10.11 | worker |
| worker02 | 103 | 10.10.10.12 | worker |
| worker03 | 104 | 10.10.10.13 | worker |

Ubuntu Server 22.04, kubeadm и kubelet версии v1.29.3, сеть - Calico. Проверка:
```bash
kubectl --kubeconfig=/etc/kubernetes/admin.conf get nodes -o wide
```
Все четыре ноды в статусе Ready.

## g. Деплой приложения в кластер

Своего registry нет, поэтому образ `webapp:1.0` собрал прямо на master01 (Docker туда тоже поставил временно через `get.docker.com`), сохранил его в файл и руками закинул в containerd на всех четырёх нодах:

```bash
docker build -t webapp:1.0 .
docker save webapp:1.0 -o webapp.tar
# и на каждой ноде (master01, worker01, worker02, worker03):
sudo ctr -n k8s.io images import webapp.tar
```

Манифесты лежат в [k8s/namespace.yaml](k8s/namespace.yaml) и [k8s/deployment.yaml](k8s/deployment.yaml) - три реплики, `imagePullPolicy: IfNotPresent`, readiness и liveness проверяют `/health`.

```bash
kubectl apply -f k8s/namespace.yaml -f k8s/deployment.yaml
kubectl get pods -n webapp -o wide
```

В итоге три пода в статусе Running и Ready, раскиданы по worker01, worker02 и worker03.

## h. Ingress без port-forward

Поставил `ingress-nginx` - взял официальный baremetal-манифест (`controller-v1.11.3`), он сам создаёт сервис типа NodePort:

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.3/deploy/static/provider/baremetal/deploy.yaml
kubectl apply -f k8s/ingress.yaml
kubectl get svc -n ingress-nginx ingress-nginx-controller
```

Сам Ingress-ресурс - [k8s/ingress.yaml](k8s/ingress.yaml).

Доступ снаружи проверял напрямую по IP ноды и NodePort, без всякого `kubectl port-forward`:
```bash
curl -i -X POST http://10.10.10.11:32061/                    # 403
curl -i -X POST -H "Test: Hello" http://10.10.10.11:32061/   # 200 Hello, World!
```

Kubernetes сам выбрал порт из диапазона 30000-32767 - в моём случае получилось 32061 для 80 и 30350 для 443.

## Структура каталога

```
9/
  app/         приложение и Dockerfile (a, c)
  systemd/     unit-файл для systemd-сервиса (b)
  monitoring/  docker-compose с prometheus и alertmanager (d)
  k8s/         манифесты namespace, deployment, ingress (g, h)
  README.md
```
