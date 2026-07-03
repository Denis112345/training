# Задание 10. Безопасность контейнеризации

Делал на том же кластере, что и в задании 9 (master01 + worker01-03 на Proxmox, `ssh pve`).

## a. Расширения безопасности платформы

### Cilium вместо Calico

Кластер работал на Calico, а Cilium ставится как основной CNI - пришлось полностью заменить сетевой плагин на живом кластере.

```bash
# удалил Calico
kubectl delete daemonset calico-node -n kube-system
kubectl delete deployment calico-kube-controllers -n kube-system
kubectl get crd -o name | grep calico | xargs kubectl delete

# на каждой ноде подчистил остатки CNI
rm -rf /etc/cni/net.d/*calico* /var/lib/cni/networks/*

# поставил Cilium с тем же pod-CIDR, что был у Calico (10.244.0.0/16), kube-proxy оставил
cilium install --version 1.19.3 \
  --set ipam.mode=kubernetes \
  --set kubeProxyReplacement=false \
  --set ipv4NativeRoutingCIDR=10.244.0.0/16

# пересоздал поды, которые остались на старой сети
kubectl delete pods -n webapp --all
kubectl delete pods -n ingress-nginx --all
```

`cilium status` - все DaemonSet'ы Ready, ноды Ready, приложение из задания 9 снова отвечает.

### Istio

```bash
curl -L https://istio.io/downloadIstio | ISTIO_VERSION=1.24.2 sh -
istioctl install -f istio-values.yaml -y
```

Профиль `minimal` с уменьшенными requests для istiod (100m CPU / 256Mi память) - дефолтные 2 CPU/2Gi не влезали в воркеры по 2Gi RAM. `istio-values.yaml` в [istio/](istio).

```bash
kubectl label namespace webapp istio-injection=enabled
kubectl delete pods -n webapp --all   # пересоздать с sidecar'ом
```

### OPA Gatekeeper

```bash
helm repo add gatekeeper https://open-policy-agent.github.io/gatekeeper/charts
helm install gatekeeper gatekeeper/gatekeeper \
  --namespace gatekeeper-system --create-namespace \
  --set controllerManager.resources.requests.memory=128Mi \
  --set audit.resources.requests.memory=128Mi
```

## b. Ограничение доступа наружу (Istio + Cilium)

Cilium работает на L3/L4 (включая ICMP), Istio - на L7 (HTTP/TCP через sidecar)

### Cilium

[cilium/network-policy.yaml](cilium/network-policy.yaml) - `CiliumNetworkPolicy` на namespace `webapp`: egress разрешён только на DNS, ICMP на 77.88.8.8 (health-check из задания 9), istiod и поды внутри namespace, всё остальное - deny. Ingress разрешён только из `ingress-nginx` и `istio-system`.

```bash
kubectl apply -f cilium/network-policy.yaml
```

Проверка через `cilium monitor`: для 77.88.8.8 и istiod - `action: allow`, для случайного IP (пробовал 1.2.3.4:81 изнутри пода) - `action: deny` с реальным drop пакета.

### Istio

[istio/sidecar-egress.yaml](istio/sidecar-egress.yaml) - `Sidecar` с `outboundTrafficPolicy.mode: REGISTRY_ONLY` (запрещает любой egress кроме сервисов mesh) + `ServiceEntry` на 77.88.8.8.

```bash
kubectl apply -f istio/sidecar-egress.yaml
```

После обеих политик приложение всё ещё отвечает через ingress:
```bash
curl -X POST -H "Test: Hello" http://10.10.10.11:32061/   # Hello, World!
curl http://10.10.10.11:32061/health                       # 200 OK
```

## c. Ограничения по ресурсам, файловой системе и пользователю

Всё в [k8s/](k8s):

- [k8s/resource-limits.yaml](k8s/resource-limits.yaml) - `ResourceQuota` на namespace и `LimitRange` на контейнер.
- [k8s/deployment-hardened.yaml](k8s/deployment-hardened.yaml) - Deployment из задания 9 с усиленным securityContext: `runAsNonRoot`, `runAsUser: 10001`, `readOnlyRootFilesystem: true` (с `emptyDir` под `/tmp`), `capabilities.drop: ["ALL"]`, `allowPrivilegeEscalation: false`, `seccompProfile: RuntimeDefault`.

```bash
kubectl apply -f k8s/resource-limits.yaml -f k8s/deployment-hardened.yaml
```

### Нюанс с `/health`

После applies `/health` стал отдавать 503. Дело оказалось не в capability для ping (пробовал `NET_RAW` + `setcap` - не помогло из-за того, как containerd прокидывает capability non-root процессам), а в том, что `net.ipv4.ping_group_range` внутри netns пода был `1 0` (непривилегированный ICMP выключен) - это per-namespace sysctl, Cilium создаёт netns с дефолтным значением, не наследуя настройку хоста (там `0 2147483647`). Починил через `securityContext.sysctls` прямо в поде:
```yaml
sysctls:
  - name: net.ipv4.ping_group_range
    value: "0 2147483647"
```
После этого ping идёт через непривилегированный ping socket, без каких-либо capability, совместимо с `readOnlyRootFilesystem` и `drop: ALL`.

### Gatekeeper constraint'ы

[gatekeeper/constraint-templates.yaml](gatekeeper/constraint-templates.yaml) - три шаблона: `K8sRequiredResources` (нужны limits+requests), `K8sRunAsNonRoot`, `K8sReadOnlyRootFilesystem`. [gatekeeper/constraints.yaml](gatekeeper/constraints.yaml) применяет их к namespace `webapp`.

```bash
kubectl apply -f gatekeeper/constraint-templates.yaml
kubectl apply -f gatekeeper/constraints.yaml
```

Проверка - под без нужных полей реально отклоняется:
```
Error from server (Forbidden): admission webhook "validation.gatekeeper.sh" denied the request:
[webapp-readonly-rootfs] container <bad> must set securityContext.readOnlyRootFilesystem: true
[webapp-run-as-nonroot] pod must set spec.securityContext.runAsNonRoot: true
```

Сам `webapp` Deployment проходит все три constraint'а (`kubectl get constraints` - `TOTAL-VIOLATIONS: 0`).

## Структура каталога

```
10/
  istio/         Sidecar + ServiceEntry для egress-ограничений (a, b)
  cilium/        CiliumNetworkPolicy для egress/ingress (a, b)
  gatekeeper/    ConstraintTemplate + Constraint (a, c)
  k8s/           ResourceQuota, LimitRange, hardened Deployment (c)
  README.md
```
