Title: Upgrading PostgreSQL to 9.4
Date: 2015-03-31 18:00
Category: PostgreSQL
Tags: PostgreSQL, pg_upgrade, rsync
Lang: en
Slug: upgrading-postgres-to-9.4

####Preface
In 9.4 there is a logical decoding which would allow to upgrade from 9.4 to 9.5
quiet cheap (at least it
[shoud](https://wiki.postgresql.org/wiki/UDR_Online_Upgrade) be so). But right
now upgrading major version of PostgreSQL is painful. In most common case it
looks like that:

  1. Stop master and call `pg_upgrade`.
  2. Start master with new version.
  3. Make a full backup from upgraded master.
  4. Refill all the replicas from new backup.

We have databases with several terabytes of data, each shard of which consists
from three hosts - master and two replics. Most of the read-only queries are
served from replicas. And with some of such DBs we can survive death of only
one replica. So if both replics would die one master would not handle all the
writing and read-only load. And making a full backup of several terabytes and
refilling at least one replica from it is a good challenge.

####Ray of hope

When we were about to upgrade at night from saturday to sunday and suffer,
Bruce Momjian sent a
[patch](http://www.postgresql.org/message-id/20150219165755.GA18714@momjian.us)
to the documentation which allows to upgrade all replics without refilling them
from backup. The patch has been applied to master branch so in documentation
for 9.5 the required steps are already
[described](http://www.postgresql.org/docs/devel/static/pgupgrade.html).

The only disadvantage of such solution is that you need to stop all hosts of
the cluster while upgrading (so DB is not accessible even in read-only mode).
Such restriction is not very good for us so we have decided to do it a bit
different.

####Implementation

Because we have several dozens of DBs we decided to do an upgrade with a
script. It is very stupid and panics on any error so that everything else you
shoud make manually.

The script is closely depends on our infrastructure so I publish just some
pieces of it. Common sequence is quiet simple (install 9.4 packages on all
hosts, upgrade master, rsync replicas, start master):

    :::python
    def main(options, hosts, master):
        prefix = options.prefix
        bydlog("Installing packages on all hosts.")
        res = apply_state_on_host('%s*' % prefix, 'components.pg94.db.packages')
        if res != 0:
            return res
        upgrade_master(master, prefix, options)
        rsync_replicas(master, hosts, options)
        start_master(master, options)
        bydlog("Seems, that everything succeded. Unbeliavable!")

Such sequence extends time in read-only mode (master could be started after
upgrading the first replica), but it completely excludes the need to refill
any host from backup.

#####Upgrading master

Master upgrade seems to be the most intense stage:

    :::python
    def upgrade_master(master, prefix, options):
        if options.need_checksums:
            cmd = "sed -i /etc/init.d/postgresql-9.4 -e 's/initdb --pgdata/initdb -k --pgdata/'"
            run_or_exit(master, cmd)

        run_or_exit(master, '/etc/init.d/postgresql-9.4 initdb')
        run_or_exit(master, '/etc/init.d/pgbouncer stop')
        run_or_exit(master, '/etc/init.d/postgresql-9.3 stop')

        cmd = '/usr/pgsql-9.4/bin/pg_upgrade -b /usr/pgsql-9.3/bin/ -B /usr/pgsql-9.4/bin/ -d /var/lib/pgsql/9.3/data/ -D /var/lib/pgsql/9.4/data/ --check'
        res = cmd_run_on_host(master, cmd, runas='postgres')
        if res != 0:
            bydlog("Running 'pg_upgrade --check' on %s failed. Turning everything on back." % master)
            cmd_run_on_host(master, '/etc/init.d/postgresql-9.3 start')
            cmd_run_on_host(master, '/etc/init.d/pgbouncer start')
            sys.exit(0)

        cmd = '/usr/pgsql-9.4/bin/pg_upgrade -b /usr/pgsql-9.3/bin/ -B /usr/pgsql-9.4/bin/ -d /var/lib/pgsql/9.3/data/ -D /var/lib/pgsql/9.4/data/ --link'
        run_or_exit(master, cmd, runas='postgres')

        if options.preserve_history:
            cmd = 'rsync -av /var/lib/pgsql/9.3/data/pg_xlog/*.history /var/lib/pgsql/9.4/data/pg_xlog/'
            cmd_run_on_host(master, cmd)

        run_or_exit(master, 'mkdir -p /var/lib/pgsql/9.4/data/conf.d/', runas='postgres')
        res = apply_state_on_host(master, 'components.pg94.db.configs')
        if res != 0:
            bydlog("Could not install configs on %s. Exiting." % master)
            sys.exit(70)

        run_or_exit(master, 'iptables -A INPUT -p tcp -m tcp --dport 5432 -j REJECT && ip6tables -A INPUT -p tcp -m tcp --dport 5432 -j REJECT')

        run_or_exit(master, '/etc/init.d/postgresql-9.4 start')
        if options.need_stat:
            run_or_exit(master, '/usr/pgsql-9.4/bin/vacuumdb --all --analyze-only', runas='postgres')
        run_or_exit(master, '/etc/init.d/postgresql-9.4 stop')
        bydlog("Seems that master has been upgraded successfully. Unbelievable!")

At first we do `pg_upgrade --check` and if it fails everything is put back in
place. It is the only case where this happens. In case of any other error the
scripts falls.

Then our configuration files are installed and master closes from replics with
firewall because (surprisingly!) replics with 9.3 can apply changes from master
with 9.4. It would not have happy end though.

It is important that from stopping pgbouncer on master all queries are routed
to replics so the cluster is in read-only state.

#####Upgrading replics

Replics are upgraded sequentially:

    :::python
    def rsync_replicas(master, hosts, options):
        hosts.remove(master)
        for replica in hosts:
            rsync_one_replica(master, replica, options)
            time.sleep(5)

The function itself does not do anything except rsync:

    :::python
    def rsync_one_replica(master, replica, options):
        run_or_exit(replica, '/etc/init.d/pgbouncer stop')
        run_or_exit(replica, '/etc/init.d/postgresql-9.3 stop')

        cmd = 'ssh -A root@%s "cd /var/lib/pgsql && rsync --relative --archive --hard-links --size-only 9.3/data 9.4/data root@%s:/var/lib/pgsql/"' % (master, replica)
        bydlog(cmd)
        res = subprocess.call(cmd, shell=True, stdout=sys.stdout, stderr=sys.stderr)
        if res != 0:
            bydlog("Could not rsync changes to %s. Exiting." % replica)
            sys.exit(110)

        if options.tablespace:
            cmd = 'ssh -A root@%s "cd /var/lib/pgsql/9.3/slow && rsync --relative --archive --hard-links --size-only PG_9.3_201306121 PG_9.4_201409291 root@%s:/var/lib/pgsql/9.3/slow/"' % (master, replica)
            bydlog(cmd)
            res = subprocess.call(cmd, shell=True, stdout=sys.stdout, stderr=sys.stderr)
            if res != 0:
                bydlog("Could not rsync tablespace to %s. Exiting." % replica)
                sys.exit(120)

        run_or_exit(replica, '/usr/local/yandex/pgswitch/convert_master.sh 9.4 %s' % master, runas='postgres')
        if options.need_remount:
            remount_catalogs(replica, options)
        run_or_exit(replica, '/etc/init.d/postgresql-9.4 start')
        run_or_exit(replica, '/etc/init.d/pgbouncer start')
        bydlog("Seems that %s has been upgraded successfully. Unbelievable!" % replica)

In last step right `recovery.conf` is created with our custom script.

After upgrade of the first replica it opens for load and at this monent the
second replica closes from load and is being upgraded. This is the hardest
stage of upgrading because master is closed, replica with 9.3 is closed and the
only host serving load is replica with 9.4 and without any statistics
(unfortunatelly, pg_upgrade does not transfer statistics for optimizer).

#####Starting up

After upgrading of all replicas master is opening for load.

    :::python
    def start_master(master, options):
        run_or_exit(master, 'iptables -D INPUT -p tcp -m tcp --dport 5432 -j REJECT && ip6tables -D INPUT -p tcp -m tcp --dport 5432 -j REJECT')
        run_or_exit(master, '/etc/init.d/postgresql-9.4 start')
        run_or_exit(master, '/etc/init.d/pgbouncer start')

        cmd = '/var/lib/pgsql/analyze_new_cluster.sh'
        run_or_exit(master, cmd, runas='postgres')

At this moment all three hosts are up and ready for serving load. Dances,
happiness.

####Summary

We have upgraded several dozens of shards from 9.3.6 to 9.4.1 with read-only
degradation for less than three minutes on each shard. On a couple os shards
we catched some special effects and script failed. So we had to update them
manually. Well that the sequence of steps is clear and manual work reduced
to invoking commands from script. It, however, took more time, about 7 minutes
per shard.

And for dessert... we have already caught a rare
[bug](http://www.postgresql.org/message-id/20150330162247.2492.923@wrigleys.postgresql.org)
with 9.4.1 and Tom Lane has made a patch to fix the problem in 38 minutes (!)
from creating a bug report. It is very cool.
