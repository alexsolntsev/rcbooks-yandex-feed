# RC Books → Yandex Direct feed generator

Проект генерирует собственный YML-фид книг для Яндекс Директа без доступа к backend сайта.

## Что делает проект

1. Собирает URL карточек книг из `sitemap.xml`, каталога, страниц жанров/новинок/популярных книг.
2. Парсит карточки книг.
3. Собирает поля для YML-фида: `offer_id`, `url`, `name`, `price`, `picture`, `vendor`, `description`.
4. Добавляет служебные параметры для рекламных сценариев: `is_new`, `is_popular`, `is_cheap`, `feed_group`, `priority`.
5. Применяет ручные правки из `input/overrides.csv`.
6. Генерирует `output/yandex-books.yml`.
7. Валидирует фид.
8. Через GitHub Actions ежедневно обновляет фид и публикует его через GitHub Pages.

## Структура

```text
rcbooks-yandex-feed/
  input/
    config.yml          # настройки сайта, правил классификации и селекторов
    seed_urls.csv       # стартовые URL: sitemap и страницы каталога
    overrides.csv       # ручные правки и исключения
  output/
    yandex-books.yml    # итоговый фид для Директа
    books_urls.csv      # собранные URL карточек
    books_parsed.csv    # распарсенные данные книг
    parsing_report.csv  # отчёт по качеству
  scripts/
    01_collect_urls.py
    02_parse_books.py
    03_apply_overrides.py
    04_generate_yml.py
    05_validate_feed.py
    run_pipeline.py
  .github/workflows/update-feed.yml
```

## Как настроить под реальный сайт

### 1. Обновить `input/seed_urls.csv`

Добавьте реальные URL сайта:

```csv
type,url
sitemap,https://rcbooks.com/sitemap.xml
catalog,https://rcbooks.com/books
catalog,https://rcbooks.com/catalog
```

Если каталог находится по другим адресам, замените ссылки.

### 2. Обновить паттерны URL в `input/config.yml`

В блоке `crawl.book_url_patterns` укажите фрагменты URL, которые отличают карточки книг:

```yaml
book_url_patterns:
  - "/book/"
  - "/books/"
```

Если карточки выглядят иначе, например `/library/slug`, добавьте этот паттерн.

### 3. Настроить CSS-селекторы

Парсер сначала ищет JSON-LD, embedded JSON и meta-теги. Если данных там нет, он использует fallback-селекторы из `config.yml`:

```yaml
selectors:
  title:
    - "h1"
    - ".book-title"
  price:
    - ".price"
```

После первого теста откройте `output/books_parsed.csv` и добавьте/исправьте селекторы, если часть полей не подтянулась.

### 4. Настроить ручные правки в `input/overrides.csv`

Пример:

```csv
url,force_offer_id,force_title,force_author,force_price,force_image_url,force_is_new,force_is_popular,force_is_cheap,exclude,custom_description,priority,comment
https://rcbooks.com/books/book-1,,,,,,true,,,false,,90,новинка
https://rcbooks.com/books/book-2,,,,,,,true,,false,,80,популярная
https://rcbooks.com/books/bad-book,,,,,,,,,true,,0,исключить из рекламы
```

## Запуск локально

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/run_pipeline.py
```

После выполнения проверьте:

```text
output/yandex-books.yml
output/parsing_report.csv
output/books_parsed.csv
```

## Автообновление через GitHub Pages

1. Создайте новый GitHub-репозиторий.
2. Загрузите туда весь проект.
3. В настройках репозитория откройте **Settings → Pages**.
4. Source: **GitHub Actions**.
5. Запустите workflow вручную: **Actions → Update Yandex Feed → Run workflow**.
6. После успешного деплоя фид будет доступен по ссылке:

```text
https://<github-username>.github.io/<repo-name>/yandex-books.yml
```

Эту ссылку нужно добавить в Яндекс Директ как фид по URL.

## Как подключить к Директу

1. Директ → Библиотека → Фиды → Добавить фид.
2. Выбрать добавление по ссылке.
3. Указать ссылку на `yandex-books.yml`.
4. Дождаться обработки.
5. Подключить фид к ЕПК / товарной кампании.
6. В группе для пользователей, которые смотрели книги, включить офферный ретаргетинг.
7. В группах fallback использовать параметры:
   - `is_new=true`
   - `is_popular=true`
   - `is_cheap=true`

## Важные правила

- В `<url>` фида должен быть чистый canonical URL книги без UTM.
- UTM лучше добавлять в Директе на уровне кампании/группы, а не в фиде.
- `offer_id` должен быть стабильным и не меняться между обновлениями.
- Когда eCommerce ID будет подключён в Метрике, `product.id` должен совпадать с `offer_id` в фиде.
- Если eCommerce ID пока нет, Директ может пытаться сопоставлять просмотренные товары по URL через офферный ретаргетинг.
- Тексты объявлений кладём в `<description>`.
- Не используйте текст “вы уже смотрели эту книгу” до проверки, что показ идёт именно по просмотренному товару, а не по рекомендациям.

## Проверка качества

Скрипт `05_validate_feed.py` проверяет:

- количество валидных офферов;
- дубли `offer_id`;
- наличие названия, цены, картинки и URL;
- количество новых / популярных / недорогих книг.

Если валидация не проходит, workflow падает и не публикует новый фид.
