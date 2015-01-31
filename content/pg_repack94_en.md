Title: PostgreSQL 9.4 and pg_repack
Date: 2015-01-31 20:00
Category: PostgreSQL
Tags: PostgreSQL, pg_repack, sources
Lang: en
Slug: pg_repack94

We have workflows with storing cooling UGC-data in DB. The older the data is,
the less likely it is asked. We partition tables with such data by date and eventually
move data from SSD-disks to SATA. It gives us very good hardware savings.
PostgreSQL has built-in support for tablespaces, that could be stored on different
devices, and has built-in command `ALTER TABLE foo SET TABLESPACE bar` which can
solve our initial problem. But this command has one big disadvantage - during
moving to another tablespace the table is exclusively locked so you can not
write or even read it.

Fortunately, there is a great tool called [pg_repack](http://reorg.github.io/pg_repack/)
which has been created to solve problems like the above. We successfully use it
with PostgreSQL 9.3 but 9.4 has been release in December and we have started
thinking about an upgrade.

There is [an open issue](https://github.com/reorg/pg_repack/issues/16) on github
about 9.4 support but nobody spent time on it. Since I was most interested in it
I did it myself. The result was this [pull request](https://github.com/reorg/pg_repack/pull/34).

It successfully passes regression-tests on 9.3 and 9.4 and definitely moves
a table with all indexes from one tablespace to another. But actually this patch
is not true - it does not support multiple TOAST-indexes which can happen
in the future. I hope, maintainers will find time to fix the problem right way.

But indeed the main achievement is not the patch but valuable experience:

* exploring `pg_catalog` structure a bit,
* debugging changes with GDB (by the way,
[a good presentation](http://www.pgcon.org/2014/schedule/attachments/321_pgcon2014-coredump.pdf)
on this topic)
* understanding PostgreSQL regression-tests.
