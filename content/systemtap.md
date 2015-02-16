Title: PostgreSQL и SystemTap
Date: 2014-12-08 21:00
Category: PostgreSQL
Tags: PostgreSQL, SystemTap, debugging, sources
Lang: ru
Slug: postgresql-and-systemtap

####Пролог

Однажды мы стали наблюдать странные проблемы с производительностью
PostgreSQL 9.4 на пишущей нагрузке с большим shared_buffers. Сама проблема
хорошо описана [тут](http://www.postgresql.org/message-id/0DDFB621-7282-4A2B-8879-A47F7CECBCE4@simply.name),
но она не относится к теме поста. Поскольку PostgreSQL не имеет аналога
интерфейса ожиданий Oracle, мы написали пару простых SystemTap скриптов для
локализации проблемы. Ниже немного деталей.

####Подготовка

Для начала нужно поставить необходимые пакеты. Строго говоря, далеко не все
из нижеперечисленных пакетов нужны, но совершенно точно, что их достаточно:

    :::BashSessionLexer
    root@xdb01d ~ # rpm -qa | grep systemtap
    systemtap-client-2.3-4.el6_5.x86_64
    systemtap-devel-2.3-4.el6_5.x86_64
    systemtap-server-2.3-4.el6_5.x86_64
    systemtap-runtime-2.3-4.el6_5.x86_64
    root@xdb01d ~ # rpm -qa | grep -E 'kernel.*2.6.32-504'
    kernel-debuginfo-2.6.32-504.el6.x86_64
    kernel-firmware-2.6.32-504.el6.x86_64
    kernel-debuginfo-common-x86_64-2.6.32-504.el6.x86_64
    kernel-headers-2.6.32-504.el6.x86_64
    kernel-2.6.32-504.el6.x86_64
    kernel-devel-2.6.32-504.el6.x86_64
    root@xdb01d ~ #

Следующее, что необходимо сделать, - это пересобрать PostgreSQL с опцией
`--enable-dtrace`, переданной `configure`-скрипту. Поскольку мы используем
RHEL, я поправил spec-файл следующим образом:

    :::DiffLexer
    $ diff postgresql-9.4.spec.orig postgresql-9.4.spec
    323a324,325
    >   --enable-dtrace \
    >   --enable-debug \

Вообще-то компиляция с `--enable-dtrace` необходима только для использования
предопределённых в коде PostgreSQL маркеров. Все они описаны в
[документации](http://www.postgresql.org/docs/current/static/dynamic-trace.html#DTRACE-PROBE-POINT-TABLE).
Именно поэтому аналог интерфейса ожиданий oracle в PostgreSQL когда-нибудь
должен быть сделан.

####Первый stap
Допустим, у нас есть всё, чтобы начать, что дальше? Первый шаг на самом деле
очень непростой. Я бы порекомендовал начать со следующего:

  * [SystemTap Beginners Guide](https://access.redhat.com/documentation/en-US/Red_Hat_Enterprise_Linux/6/html/SystemTap_Beginners_Guide/)
  от Red Hat. И в первую очередь с
  [параграфа про проверку работы SystemTap](https://access.redhat.com/documentation/en-US/Red_Hat_Enterprise_Linux/6/html/SystemTap_Beginners_Guide/using-systemtap.html#testing).
  * [PostgreSQL with SystemTap](http://blog.endpoint.com/2009/05/postgresql-with-systemtap.html) от Joshua Tolley.
  * [Немного примеров и даже видео](https://sourceware.org/systemtap/wiki/PostgresqlMarkers) на SystemTap wiki.

Для начала можно просто скопировать и запустить примеры выше, а затем вносить
в них небольшие изменения, которые вам необходимы. Мой первый stap ниже, он
просто выводит начало и конец всех этапов checkpoint'а (время и pid). Он был
мне необходим для сопоставления всплесков потребления CPU во время
checkpoint'ов с происходящими событиями.

    :::CLexer
    probe process("/usr/pgsql-9.4/bin/postgres").mark("checkpoint__start")
    { printf ("[%s] Checkpoint started by pid %d\n", ctime(gettimeofday_s()), pid()) }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("checkpoint__done")
    {
        printf ("[%s] Checkpoint done by pid %d\n", ctime(gettimeofday_s()), pid())
        exit()
    }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("clog__checkpoint__start")
    { printf ("[%s] Clog checkpoint started by pid %d\n", ctime(gettimeofday_s()), pid()) }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("clog__checkpoint__done")
    { printf ("[%s] Clog checkpoint done by pid %d\n", ctime(gettimeofday_s()), pid()) }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("subtrans__checkpoint__start")
    { printf ("[%s] Subtrans checkpoint started by pid %d\n", ctime(gettimeofday_s()), pid()) }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("subtrans__checkpoint__done")
    { printf ("[%s] Subtrans checkpoint done by pid %d\n", ctime(gettimeofday_s()), pid()) }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("multixact__checkpoint__start")
    { printf ("[%s] Multixact checkpoint started by pid %d\n", ctime(gettimeofday_s()), pid()) }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("multixact__checkpoint__done")
    { printf ("[%s] Multixact checkpoint done by pid %d\n", ctime(gettimeofday_s()), pid()) }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("buffer__checkpoint__start")
    { printf ("[%s] Buffer checkpoint started by pid %d\n", ctime(gettimeofday_s()), pid()) }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("buffer__sync__start")
    { printf ("[%s] Buffer sync started by pid %d\n", ctime(gettimeofday_s()), pid()) }

    #probe process("/usr/pgsql-9.4/bin/postgres").mark("buffer__sync__written")
    #{ printf ("[%s] Buffer %d sync written by pid %d\n", ctime(gettimeofday_s()), $arg1, pid()) }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("buffer__sync__done")
    { printf ("[%s] Buffer sync done by pid %d\n", ctime(gettimeofday_s()), pid()) }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("buffer__checkpoint__sync__start")
    { printf ("[%s] Buffer checkpoint sync started by pid %d\n", ctime(gettimeofday_s()), pid()) }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("buffer__checkpoint__done")
    { printf ("[%s] Buffer checkpoint sync done by pid %d\n", ctime(gettimeofday_s()), pid()) }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("twophase__checkpoint__start")
    { printf ("[%s] Twophase checkpoint started by pid %d\n", ctime(gettimeofday_s()), pid()) }

    probe process("/usr/pgsql-9.4/bin/postgres").mark("twophase__checkpoint__done")
    { printf ("[%s] Twophase checkpoint done by pid %d\n", ctime(gettimeofday_s()), pid()) }

Дальше возникла необходимость отследить время, в течение которого держалась
блокировка на расширение отношения. Я это сделал так:

    :::CLexer
    global count, abyrvalg, timings, sec_timings

    probe process("/usr/pgsql-9.4/bin/postgres").function("LockRelationForExtension")
    {
        abyrvalg[$relation, tid()] = gettimeofday_ms()
        count++
    }

    probe process("/usr/pgsql-9.4/bin/postgres").function("UnlockRelationForExtension")
    {
        p = tid(); t = gettimeofday_ms()
        if ( [$relation,p] in abyrvalg) {
            tmp = t - abyrvalg[$relation,p]
            timings <<< tmp
            sec_timings[gettimeofday_s()] <<< tmp
            delete abyrvalg[$relation,p]
        }
    #   if (tmp >1000)
    #       printf ("[%s] Relation %d for extension has been locked by pid %d for %d ms\n", ctime(gettimeofday_s()), $relation->rd_id, pid(), tmp)
    }


    probe timer.s(1)
    {
        tmp = gettimeofday_s()-1
        if (tmp in sec_timings) {
            printf("[%s] Min: %d ms; Max: %d ms; Avg: %d ms\n", ctime(tmp), @min(sec_timings[tmp]), @max(sec_timings[tmp]), @avg(sec_timings[tmp]))
            delete sec_timings[tmp]
        }
    }

    probe end
    {
        printf("\nLockRelationForExtension has been called %d times\n", count)
        printf("Min: %d ms\nMax: %d ms\nAvg: %d ms\n", @min(timings), @max(timings), @avg(timings))
    }

Строго говоря, я добавил эту часть в первый stap и запустил всё вместе. Вывод
команды `stap -v` был следующий (много строчек пропущено с `<...>`):

    :::TextLexer
    Pass 1: parsed user script and 96 library script(s) using 198148virt/26440res/3120shr/23744data kb, in 160usr/10sys/165real ms.
    Pass 2: analyzed script: 25 probe(s), 8 function(s), 3 embed(s), 4 global(s) using 231456virt/44380res/12740shr/31976data kb, in 90usr/60sys/163real ms.
    Pass 3: using cached /root/.systemtap/cache/54/stap_5407ff18f4496fac55552cb675f64223_13156.c
    Pass 4: using cached /root/.systemtap/cache/54/stap_5407ff18f4496fac55552cb675f64223_13156.ko
    Pass 5: starting run.
    [Thu Oct 23 13:58:03 2014] Min: 0 ms; Max: 1 ms; Avg: 0 ms
    [Thu Oct 23 13:58:04 2014] Min: 0 ms; Max: 1 ms; Avg: 0 ms
    <...>
    [Thu Oct 23 13:58:36 2014] Checkpoint started by pid 8463
    [Thu Oct 23 13:58:36 2014] Clog checkpoint started by pid 8463
    [Thu Oct 23 13:58:36 2014] Clog checkpoint done by pid 8463
    [Thu Oct 23 13:58:36 2014] Subtrans checkpoint started by pid 8463
    [Thu Oct 23 13:58:36 2014] Subtrans checkpoint done by pid 8463
    [Thu Oct 23 13:58:36 2014] Multixact checkpoint started by pid 8463
    [Thu Oct 23 13:58:36 2014] Multixact checkpoint done by pid 8463
    [Thu Oct 23 13:58:36 2014] Buffer checkpoint started by pid 8463
    [Thu Oct 23 13:58:36 2014] Buffer sync started by pid 8463
    [Thu Oct 23 13:58:36 2014] Min: 0 ms; Max: 1 ms; Avg: 0 ms
    [Thu Oct 23 13:58:37 2014] Min: 0 ms; Max: 1 ms; Avg: 0 ms
    <...>
    [Thu Oct 23 13:58:42 2014] Min: 0 ms; Max: 438 ms; Avg: 82 ms
    [Thu Oct 23 13:58:43 2014] Min: 0 ms; Max: 657 ms; Avg: 293 ms
    [Thu Oct 23 13:58:44 2014] Min: 647 ms; Max: 681 ms; Avg: 665 ms
    <...>
    [Thu Oct 23 13:58:52 2014] Min: 1738 ms; Max: 1844 ms; Avg: 1772 ms
    <...>
    [Thu Oct 23 13:59:25 2014] Min: 3239 ms; Max: 3239 ms; Avg: 3239 ms
    [Thu Oct 23 13:59:26 2014] Min: 0 ms; Max: 4518 ms; Avg: 3034 ms
    [Thu Oct 23 13:59:28 2014] Min: 0 ms; Max: 2078 ms; Avg: 428 ms
    [Thu Oct 23 13:59:29 2014] Min: 0 ms; Max: 136 ms; Avg: 68 ms
    [Thu Oct 23 13:59:33 2014] Min: 4880 ms; Max: 5007 ms; Avg: 4943 ms
    [Thu Oct 23 13:59:34 2014] Min: 0 ms; Max: 5206 ms; Avg: 3654 ms
    <...>
    [Thu Oct 23 14:00:20 2014] Min: 0 ms; Max: 3346 ms; Avg: 2497 ms
    [Thu Oct 23 14:00:24 2014] Min: 7342 ms; Max: 7342 ms; Avg: 7342 ms
    [Thu Oct 23 14:00:25 2014] Min: 0 ms; Max: 8382 ms; Avg: 3949 ms
    <...>
    [Thu Oct 23 14:02:02 2014] Min: 1499 ms; Max: 1646 ms; Avg: 1587 ms
    [Thu Oct 23 14:02:03 2014] Min: 0 ms; Max: 4665 ms; Avg: 3021 ms
    [Thu Oct 23 14:02:04 2014] Min: 1201 ms; Max: 6449 ms; Avg: 3876 ms
    [Thu Oct 23 14:02:05 2014] Min: 0 ms; Max: 7268 ms; Avg: 3291 ms
    [Thu Oct 23 14:02:07 2014] Min: 1899 ms; Max: 6311 ms; Avg: 4735 ms
    [Thu Oct 23 14:02:08 2014] Min: 2791 ms; Max: 7107 ms; Avg: 6017 ms
    [Thu Oct 23 14:02:09 2014] Min: 0 ms; Max: 8343 ms; Avg: 2551 ms
    [Thu Oct 23 14:02:22 2014] Min: 9543 ms; Max: 12365 ms; Avg: 10954 ms
    [Thu Oct 23 14:02:23 2014] Min: 0 ms; Max: 22017 ms; Avg: 8741 ms
    [Thu Oct 23 14:02:25 2014] Min: 0 ms; Max: 23489 ms; Avg: 11113 ms
    <...>
    [Thu Oct 23 14:06:05 2014] Buffer sync done by pid 8463
    [Thu Oct 23 14:06:05 2014] Buffer checkpoint sync started by pid 8463
    [Thu Oct 23 14:06:04 2014] Min: 0 ms; Max: 128 ms; Avg: 8 ms
    [Thu Oct 23 14:06:05 2014] Min: 0 ms; Max: 98 ms; Avg: 5 ms
    [Thu Oct 23 14:06:06 2014] Min: 0 ms; Max: 1 ms; Avg: 0 ms
    [Thu Oct 23 14:06:07 2014] Min: 0 ms; Max: 1 ms; Avg: 0 ms
    <...>
    [Thu Oct 23 14:06:48 2014] Min: 0 ms; Max: 1 ms; Avg: 0 ms
    [Thu Oct 23 14:06:49 2014] Min: 0 ms; Max: 0 ms; Avg: 0 ms
    [Thu Oct 23 14:06:50 2014] Buffer checkpoint sync done by pid 8463
    [Thu Oct 23 14:06:51 2014] Checkpoint done by pid 8463

    LockRelationForExtension has been called 16075 times
    Min: 0 ms
    Max: 23489 ms
    Avg: 287 ms
    WARNING: Number of errors: 0, skipped probes: 13046
    Pass 5: run completed in 20usr/100sys/527749real ms.

Из вывода этого скрипты видно, что проблемы случаются во время сбрасывания
буфферов из shared_buffers на диск. И есть моменты, когда много времени
проводится под ExclusiveLock на расширение отношения между [этой](http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/access/heap/hio.c;h=631af759d78fef6c9e909b50fc48ef37b32cbae9;hb=refs/heads/REL9_4_STABLE#l431)
и [этой](http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/access/heap/hio.c;h=631af759d78fef6c9e909b50fc48ef37b32cbae9;hb=refs/heads/REL9_4_STABLE#l460)
строчками кода в [функции RelationGetBufferForTuple](http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/access/heap/hio.c;h=631af759d78fef6c9e909b50fc48ef37b32cbae9;hb=refs/heads/REL9_4_STABLE#l158).

####Второй stap
Вторым я написал следующий stap:

    :::CLexer
    global count, count_with_clock, passes, sec_passes

    probe process("/usr/pgsql-9.4/bin/postgres").function("StrategyGetBuffer").return
    {
        tmp = $StrategyControl->completePasses
        count++
        if (tmp>0) {
            count_with_clock++
            passes <<< tmp
            sec_passes[gettimeofday_s()] <<< tmp
            printf("[%s] %d made %d iterations to find least used buffer\n", ctime(gettimeofday_s()), pid(), tmp)
        }
    }

    probe timer.s(1)
    {
        tmp = gettimeofday_s()-1
        if (tmp in sec_passes) {
            printf("[%s] Min: %d ms; Max: %d ms; Avg: %d ms\n", ctime(tmp), @min(sec_passes[tmp]), @max(sec_passes[tmp]), @avg(sec_passes[tmp]))
            delete sec_passes[tmp]
        }
    }

    probe end
    {
        printf("\nStrategyGetBuffer has been called %d times, %d times with clock sweep\n", count, count_with_clock)
        printf("Min: %d ms\nMax: %d ms\nAvg: %d ms\n", @min(passes), @max(passes), @avg(passes))
    }

Обратите внимание, что PostgreSQL не должен быть собран с опцией `--enable-dtrace`
для работы этого скрипта (но `--enable-debug` обязателен). И этот stap получает данные из
[структуры StrategyControl](http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/storage/buffer/freelist.c;h=4befab0e1ad05f05e950d3dea6f0951d94b4ef4d;hb=refs/heads/REL9_4_STABLE#l22)
на выходе из [функции StrategyGetBuffer](http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/storage/buffer/freelist.c;h=4befab0e1ad05f05e950d3dea6f0951d94b4ef4d;hb=refs/heads/REL9_4_STABLE#l94),
чтобы увидеть, сколько страничек в shared_buffers было пройдено до того, как
был найден буффер для вытеснения.

Этот stap показал, что ClockSweep может пройти огромную часть shared_buffers
внутри функции `StrategyGetBuffer`, держа эксклюзивную блокировку на расширение
отношения и [BufFreelistLock LWLock](http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/storage/buffer/freelist.c;h=4befab0e1ad05f05e950d3dea6f0951d94b4ef4d;hb=refs/heads/REL9_4_STABLE#l134).

Стало быть, проблема в базовой функциональности PostgreSQL и не проблема не
может быть решена без правок в коде :( Но к стачстью, есть пару патчей, которые
уже закоммичены в 9.5:

  1. [Change locking regimen around buffer replacement](http://git.postgresql.org/gitweb/?p=postgresql.git;a=commit;h=5d7962c6) by Robert Haas,
  2. [Lockless StrategyGetBuffer clock sweep hot path](http://git.postgresql.org/gitweb/?p=postgresql.git;a=commit;h=d72731a7) by Andres Freund.

Я обязательно попробую PostgreSQL, собранные из мастера, на том же профиле
нагрузки, чтобы проверить, стало ли лучше. Следите за новостями.
