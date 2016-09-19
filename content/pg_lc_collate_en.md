Title: One more time about collation in PostgreSQL
Date: 2016-09-18 23:00
Category: PostgreSQL
Tags: PostgreSQL, i18n, initdb, lc_collate
Lang: en
Slug: pg-lc-collate

It's been a long time since my last post. It's time to write something useful :)

When people start working with PostgreSQL they sometimes make mistakes which are
really difficult to fix later. For example during `initdb` of your first DB you
don't really understand whether you need checksums for data or not. Especially
that by default they are turned off and documentation says that they "may incur
a noticeable performance penalty".

And when you already have several hundred databases with a few hundred terabytes
of data on different hardware or (even worse) in different virtualization
systems, you do understand that you are ready to pay some performance for
identification of silent data corruption. But the problem is that you can't
easily turn checksums on. It is one of the things that is adjusted only once
while invoking `initdb` command. In the bright future we hope for logical
replication but until that moment the only way is `pg_dump`, `initdb`,
`pg_restore` that is with downtime.

And if checksums may be not useful for you (e.g. you have perfect hardware and
OS without bugs), `lc_collate` is important for everyone. And now I will prove
it.

### Sort order

Suppose you have installed PostgreSQL from packages or built it from sources and
initialized DB by yourself. Most probably, in the modern world of victorious
UTF-8 you would see something like that:

    :::BashSessionLexer
    d0uble ~ $ psql -l
                                   List of databases
       Name    | Owner  | Encoding |   Collate   |    Ctype    | Access privileges
    -----------+--------+----------+-------------+-------------+-------------------
     postgres  | d0uble | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
     template0 | d0uble | UTF8     | en_US.UTF-8 | en_US.UTF-8 | =c/d0uble        +
               |        |          |             |             | d0uble=CTc/d0uble
     template1 | d0uble | UTF8     | en_US.UTF-8 | en_US.UTF-8 | =c/d0uble        +
               |        |          |             |             | d0uble=CTc/d0uble
    (3 rows)

    d0uble ~ $

If you don't specify explicitly, `initdb` will take settings for columns 3-5
from operating system. And most likely you would think that everything is fine
if you see `UTF-8` there. However, in some cases you may be surprised. Look at
the following query result on linux box:

    :::PostgresConsoleLexer
    linux> SELECT name FROM unnest(ARRAY[
        'MYNAME', ' my_name', 'my-image.jpg', 'my-third-image.jpg'
    ]) name ORDER BY name;
            name
    --------------------
     my-image.jpg
      my_name
     MYNAME
     my-third-image.jpg
    (4 rows)

    linux>

Such sort order seems really weird. And this despite the fact that the client
connected to DB with quite adequate settings:

    :::PostgresConsoleLexer
    linux> SELECT name, setting FROM pg_settings WHERE category ~ 'Locale';
                name            |      setting
    ----------------------------+--------------------
     client_encoding            | UTF8
     DateStyle                  | ISO, MDY
     default_text_search_config | pg_catalog.english
     extra_float_digits         | 0
     IntervalStyle              | postgres
     lc_collate                 | en_US.UTF-8
     lc_ctype                   | en_US.UTF-8
     lc_messages                | en_US.UTF-8
     lc_monetary                | en_US.UTF-8
     lc_numeric                 | en_US.UTF-8
     lc_time                    | en_US.UTF-8
     server_encoding            | UTF8
     TimeZone                   | Europe/Moscow
     timezone_abbreviations     | Default
    (14 rows)

    linux>

The result doesn't depend on distro -- at least it is the same on RHEL 6 and
Ubuntu 14.04. Even more strange is the fact that the same query with the same
server and client settings on Mac OS X gives another result:

    :::PostgresConsoleLexer
    macos> SELECT name FROM unnest(ARRAY[
        'MYNAME', ' my_name', 'my-image.jpg', 'my-third-image.jpg'
    ]) name ORDER BY name;
            name
    --------------------
      my_name
     MYNAME
     my-image.jpg
     my-third-image.jpg
    (4 rows)

    macos>

At first glance, linux is seriously broken in this place. But the problem is
that the result which depends on OS is very bad result. Fortunately, we discoved
it during testing -- tests on developer's macbook were fine, but on testing
linux-server not.

