Title: Обновление PostgreSQL до 9.4
Date: 2015-03-31 18:00
Category: PostgreSQL
Tags: PostgreSQL, pg_upgrade, rsync
Lang: ru
Slug: upgrading-postgres-to-9.4

####Пролог

В 9.4 появилась логическая репликация. А потому с 9.4 на 9.5 можно будет
обновиться весьма дёшево (по крайней мере так
[должно](https://wiki.postgresql.org/wiki/UDR_Online_Upgrade) быть). Ну а прямо
сейчас обновление мажорной версии PostgreSQL - боль. В самом распространённом
варианте это выглядит так:

  1. Необходимо полностью потушить мастер и дёрнуть `pg_upgrade`.
  2. Взлететь с новой версией только мастером.
  3. Сделать полный бэкап с обновлённого мастера.
  4. Переналить все реплики из нового бэкапа.

У нас есть базы объёмом в единицы терабайт, каждый шард которых состоит из трёх
машин - мастера и двух реплик. Значительная часть читающих запросов летит в
реплики. И есть такие базы, где мы умеем переживать смерть только одной реплики.
Т.е. если обе реплики умрут, один мастер не вытащит на себе всю пишущую и
читающую нагрузку. А сделать полный бэкап базки в пару терабайт и развернуть
его хотя бы на одну реплику за ночь - не самая простая задача.

####Луч надежды

Когда мы уже собрались обновляться в ночь с субботы на воскресенье и страдать,
Bruce Momjian прислал
[патч](http://www.postgresql.org/message-id/20150219165755.GA18714@momjian.us)
к документации, позволяющий выполнить upgrade и всех реплик без переналивки из
бэкапа. Патч в итоге применён к мастеру, т.е. в документации для 9.5 уже
[есть](http://www.postgresql.org/docs/devel/static/pgupgrade.html) необходимые
шаги.

Единственным минусом этого решения является тот факт, что в момент обновления
потушены должны быть все машины кластера (т.е. база недоступна даже для чтения).
Такое ограничение нам тоже не очень понравилось, потому мы решили сделать
немного по-другому.

####Реализация

Поскольку базок у нас несколько десятков, выполнять обновление руками на каждой
из них очень не хотелось, потому я написал простой скрипт для этого. При этом
скрипт очень тупой - при любой проблеме он немедленно падает и дальше необходимо
доделывать руками.

Поскольку скрипт тесно провязан с нашей инфраструктурой, я публикую лишь
некоторые кусочки из него, отражающие суть. Общая последовательность достаточно
простая (ставим на все машины пакеты 9.4, обновляем мастер, делаем rsync на
каждую из реплик, взлетаем мастером):

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

Такая последовательность продлевает время жизни в read-only (мастером можно
взлетать после обновления первой реплики), но совсем исключает необходимость
переналивки реплик из бэкапов.

#####Обновление мастера

Обновление мастера, наверное, самый насыщенный этап:

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

Сначала делается `pg_upgrade --check` и если есть какие-то проблемы, то всё
возвращается на место. Это единственное место, где так происходит. Во всех
остальных случаях скрипт просто падает.

Затем притаскиваются наши конфигурационные файлы и мастер закрывается от реплик
межсетевым экраном, потому что (сюрприз!) реплики с 9.3 могут тащить изменения
с мастера с 9.4. Ничем хорошим это, правда, не закончится.

Важным является тот факт, что с момента остановки pgbouncer на мастере вся
нагрузка льётся в реплики, т.е. кластер деградирует в read-only.

#####Обновление реплик

Обновление реплик происходит последовательно:

    :::python
    def rsync_replicas(master, hosts, options):
        hosts.remove(master)
        for replica in hosts:
            rsync_one_replica(master, replica, options)
            time.sleep(5)

В самой функции по большому счёту не делается ничего, кроме rsynс:

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

Последний шаг создаёт правильный `recovery.conf`, чтобы повернуть реплику на
правильного мастера.

После обновления первой реплики она открывается для нагрузки, а в этот момент
вторая закрывается и обновляется. Это самый сложный этап обновления, потому что
мастер закрыт, реплика с 9.3 закрыта и единственная машина, обслуживающая
нагрузку, - реплика с 9.4, у которой совсем нет никакой статистики (к
сожалению, pg_upgrade не переносит статистику).

#####Взлёт

После обновления всех реплик мастер открывается для нагрузки.

    :::python
    def start_master(master, options):
        run_or_exit(master, 'iptables -D INPUT -p tcp -m tcp --dport 5432 -j REJECT && ip6tables -D INPUT -p tcp -m tcp --dport 5432 -j REJECT')
        run_or_exit(master, '/etc/init.d/postgresql-9.4 start')
        run_or_exit(master, '/etc/init.d/pgbouncer start')

        cmd = '/var/lib/pgsql/analyze_new_cluster.sh'
        run_or_exit(master, cmd, runas='postgres')

В этот момент все три машины доступны для обслуживания нагрузки. Танцы,
радость.

####Итоги

Несколько десятков шардов мы обновили с 9.3.6 на 9.4.1 с нахождением в read-only
каждого из них менее трёх минут. На паре шардов вылезли спецэффекты, скрипт упал
и потому пришлось их обновлять руками, но последовательность шагов чёткая и
действия руками сводились к выполнению того же, что написано в скрипте. Времени,
правда, это, конечно, заняло побольше, около 7 минут на шард.

И на сладкое скажу, что мы уже наступили на редкий
[баг](http://www.postgresql.org/message-id/20150330162247.2492.923@wrigleys.postgresql.org),
патч с решением которого Tom Lane наваял за 38 минут (!) с момента создания bug
report. Это очень круто.
