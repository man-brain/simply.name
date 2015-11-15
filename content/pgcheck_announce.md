Title: Pgcheck
Date: 2014-10-21 15:20
Category: PostgreSQL
Tags: PostgreSQL, plproxy, pgcheck
Lang: ru
Slug: pgcheck

Месяц назад я [рассказывал]({filename}/yameetup_video2015.html) о первых шагах Яндекс.Почты с PostgreSQL и, в частности, о наших инструментах обеспечения отказоустойчивости. Один из них pgcheck -- средство мониторинга конечных баз с [PL/Proxy](http://plproxy.projects.pgfoundry.org/doc/tutorial.html)-машин и изменения выдачи функции `plproxy.get_cluster_partitions` для распределения нагрузки на базы.

Больше информации можно найти на [github](https://github.com/yandex/pgcheck). Ура!
