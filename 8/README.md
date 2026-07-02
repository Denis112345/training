# Установка Java и Jenkins

```bash
sudo apt update
sudo apt install -y fontconfig openjdk-21-jre-headless

# Ставим ключи чтобы скачать с помощью apt Jenkins
tmp=$(mktemp -d)
gpg --homedir "$tmp" --keyserver keyserver.ubuntu.com \
    --recv-keys 7198F4B714ABFC68
gpg --homedir "$tmp" --export 7198F4B714ABFC68 | \
    sudo tee /usr/share/keyrings/jenkins-keyring.gpg > /dev/null
rm -rf "$tmp"

echo "deb [signed-by=/usr/share/keyrings/jenkins-keyring.gpg] \
https://pkg.jenkins.io/debian-stable binary/" | \
    sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null

sudo apt update
sudo apt install -y jenkins

# Включаем автозапуск и сам сервис
sudo systemctl enable --now jenkins

# Посмотрим дефолтный пароль чтобы зайти
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

Далее установил дефолтные плагины для реализации задачи их хватит

