Title: Pgcheck and delayed replics
Date: 2014-12-23 21:00
Category: PostgreSQL
Tags: PostgreSQL, plproxy, pgcheck
Lang: en
Slug: pgcheck-and-delayed-replics

Two months ago we [announced]({filename}/pgcheck_announce_en.md) pgcheck - a tool for automatic load control on PostgreSQL databases using PL/Proxy. Today we have fixed all found issues about one new feature - pgcheck can now account replication delays and not to route queires on delayed replics.

Sources and some more info could be found on [github](https://github.com/yandex/pgcheck). Enjoy.
