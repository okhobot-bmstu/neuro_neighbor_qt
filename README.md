# Neuro Neighbor QT

Qt-интерфейс для AI-ассистента с голосовым вводом/выводом, поддержкой нейросетевых моделей, памятью контекста и возможностью выполнения консольных команд через нейросеть.

## Установка

### Windows

```bat
install_deps.bat        # CPU
install_deps_cuda.bat   # CUDA (автоопределение версии)
```

### Linux

```bash
bash install_deps.sh        # CPU
bash install_deps_cuda.sh   # CUDA (автоопределение версии)
```

Скрипты создают виртуальное окружение `venv/`, устанавливают PyTorch, llama-cpp-python, зависимости из `requirements.txt` и пакет `ai_nn`.

## Запуск

```bash
# Windows
run.bat

# Linux
bash run.sh
```

## Структура проекта

- `main.py` — точка входа Qt-приложения
- `widgets/` — компоненты интерфейса
- `styles/` — QSS-стили
- `ai_nn/` — модуль AI-ассистента (STT, TTS, нейросеть, память)
- `config/` — конфигурационные файлы
- `assets/` — ресурсы

## Конфигурация

Настройки приложения задаются в `config/config.json` (пример — `config/config_template.json`) или через интерфейс приложения.

## Требования

- Python 3.8+
- Для CUDA — видеокарта NVIDIA с драйвером и CUDA Toolkit (опционально)

## Лицензия

GNU General Public License v3 (GPLv3). См. [LICENSE](LICENSE).
