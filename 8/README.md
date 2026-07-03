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

# Jobs

## Job_1

```
New Item - Freestyle project - Job_1
```

```
Source Code Management:
  - Git
  - Repository URL: git@github.com:Denis112345/training.git
  - Branch: */master
  - Credentials: Добавил свой ключ через секреты
```

```
Build Steps:
 - Execute shell:
   echo "Код на месте в $WORKSPACE"
   ls -la
```

```
Post-build Actions:
  - Build other projects: Job_2
  - Trigger only if build is stable
```

## Job_2

```
Build Steps:
 - Execute shell:
    cp -r /var/lib/jenkins/workspace/Job_1/* $WORKSPACE/ 2>/dev/null || true
    cp -r /var/lib/jenkins/workspace/Job_1/.git $WORKSPACE/ 2>/dev/null || true

    cd $WORKSPACE
    rm -f test.txt test2.txt

    git config --global user.email "admin@admin.com"
    git config --global user.name "admin"

    git add -A
    git commit -m "rm test.txt test2.txt"

    echo "All good, удалили что нужно:"
    ls -la
```

## Job_3

```
Environment:
  SSH User Private Key:
    Key File Variable: SSH_KEY
    Credentials: git
```

```
Build Steps:
 - Execute shell:
    cd /var/lib/jenkins/workspace/Job_2
    git remote set-url origin git@github.com:Denis112345/training.git
    git checkout -B main

    export GIT_SSH_COMMAND="ssh -i $SSH_KEY -o StrictHostKeyChecking=no"
    git push origin main
    echo "Запушили наши изменения"
```