Title: Лаг репликации PostgreSQL в секундах
Date: 2015-06-14 16:00
Category: PostgreSQL
Tags: PostgreSQL, bgworker, sources, replication, monitoring
Lang: ru
Slug: postgresql-replication-monitoring

Наш классический шард PostgreSQL состоит из мастера и двух реплик. Мы мониторим
тот факт, что реплик ровно столько, сколько должно быть (зажигаем WARN, если
осталась одна, и CRIT, если реплик не осталось). И мониторим отставание реплик,
а именно `replay_location`. Всё это делается парой простых запросов в
`pg_stat_replication`.

У этого способа есть два существенных недостатка:

  * Доставать бОльшую часть данных из `pg_stat_replication` могут только
пользователи с опцией `SUPERUSER`. Давать такую пользователю для мониторинга не
очень хорошо.
  * Пороги для лага репликации на всех кластерах мы ставим разными, потому что
10&nbsp;МБ лага на кластере, куда записи 1&nbsp;МБ/с, и на кластере с 100&nbsp;МБ/с записи --
сильно разные вещи.

Для решения обеих проблем мы написали
[bgworker](http://www.postgresql.org/docs/current/static/bgworker.html),
исходники которого лежат [тут](https://github.com/dev1ant/repl_mon).

Принцип работы очень простой -- bgworker раз в какое-то время (настраивается с
точностью до милисекунды) пишет в какую-то табличку (по-умолчанию `repl_mon`, но
имя настраивается) следующие вещи:

    :::PostgresConsoleLexer
    pgtest02g/postgres M # \dS+ repl_mon
                                     Table "public.repl_mon"
      Column  |           Type           | Modifiers | Storage  | Stats target | Description
    ----------+--------------------------+-----------+----------+--------------+-------------
     ts       | timestamp with time zone |           | plain    |              |
     location | text                     |           | extended |              |
     replics  | integer                  |           | plain    |              |

    pgtest02g/postgres M # select * from repl_mon ;
                  ts               |  location  | replics
    -------------------------------+------------+---------
     2015-06-14 15:35:51.632041+03 | 0/1E04E568 |       2
    (1 row)

    Time: 0.664 ms
    pgtest02g/postgres M #

Запрос для получения данных можно увидеть
[тут](https://github.com/dev1ant/repl_mon/blob/8e14fb52/repl_mon.c#L127-L131).

Количество живых реплик можно доставать прямо из этой таблички на мастере, а
на репликах можно сравнивать значения из полей `ts` и `location` с текущим
временем и `pg_last_xlog_replay_location()`:

    :::PostgresConsoleLexer
    pgtest02d/postgres R # SELECT (current_timestamp - ts) AS lag_time, greatest(0,
    pg_xlog_location_diff(location::pg_lsn, pg_last_xlog_replay_location()))
    AS lag_bytes FROM repl_mon ;
        lag_time     | lag_bytes
    -----------------+-----------
     00:00:00.516017 |         0
    (1 row)

    Time: 0.724 ms
    pgtest02d/postgres R #

Важно, что всё это не требует прав суперпользователя.

Для работы этой штуки надо в каталоге с исходниками сказать `make` и `sudo make
install`. Затем в `shared_preload_libraries` добавить `repl_mon` и перезапустить
PostgreSQL.

Надеюсь, кому-нибудь оно будет полезно.

P.S. Отдельное спасибо стоит сказать Michael Paquier, который поддерживает
[pg_plugins](https://github.com/michaelpq/pg_plugins) -- шаблоны простых
расширений для PostgreSQL. БОльшую часть кода я скопировал оттуда.
