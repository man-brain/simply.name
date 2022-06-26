Title: Ещё один способ раскрасить psql
Date: 2014-11-07 21:00
Modified: 2015-05-10 20:00
Category: PostgreSQL
Tags: PostgreSQL, psql
Lang: ru
Slug: yet-another-psql-color-prompt

В этом посте вы найдёте скриншоты и конфиги ещё одного раскрашивания цветом psql. Целью было сделать такую цветовую схему, которая одинаково хорошо бы смотрелась на терминалах со светлым и тёмным фонами.

Пример файла `.bashrc`:

    :::bash
    #!/bin/bash

    export YELLOW=`echo -e '\033[1;33m'`
    export LIGHT_CYAN=`echo -e '\033[1;36m'`
    export GREEN=`echo -e '\033[0;32m'`
    export NOCOLOR=`echo -e '\033[0m'`
    export LESS="-iMSx4 -FXR"
    export PAGER="sed \"s/^\(([0-9]\+ [rows]\+)\)/$GREEN\1$NOCOLOR/;s/^\(-\[\ RECORD\ [0-9]\+\ \][-+]\+\)/$GREEN\1$NOCOLOR/;s/|/$GREEN|$NOCOLOR/g;s/^\([-+]\+\)/$GREEN\1$NOCOLOR/\" 2>/dev/null | less"

И соответствующий ему пример `.psqlrc`:

    :::PostgresConsoleLexer
    \set QUIET 1
    \set ON_ERROR_ROLLBACK interactive
    \set VERBOSITY verbose
    \x auto
    \set PROMPT1 '%[%033[38;5;27m%]%`hostname -s`%[%033[38;5;102m%]/%/ %[%033[31;5;27m%]%`/var/lib/pgsql/.role.sh`%[%033[0m%] %# '
    \set PROMPT2 ''
    \set HISTFILE ~/.psql_history- :DBNAME
    \set HISTCONTROL ignoredups
    \pset null [null]
    \pset pager always
    \timing
    \unset QUIET

Скрипт для определения роли машины (`/var/lib/pgsql/.role.sh`) весьма простой:

    :::bash
    #!/bin/bash

    res=`psql postgres -t -A -c 'show transaction_read_only;'`
    if [ $res == 'off' ]; then
        echo 'M'
    else
        echo 'R'
    fi

И конечно же, скриншоты psql с такими настройками:
[![Colorized psql for dark backgrounds]({static}/images/psql1.png)]({static}/images/psql1.png)

[![Colorized psql for light backgrounds]({static}/images/psql2.png)]({static}/images/psql2.png)

Наслаждайтесь!