The reason is that PostgreSQL takes collation from OS and surprisingly UTF-8 may
be different ¯\\\_(ツ)_/¯ While searching you could find a lot of threads about
different sort order in Linux and Mac OS X (
[1](http://stackoverflow.com/questions/16328592),
[2](https://www.postgresql.org/message-id/flat/23053.1337036410%40sss.pgh.pa.us#23053.1337036410@sss.pgh.pa.us),
[3](http://stackoverflow.com/questions/27395317),
[4](https://www.postgresql.org/message-id/4B4E845F.80906@postnewspapers.com.au),
[5](http://dba.stackexchange.com/questions/106964),
[6](http://dba.stackexchange.com/questions/94887)).

Opinions are different about the question "who is to blame?" but we can
confidently say that Mac OS X exactly doesn't account all regional specifics. It
can be seen by links above or i.e. on the following example for Russian
language:

    :::PostgresConsoleLexer
    macos> SELECT name FROM unnest(ARRAY[
        'а', 'д', 'е', 'ё', 'ж', 'я'
    ]) name ORDER BY name;
     name
    ------
     а
     д
     е
     ж
     я
     ё
    (6 rows)

    macos>

Meanwhile Linux handles this request reasonably from my point of view. And even
previous query result may be explained -- linux ignores whitespaces and symbols
`-`, `_` while sorting. I.e. thinking a little the broken OS is Mac OS X.

After all we moved our tests to docker to be independant from OS characteristics
but there are other ways to get the same results in different operating systems.
The easiest one is to use `LC_COLLATE = C` because it is the only collation
which is distributed with PostgreSQL and doesn't depend on OS (see
[documentation](https://www.postgresql.org/docs/current/static/charset.html)).

    :::PostgresConsoleLexer
    linux> SELECT name FROM unnest(ARRAY[
        'MYNAME', ' my_name', 'my-image.jpg', 'my-third-image.jpg'
    ]) name ORDER BY name COLLATE "C";
            name
    --------------------
      my_name
     MYNAME
     my-image.jpg
     my-third-image.jpg
    (4 rows)

    linux>

You can see that is such case results are the same for both OS. But it is also
easy to see that they are the same as in Mac OS X so also with problems for
multibyte encodings, e.g.:

    :::PostgresConsoleLexer
    linux> SELECT name FROM unnest(ARRAY[
        'а', 'д', 'е', 'ё', 'ж', 'я'
    ]) name ORDER BY name COLLATE "C";
     name
    ------
     а
     д
     е
     ж
     я
     ё
    (6 rows)

    linux>

Not worth while to think that sort result with `LC_COLLATE=en_US.UTF-8` in Mac
OS X always would be the same as with `LC_COLLATE=C` in any OS. You can
certainly be sure only in the fact that collation `C` guarantees the same result
everywhere because it is provided with PostgreSQL and doesn't depend on OS.

Meanwhile from a purely narrow-minded point of ordinary user view it seems odd
not to account whitespaces and other non-alphanumeric characters while sorting,
but these rules have been invented, standardized and not for me to change them.
However, in the original problem these rules were invalid so we moved to `C`
collation.

### Prefix queries

The fact that postgres relies on glibc in sorting has some more nuances which is
to say some more. For example let's create the following table with two text
fields and insert into it a million of random rows:

    :::PostgresConsoleLexer
    linux> CREATE TABLE sort_test (
        a text,
        b text COLLATE "C");
    CREATE TABLE
    linux> INSERT INTO sort_test SELECT md5(n::text), md5(n::text)
        FROM generate_series(1, 1000000) n;
    INSERT 0 1000000
    linux> CREATE INDEX ON sort_test USING btree (a);
    CREATE INDEX
    linux> CREATE INDEX ON sort_test USING btree (b);
    CREATE INDEX
    linux> ANALYZE sort_test;
    ANALYZE
    linux> SELECT * FROM sort_test LIMIT 2;
                    a                 |                b
    ----------------------------------+----------------------------------
     c4ca4238a0b923820dcc509a6f75849b | c4ca4238a0b923820dcc509a6f75849b
     c81e728d9d4c2f636f067f89cc14862c | c81e728d9d4c2f636f067f89cc14862c
    (2 rows)

    linux>

First field is created with default collation (`en_US.UTF-8` in my example)
while the second one is with collation `C`, the values are the same in both
columns. Let's see plans for queries by prefix of each field:

    :::PostgresConsoleLexer
    linux> explain SELECT * FROM sort_test WHERE a LIKE 'c4ca4238a0%';
                               QUERY PLAN
    ----------------------------------------------------------------
     Seq Scan on sort_test  (cost=0.00..24846.00 rows=100 width=66)
       Filter: (a ~~ 'c4ca4238a0%'::text)
    (2 rows)

    linux> explain SELECT * FROM sort_test WHERE b LIKE 'c4ca4238a0%';
                                         QUERY PLAN
    ------------------------------------------------------------------------------------
     Index Scan using sort_test_b_idx on sort_test  (cost=0.42..8.45 rows=100 width=66)
       Index Cond: ((b >= 'c4ca4238a0'::text) AND (b < 'c4ca4238a1'::text))
       Filter: (b ~~ 'c4ca4238a0%'::text)
    (3 rows)

    linux>

It's easy to see that PostgreSQL uses index only for seconf query. The reason
can be seen in EXPLAIN output (see `Index Cond`) -- in the second case
PostgreSQL knows the order of characters and converts index search condition
from `b LIKE 'c4ca4238a0%'` to `b >= 'c4ca4238a0' AND b < 'c4ca4238a1'` (and
just then postgres will filter received results by original condition) and
these two operations are well covered by B-Tree.

You can see that such query cost with collation `C` is approximately 2500 times
less.

### Abbreviated keys

One of really good optimizations which appeared in PostgreSQL 9.5 was so called
abbreviated keys. The best thing to read about it is [the
post](http://pgeoghegan.blogspot.ru/2015/01/abbreviated-keys-exploiting-locality-to.html)
of optimization's author, Peter Geoghegan. In short it greatly accelerated
sorting of text fields and creating indexes on them. Some examples may be seen
[here](https://www.depesz.com/2015/01/27/waiting-for-9-5-use-abbreviated-keys-for-faster-sorting-o
f-text-datums/).

Unfortunately, in 9.5.2 this optimization [was turned
off](https://git.postgresql.org/gitweb/?p=postgresql.git;a=commitdiff;h=3df9c374e279db37b0
0cd9c86219471d0cdaa97c) for all collations except `C`. The reason was glibc bug
(as we remember PostgreSQL relies on glibc for all collations except `C`) in
which result indexes could be inconsistent.

### Instead of a conclusion

In the original issue after all we started using `lc_collate = C`, because the
data may be in different languages and this collation seems to be the best
choice for that. Yes, it won't consider some corner cases in each language but
it would be good enough for all others.

Meanwhile it is really sad that there is no silver bullet and when all your data
is e.g. in Russian you have to choose between performance and correct sorting
order with accounting Russian language specifics.
