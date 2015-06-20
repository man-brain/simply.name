Title: Pgcheck и отставшие реплики
Date: 2014-12-23 21:00
Category: PostgreSQL
Tags: PostgreSQL, plproxy, pgcheck
Lang: ru
Slug: pgcheck-and-delayed-replics

Два месяца назад мы [анонсировали]({filename}/pgcheck_announce.md) pgcheck -- инструмент для автоматической балансировки нагрузки на базы PostgreSQL с использованием PL/Proxy. Сегодня мы поправили все найденные проблемы, связанные с новой функциональностью -- pgcheck теперь учитывает отставание реплик и не отправляет читающие запросы на отставшие реплики.

Исходники и документация на [github](https://github.com/yandex/pgcheck). Наслаждайтесь.
