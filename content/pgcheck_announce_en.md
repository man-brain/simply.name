Title: Pgcheck
Date: 2014-10-21 15:20
Category: PostgreSQL
Tags: PostgreSQL, plproxy, pgcheck
Lang: en
Translation: True
Slug: pgcheck

A month ago I [spoke]({filename}/yameetup_video.html) about first steps in Yandex.Mail with PostgreSQL and particularly about our tools to provide fault tolerance. One of them is pgcheck - tool for monitoring backend databases from [PL/Proxy](http://plproxy.projects.pgfoundry.org/doc/tutorial.html) hosts and changing `plproxy.get_cluster_partitions` function output to for controlling load on databases.

More info could be found on [github](https://github.com/yandex/pgcheck) as pgcheck is open source now. Enjoy.
