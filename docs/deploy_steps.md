# Деплой и запуск фида

## 1. Подготовить репозиторий

```bash
git init
git add .
git commit -m "Initial RC Books Yandex feed generator"
git branch -M main
git remote add origin https://github.com/<username>/<repo>.git
git push -u origin main
```

## 2. Включить GitHub Pages

1. Открыть GitHub repo.
2. Settings → Pages.
3. Source: GitHub Actions.

## 3. Запустить первый workflow

1. Actions → Update Yandex Feed.
2. Run workflow.
3. Дождаться зелёного статуса.

## 4. Проверить опубликованный фид

Открыть:

```text
https://<username>.github.io/<repo>/yandex-books.yml
```

Если файл открывается в браузере, можно добавлять его в Директ.

## 5. Добавить в Яндекс Директ

1. Директ → Библиотека → Фиды.
2. Добавить фид.
3. Выбрать URL.
4. Указать ссылку на `yandex-books.yml`.
5. Дождаться проверки.
6. Исправить ошибки, если Директ их покажет.

## 6. Подключить к кампании

1. Создать / открыть ЕПК или товарную кампанию.
2. Выбрать собственный фид.
3. Группа `Viewed books`: включить офферный ретаргетинг.
4. Группа `No book views`: фильтр `is_popular=true` или `is_new=true`.
5. Группа `Popular`: фильтр `is_popular=true`.
6. Группа `Cheap`: фильтр `is_cheap=true`.

## 7. После запуска

Проверять ежедневно:

- статус workflow;
- `output/parsing_report.csv`;
- количество офферов в Директе;
- ошибки обработки фида в Директе;
- совпадение URL фида с URL страниц в Метрике.
