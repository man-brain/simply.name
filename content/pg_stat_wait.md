Title: Интерфейс ожиданий в PostgreSQL
Date: 2015-11-16 16:00
Category: PostgreSQL
Tags: PostgreSQL, monitoring, debugging
Lang: ru
Slug: pg-stat-wait

Люди, имеющие опыт работы с коммерческими СУБД, привыкли к тому, что могут
получить ответ на вопрос "Чем прямо сейчас занимается конкретная сессия?"
Или ещё лучше "Чего ждала каждая сессия 5 минут назад?" Долгое время
PostgreSQL не имел таких средств диагностики и DBA приходилось выкручиваться
разной степени изощрённости способами. О том, как это делаем мы, я
[рассказывал]({filename}/pgday2015_slides.html) на pgday.ru. Этот доклад
я читал не один, а вместе с Ильдусом Курбангалиевым из PostgrePro. И Ильдус
как раз рассказывал об инструменте, который позволяет ответить на вопросы выше.

Строго говоря, это далеко не первая попытка реализовать то, что люди привыкли
называть интерфейсом [событий] ожиданий, но все предыдущие не были доведены
до какого-либо разумного состояния, оставаясь proof of concept патчами. А вот
`pg_stat_wait` вполне себе доступен [в виде набора патчей к текущей стабильной
ветке 9.4](https://github.com/postgrespro/postgres/tree/waits_monitoring_94) и
разрабатываемой нынче 9.6 (актуальные версии стоит искать в pgsql-hackers@).

После довольно продолжительного тестирования и исправления ряда багов мы не
просто посчитали эти патчи полезными, но даже пригодными для использования
в бою. Довольно долго мы катили эти изменения в production и ничего такого
не случилось :)

