Title: Checking backups consistency
Date: 2015-06-06 20:00
Category: PostgreSQL
Tags: PostgreSQL, barman, backup, monitoring
Lang: en
Slug: barman-backups-check

Once upon a time as a result of two human errors while deploying new code on
our databases we did `DROP SCHEMA data CASCADE;` on all shards of one of our
clusters with more than 3 TB of data. It added us gray hair, allowed us to
check our PITR skills in production and made us to treat backups differently.

That story had happy end. The incident occured in the end of the working day
when workload was already descreasing and by morning we restored everything
from backups to the needed point of time. We have always been doing backups
and have always been monitoring the fact they are done. But we threw checking of
the ability to restore from them when we migrated to
[barman](http://www.pgbarman.org) because of high cost.

Recovery of one shard took more time than others because we could not restore
from last backup and we had to restore from second last (we do backups every
night). For that reason after fuckup we decided to get back checking of backups
consistency. As a result there are a couple of scripts which could be seen
[here](https://github.com/man-brain/misc/tree/master/backups_checking). One of
them (`check_backup_consistency.py`) sequentially deploys last backup of each
cluster, starts PostgreSQL with `recovery_target = 'immediate'` and waits for
reaching consistent state.

The second one (`check_xlogs.sh`) checks that backup server contains all needed
WALs (from the first WAL of first backup to the last archived WAL). Generally,
archiver guarantees the sequence in archiving WALs and if you configure
`archive_command` the right way you should not have problems with that. But we
had situations when free space on partition with `pg_xlog` ended and we changed
`archive_command` to move WALs locally. The first deploy would return
`archive_command` back but locally copied WALs could be forgotten.

We run these checks with cron and monitoring scripts look at status-files
created in `/tmp`. We start doing backups at 2 a.m. and the last one ends
around 6 a.m. (thanks to incremental backups in barman 1.4). And in the middle
of the day (around 2-3 p.m.) we already know if our backups are consistent and
if we can do `DROP SCHEMA` again :)

Perhaps, someone would find this scripts useful. Feel free to ask questions.
