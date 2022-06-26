Title: PostgreSQL replication lag in seconds
Date: 2015-06-14 16:00
Category: PostgreSQL
Tags: PostgreSQL, bgworker, sources, replication, monitoring
Lang: en
Slug: postgresql-replication-monitoring

Our typical PostgreSQL shard consists of master and two replics. We monitor that
master has as much as needed number of replics (we fire WARN event in monitoring
if there is only one alive replica and CRIT if there are no alive replics). And
we monitor replication lag, `replay_location` of the replica. All this is done
with a couple of easy queries to `pg_stat_replication`.

This method has two great disadvantages:

  * Most of the data from `pg_stat_replication` could be taken only by users
with `SUPERUSER` option. Giving such option to monitoring user is not really
good idea.
  * We have different threasholds for replication lag because 10&nbsp;MB of
replication lag on cluster with 1&nbsp;MB/s of writing load and on cluster with
100&nbsp;MB/s are not the same.

To solve both problems we have written
[bgworker](http://www.postgresql.org/docs/current/static/bgworker.html),
sources for which could be taken [here](https://github.com/man-brain/repl_mon).

The princile of operation is really simple -- bgworker once in a while (which
could be configured with an accuracy of 1 ms) writes in some table (`repl_mon`
by default, but it can be configured) next things:

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

Query for getting data could be seen
[here](https://github.com/man-brain/repl_mon/blob/8e14fb52/repl_mon.c#L127-L131).

Number of alive replics could be taken directly from this table on master. And
on replics values of fields `ts` and `location` could be compared with current
time and `pg_last_xlog_replay_location()`:

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

Important thing here is that it does not require superuser rights.

For this thing to work you need to execute `make` and `sudo make install` in the
source directory. And then add `repl_mon` to `shared_preload_libraries` and
restart PostgreSQL.

I hope, someone will find it useful.

P.S. A special thank is to say to Michael Paquier, who supports
[pg_plugins](https://github.com/michaelpq/pg_plugins) -- a set of simple
templates for PostgreSQL extensions. Most of the code I copied from there.
