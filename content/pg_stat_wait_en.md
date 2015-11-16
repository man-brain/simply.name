Title: Wait interface in PostgreSQL
Date: 2015-11-16 16:00
Category: PostgreSQL
Tags: PostgreSQL, monitoring, debugging
Lang: en
Slug: pg-stat-wait

People having experience with commercial RDBMS are used to have the ability
to answer the question "What a particular session is doing right now?" Or
even "What was that session waiting 5 minutes ago?" For a long time PostgreSQL
did not have such diagnostic tools and DBAs used to get out with different
ways of sophistication. I [gave a talk]({filename}/pgday2015_slides.html) on
pgday.ru (in Russian) about how we do it. This talk was collaborative with
Ildus Kurbangaliev from PostgrePro. And Ildus was just speaking about tool
that allows to answer questions above.

Strictly speaking it is not the first try to implement what people used to call
wait [events] interface, but all previous attempts were not brought to some
reasonable state and died as proof of concept patches. But `pg_stat_wait` is
currently available [as a set of patches to current stable 9.4
branch](https://github.com/postgrespro/postgres/tree/waits_monitoring_94) and
currently developing 9.6 (actual versions should be looked at pgsql-hackers@).

After quite long testing and fixing bugs we even deployed them to production.

###Installation

Before it all becomes part of core PostgreSQL you need to recompile postgres.
I think description of rebuilding as `./configure && make && sudo make install`
is meaningless -- much better to look into
[documentation](http://www.postgresql.org/docs/9.4/static/install-procedure.html).

After it you should add `pg_stat_wait` to `shared_preload_libraries`.
Additionally, you can add following options to `postgresql.conf`:

  * `waits_monitoring = on` - enabling functionality on,
  * `pg_stat_wait.history = on` - storing history of wait events,
  * `pg_stat_wait.history_size = 1000000` - number of last events to keep
  in history,
  * `pg_stat_wait.history_period = 1000` - how often should wait events be
  stored in history (ms).

After that you should restart PostgreSQL and make `CREATE EXTENSION
pg_stat_wait`. After that everything will start working.

###Capabilities

What exactly will start to work? First you may look at what is inside the
extension:

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

Let's see what wait events `pg_stat_wait` is able to monitor:

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

You can see that waits monitoring for 9.4 knows about 52 LWLocks and
for disk, for example, it can track next things:

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

Under "can track" the following is meant:

  * What and *how long* a particular process is waiting right now?
  * How many times a particular process hung in waiting of every event type
  and *how much time* did it spend waiting?
  * What was a particular process waiting some time ago?

For answering these questions there are `pg_stat_wait_current`,
`pg_stat_wait_profile`, `pg_stat_wait_history` respectively. Best seen on the
examples.

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

We remove waits of classes 'Network' and 'Latch' because their waiting time
is usually several orders of magnitude longer than waits of other classes.
And listed above columns are not all columns that exist in the view:

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

Parameters `p1`-`p5` are text fields. For example, for heavy-weight locks they
give approximately same information that you can see in `pg_locks` view and for
disk I/O waits you can understand from which DB, relation and block we were
waiting while reading.

####pg_stat_wait_profile

For example, you can see how much time DB spent in each class of waits:

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

Or which LWLocks are the hottest in the system:

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

These two examples show that waiting time does not always correlate with wait
events count. That's why sampling without accounting waiting time can give
not right the whole picture.

####pg_stat_wait_history

This view allows to see what a particular process was waiting for in the past.
Storage depth and sampling interval can be configured as shown above.

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

####Session tracing

All described above views are designed to be always turned on, their
performance overhead is minimal. But there are cases when sampling once in
`pg_stat_wait.history_period` is not enough and you need to see all waits of
a particular process. In that case you should use functions for tracing,
for example:

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

A simple text file would be created where there would be two lines for each
wait event, for example:

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

###Instead of conclusion

Wait interface is the long-awaited feature in PostgreSQL which allows
significantly improve the understanding of what is happening inside the
database. Right now this functionality is kicked into core PostgreSQL
so that starting from 9.6 you would not need to recompile postgres.

Just in case, shortly before Ildus
[submitted](http://www.postgresql.org/message-id/559D4729.9080704@postgrespro.ru)
his implementation on pgsql-hackers@ Robert Haas
[proposed](http://www.postgresql.org/message-id/CA+TgmoYd3GTz2_mJfUHF+RPe-bCy75ytJeKVv9x-o+SonCGApw@mail.gmail.com)
the same idea and lots of people supported this idea. To become it true
a couple of preparatory patches have already been commited, for example
[Refactoring of LWLock tranches](http://www.postgresql.org/message-id/3F71DA37-A17B-4961-9908-016E6323E612@postgrespro.ru).

I really hope that it will become part of PostgreSQL in 9.6.