###Установка
До того, как всё это попадёт в ядро PostgreSQL, нужно пересобирать postgres.
Пересборку в виде `./configure && make && sudo make install`, думаю, описывать
смысла нет - лучше посмотреть в
[документации](http://www.postgresql.org/docs/9.4/static/install-procedure.html).

После этого в `shared_preload_libraries` надо будет добавить `pg_stat_wait`.
Кроме того, в `postgresql.conf` можно добавить следующие опции:

  * `waits_monitoring = on` - включение функциональности как таковой,
  * `pg_stat_wait.history = on` - хранение истории ожиданий,
  * `pg_stat_wait.history_size = 1000000` - количество событий в истории,
  * `pg_stat_wait.history_period = 1000` - как часто сохранять события ожидания
  в историю (мс).

После этого стоит запустить PostgreSQL и сказать `CREATE EXTENSION
pg_stat_wait`. После этого всё начнёт работать.

###Возможности
А что именно начнёт работать? Первым делом стоит посмотреть, что входит в
состав расширения:

    :::PostgresConsoleLexer
    rpopdb01g/postgres M # \dxS+ pg_stat_wait
               Objects in extension "pg_stat_wait"
                       Object Description
    ---------------------------------------------------------
     function pg_is_in_trace(integer)
     function pg_start_trace(integer,cstring)
     function pg_stat_wait_get_current(integer)
     function pg_stat_wait_get_history()
     function pg_stat_wait_get_profile(integer,boolean)
     function pg_stat_wait_make_test_lwlock(integer,integer)
     function pg_stat_wait_reset_profile()
     function pg_stop_trace(integer)
     function pg_wait_class_list()
     function pg_wait_event_list()
     view pg_stat_wait_current
     view pg_stat_wait_history
     view pg_stat_wait_profile
     view pg_wait_class
     view pg_wait_event
     view pg_wait_events
    (16 rows)

    rpopdb01g/postgres M #

Давайте посмотрим, какие события ожидания `pg_stat_wait` умеет мониторить:

    :::PostgresConsoleLexer
    rpopdb01g/postgres M # SELECT version();
                                                        version
    ---------------------------------------------------------------------------------------------------------------
     PostgreSQL 9.4.5 on x86_64-unknown-linux-gnu, compiled by gcc (GCC) 4.4.7 20120313 (Red Hat 4.4.7-11), 64-bit
    (1 row)

    rpopdb01g/postgres M # SELECT class_name, count(event_name)
    FROM pg_wait_events GROUP BY 1 ORDER BY 2 DESC;
     class_name | count
    ------------+-------
     LWLocks    |    52
     Storage    |     9
     Locks      |     9
     Network    |     3
     Latch      |     1
     CPU        |     1
    (6 rows)

    rpopdb01g/postgres M #

Можно увидеть, что мониторинг ожиданий для 9.4 знает 52 типа легковесных
блокировок, а например, для диска умеет отслеживать следующие вещи:


    :::PostgresConsoleLexer
    rpopdb01g/postgres M # SELECT * FROM pg_wait_events WHERE class_id = 3;
     class_id | class_name | event_id | event_name
    ----------+------------+----------+------------
            3 | Storage    |        0 | SMGR_READ
            3 | Storage    |        1 | SMGR_WRITE
            3 | Storage    |        2 | SMGR_FSYNC
            3 | Storage    |        3 | XLOG_READ
            3 | Storage    |        4 | XLOG_WRITE
            3 | Storage    |        5 | XLOG_FSYNC
            3 | Storage    |        6 | SLRU_READ
            3 | Storage    |        7 | SLRU_WRITE
            3 | Storage    |        8 | SLRU_FSYNC
    (9 rows)

    rpopdb01g/postgres M #

Под "умеет отслеживать" понимается тот факт, что можно посмотреть:

  * Чего прямо сейчас ждёт конкретный процесс и *как долго*?
  * Сколько раз конкретный процесс повисал в ожидании каждого события и *как
  много* времени суммарно провёл в ожидании?
  * Чего ждал конкретный процесс какое-то время назад?

Для ответов на эти вопросы есть представления `pg_stat_wait_current`,
`pg_stat_wait_profile` и `pg_stat_wait_history` соответственно. Лучше всего
рассмотреть на примерах.

####pg_stat_wait_current

    :::PostgresConsoleLexer
    rpopdb01g/postgres M # SELECT pid, class_name, event_name, wait_time
    FROM pg_stat_wait_current WHERE class_id NOT IN (4, 5)
    ORDER BY wait_time DESC;
      pid  | class_name |  event_name   | wait_time
    -------+------------+---------------+-----------
     23510 | LWLocks    | BufferLWLocks |     17184
     23537 | LWLocks    | BufferLWLocks |      9367
     23628 | LWLocks    | BufferLWLocks |      9366
     23502 | LWLocks    | BufferLWLocks |      3215
     23504 | LWLocks    | BufferLWLocks |      2846
     23533 | LWLocks    | BufferLWLocks |      2788
     23514 | LWLocks    | BufferLWLocks |      2658
     23517 | LWLocks    | BufferLWLocks |      2658
     23532 | LWLocks    | BufferLWLocks |      2641
     23527 | LWLocks    | BufferLWLocks |      2507
     23952 | Storage    | SMGR_READ     |      2502
     23518 | Storage    | XLOG_FSYNC    |      1576
     23524 | LWLocks    | WALWriteLock  |      1027
    (13 rows)

    rpopdb01g/postgres M #

Мы исключаем ожидания сети и латчей, поскольку время их ожидания обычно на
несколько порядков больше времени ожидания остальных классов. Ну и это далеко
не все столбцы, которые есть в представлении:

    :::PostgresConsoleLexer
    smcdb01d/postgres M # SELECT * FROM pg_stat_wait_current
    WHERE class_id IN (2, 3) LIMIT 2;
    -[ RECORD 1 ]-----------------------------
    pid        | 12107
    sample_ts  | 2015-11-16 10:36:59.598562+03
    class_id   | 2
    class_name | Locks
    event_id   | 4
    event_name | Transaction
    wait_time  | 24334
    p1         | 5
    p2         | 255593733
    p3         | 0
    p4         | 0
    p5         | 0
    -[ RECORD 2 ]-----------------------------
    pid        | 1266
    sample_ts  | 2015-11-16 10:36:59.598562+03
    class_id   | 3
    class_name | Storage
    event_id   | 0
    event_name | SMGR_READ
    wait_time  | 1710
    p1         | 1663
    p2         | 16400
    p3         | 20508
    p4         | 0
    p5         | 220036

    smcdb01d/postgres M #

Параметры `p1`-`p5` -- это текстовые поля. Например, для heavy-weight блокировок
они дают примерно ту же информацию, что можно найти в `pg_locks`, а для
событий дискового I/O можно понять, из каких базы, отношения, блока мы ожидали
чтения.

####pg_stat_wait_profile

Например, можно посмотреть, сколько времени база тратила в каждом из типов
ожиданий:

    :::PostgresConsoleLexer
    rpopdb01g/postgres M # SELECT class_name, sum(wait_time) AS wait_time,
    sum(wait_count) AS wait_count FROM pg_stat_wait_profile
    GROUP BY class_name ORDER BY wait_time DESC;
     class_name |  wait_time   | wait_count
    ------------+--------------+------------
     Network    | 144196945815 |   11877848
     Latch      |  90164921148 |    3521073
     LWLocks    |   2648490737 |   10501900
     Storage    |    977430136 |   36444251
     CPU        |     68890774 |  365699457
     Locks      |           74 |          1
    (6 rows)

    rpopdb01g/postgres M #

Или, например, какие легковесные блокироки являются самыми горячими:

    :::PostgresConsoleLexer
    rpopdb01g/postgres M # SELECT event_name, sum(wait_time) AS wait_time,
    sum(wait_count) AS wait_count FROM pg_stat_wait_profile
    WHERE class_id = 1 AND wait_time != 0 AND wait_count != 0
    GROUP BY event_name ORDER BY wait_time DESC;
          event_name      | wait_time  | wait_count
    ----------------------+------------+------------
     LockMgrLWLocks       | 1873294341 |    3870685
     WALWriteLock         | 1039279117 |     859101
     BufferLWLocks        |  299153931 |    7356555
     BufFreelistLock      |    7466923 |      75484
     ProcArrayLock        |    2321769 |      34355
     CLogControlLock      |     778148 |      21286
     WALInsertLocks       |     456224 |       7451
     BufferMgrLocks       |     107374 |       8447
     XidGenLock           |      84914 |       2506
     UserDefinedLocks     |       1875 |          7
     CLogBufferLocks      |        868 |         80
     SInvalWriteLock      |         11 |          3
     CheckpointerCommLock |          1 |          1
    (13 rows)

    Time: 29.388 ms
    rpopdb01g/postgres M #

Эти два примера хорошо показывают, что время ожидания не всегда коррелирует
с количеством самих ожиданий, а потому семплирование без учёта времени ожиданий
может давать не слишком правильную картину мира.

####pg_stat_wait_history

Это представление позволяет увидеть, чего ожидал конкретный процесс в прошлом.
Глубина хранения и интервал семплирования данных настраивается, как описано
выше.

    :::PostgresConsoleLexer
    xivadb01e/postgres M # SELECT sample_ts, class_name, event_name, wait_time
    FROM pg_stat_wait_history WHERE pid = 29585 ORDER BY sample_ts DESC LIMIT 10;
               sample_ts           | class_name |   event_name    | wait_time
    -------------------------------+------------+-----------------+-----------
     2015-11-16 10:56:28.544052+03 | LWLocks    | BufferMgrLocks  |    983997
     2015-11-16 10:56:27.542938+03 | LWLocks    | CLogControlLock |    655975
     2015-11-16 10:56:26.850302+03 | LWLocks    | WALInsertLocks  |    979516
     2015-11-16 10:56:25.849207+03 | LWLocks    | WALInsertLocks  |    207418
     2015-11-16 10:56:24.848059+03 | LWLocks    | WALInsertLocks  |    923916
     2015-11-16 10:56:23.846909+03 | LWLocks    | WALInsertLocks  |    753185
     2015-11-16 10:56:22.845808+03 | LWLocks    | WALInsertLocks  |    877707
     2015-11-16 10:56:21.844718+03 | LWLocks    | WALInsertLocks  |    778897
     2015-11-16 10:56:20.843562+03 | LWLocks    | CLogControlLock |    991267
     2015-11-16 10:56:19.842464+03 | LWLocks    | CLogControlLock |   1001059
    (10 rows)

    xivadb01e/postgres M #

####Трассировка сессии

Все описанные выше представления рассчитаны на то, что они могут быть включены
всегда, т.е. они сделаны с минимальным overhead'ом по производительности. Но
бывают случаи, когда семплирования раз в `pg_stat_wait.history_period`
недостаточно и нужно увидеть все события ожидания процесса. В этом случае стоит
использовать функции для трассировки, например, так:

    :::PostgresConsoleLexer
    rpopdb01g/postgres M # SELECT pg_backend_pid();
     pg_backend_pid
    ----------------
               5399
    (1 row)

    rpopdb01g/postgres M # SELECT pg_start_trace(5399, '/tmp/5399.trace');
    INFO:  00000: Trace was started to: /tmp/5399.trace
    LOCATION:  StartWait, wait.c:259
     pg_start_trace
    ----------------

    (1 row)

    rpopdb01g/postgres M # SELECT pg_is_in_trace(5399);
     pg_is_in_trace
    ----------------
     t
    (1 row)

    -- some activity

    rpopdb01g/postgres M # SELECT pg_stop_trace(5399);
    INFO:  00000: Trace was stopped
    LOCATION:  StartWait, wait.c:265
     pg_stop_trace
    ---------------

    (1 row)

    rpopdb01g/postgres M #

Будет создан обычный текстовый файл, где на каждое событие ожидания будет
записываться две строки, например:

    :::TextLexer
    start 2015-11-16 11:17:26.831686+03 CPU MemAllocation 0 0 0 0 0
    stop 2015-11-16 11:17:26.831695+03 CPU
    start 2015-11-16 11:17:26.831705+03 LWLocks BufferLWLocks 122 1 0 0 0
    stop 2015-11-16 11:17:26.831715+03 LWLocks
    start 2015-11-16 11:17:26.831738+03 Network WRITE 0 0 0 0 0
    stop 2015-11-16 11:17:26.831749+03 Network
    start 2015-11-16 11:17:26.831795+03 Network READ 0 0 0 0 0
    stop 2015-11-16 11:17:26.831808+03 Network
    start 2015-11-16 11:17:26.831825+03 Storage SMGR_READ 1663 13003 12763 0 13
    stop 2015-11-16 11:17:26.831844+03 Storage

###Вместо заключения

Интерфейс ожиданий -- долгожданная функциональность в PostgreSQL, которая
позволяет значительно лучше понимать, что именно происходит с базой. Прямо
сейчас эта функциональность толкается в ядро PostgreSQL, чтобы начиная с 9.6
не требовалось пересобирать postgres для её работы.

На всякий случай скажу, что незадолго до того, как Ильдус
[представил](http://www.postgresql.org/message-id/559D4729.9080704@postgrespro.ru)
свою реализацию на pgsql-hackers@, идею сделать wait interface
[озвучил](http://www.postgresql.org/message-id/CA+TgmoYd3GTz2_mJfUHF+RPe-bCy75ytJeKVv9x-o+SonCGApw@mail.gmail.com)
Robert Haas. И очевидно, эту идею поддержали многие. Для того, чтобы это
случилось, уже принято пару подготовительных патчей, например,
[Refactoring of LWLock tranches](http://www.postgresql.org/message-id/3F71DA37-A17B-4961-9908-016E6323E612@postgrespro.ru).

Очень надеемся, что мы увидим это в 9.6.
