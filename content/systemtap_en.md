Title: PostgreSQL and SystemTap
Date: 2014-12-08 21:00
Category: PostgreSQL
Tags: PostgreSQL, SystemTap, debugging, sources
Lang: en
Slug: postgresql-and-systemtap

####Preface

Once upon a time we started having strange performance issues with writing-only
load on PostgreSQL 9.4 with huge shared_buffers. The problem itself is well
described [here](http://www.postgresql.org/message-id/0DDFB621-7282-4A2B-8879-A47F7CECBCE4@simply.name)
but it is not the topic of the post. And since PostgreSQL does not have
something like Oracle wait events interface yet, we have written a couple of
simple SystemTap scripts to determine the problem. Below are some details.

####Preparing

First of all you need to install needed packages. Actually, not everything from
below listed is needed but it is just enough:

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

The next thing to do is to compile PostgreSQL with `--enable-dtrace` option
passed to `configure`-script. Since I am using RHEL I have fixed spec-file for that:

    :::DiffLexer
    $ diff postgresql-9.4.spec.orig postgresql-9.4.spec
    323a324,325
    >   --enable-dtrace \
    >   --enable-debug \

Actually, compiling with such symbols is neccessary for using predefined in
PostgreSQL source code markers. All of them are defined in the
[documentation](http://www.postgresql.org/docs/current/static/dynamic-trace.html#DTRACE-PROBE-POINT-TABLE).
Option `--enable-debug` is not needed for using systemtap at all - I have added
it for taking PostgreSQL backend stack traces with gdb. One more thing to say
is that recompiling PostgreSQL for deeper debugging is not really the thing to
be used in production-environment :( That's why IMHO analogue of oracle wait
interface in PostgreSQL should be done ever.

####First stap
Right, let's assume that we have everything needed to start, what next? The
first step is really very difficult. I could recommend a few things to look at:

  * [SystemTap Beginners Guide](https://access.redhat.com/documentation/en-US/Red_Hat_Enterprise_Linux/6/html/SystemTap_Beginners_Guide/) from Red Hat.
  And first of all [paragraph about testing SystemTap](https://access.redhat.com/documentation/en-US/Red_Hat_Enterprise_Linux/6/html/SystemTap_Beginners_Guide/using-systemtap.html#testing).
  * [PostgreSQL with SystemTap](http://blog.endpoint.com/2009/05/postgresql-with-systemtap.html) by Joshua Tolley.
  * [Some examples and even video](https://sourceware.org/systemtap/wiki/PostgresqlMarkers) on SystemTap wiki.

At first you could simply do copy-paste the examples above. And than do small
changes in them to get what you need. My first stap is below, it simply prints
all checkpoint events (time and pid). I needed it to map CPU spikes during
checkpointing with events happening at this time.

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

The next thing was to track spent time under locking the relation for extension.
I've done it in this way:

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

Actually I have added this part to the first stap and the output of running it
with `stap -v ` command was (lost of lines are skipped with `<...>`):

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

From the output of this stap you can see that problems occur while doing buffer
sync and there are situations when a lot of time is spent under holding
ExclusiveLock on extension of relation between
[this](http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/access/heap/hio.c;h=631af759d78fef6c9e909b50fc48ef37b32cbae9;hb=refs/heads/REL9_4_STABLE#l431)
and [this](http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/access/heap/hio.c;h=631af759d78fef6c9e909b50fc48ef37b32cbae9;hb=refs/heads/REL9_4_STABLE#l460)
lines of code in
[RelationGetBufferForTuple function](http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/access/heap/hio.c;h=631af759d78fef6c9e909b50fc48ef37b32cbae9;hb=refs/heads/REL9_4_STABLE#l158).

####Second stap
The next stap I had written was the following:

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

Note that PostgreSQL should not be built with `--enable-dtrace` option for this
stap to work. And this stap gets data from
[StrategyControl structure](http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/storage/buffer/freelist.c;h=4befab0e1ad05f05e950d3dea6f0951d94b4ef4d;hb=refs/heads/REL9_4_STABLE#l22) on exit from
[StrategyGetBuffer function](http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/storage/buffer/freelist.c;h=4befab0e1ad05f05e950d3dea6f0951d94b4ef4d;hb=refs/heads/REL9_4_STABLE#l94)
to see how many ClockSweep passes have been done through shared buffers to find
a buffer to be replaced.

This stap showed me that a huge part of shared_buffers pages could be gone by
ClockSweep inside StrategyGetBuffer while holding ExclusiveLock on extension
of relation and
[BufFreelistLock LWLock](http://git.postgresql.org/gitweb/?p=postgresql.git;a=blob;f=src/backend/storage/buffer/freelist.c;h=4befab0e1ad05f05e950d3dea6f0951d94b4ef4d;hb=refs/heads/REL9_4_STABLE#l134).

So this is the problem in core functionality of PostgreSQL and it can't be
fixed without patching the code :( But fortunatelly there are two patches
that have been already commited for 9.5:

  1. [Change locking regimen around buffer replacement](http://git.postgresql.org/gitweb/?p=postgresql.git;a=commit;h=5d7962c6) by Robert Haas,
  2. [Lockless StrategyGetBuffer clock sweep hot path](http://git.postgresql.org/gitweb/?p=postgresql.git;a=commit;h=d72731a7) by Andres Freund.

I will definitely try PostgreSQL built from master on the same worload to see
if that helped. Stay tuned.
