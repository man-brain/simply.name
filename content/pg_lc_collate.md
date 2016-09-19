Title: Ещё раз про collation в PostgreSQL
Date: 2016-09-18 23:00
Category: PostgreSQL
Tags: PostgreSQL, i18n, initdb, lc_collate
Lang: ru
Slug: pg-lc-collate

Давненько я ничего не писал. Надо сдуть пыль с блога и написать что-нибудь
полезное :)

Когда люди начинают работать с PostgreSQL, они временами допускают
ошибки, которые потом очень сложно исправить. Например, в момент инициализации
первой базы ты слабо понимаешь, зачем нужно включать контрольные суммы для
данных. Тем более, что по-умолчанию они выключены, а в документации написано,
что они могут сильно просадить производительность.

А когда у тебя уже больше сотни баз с сотнями терабайт данных на самом разном
железе или (ещё хуже) в разных системах виртуализации, ты понимаешь, что готов
заплатить немножко производительности для определения тихого повреждения данных.
Но проблема в том, что дёшево включить контрольные суммы ты не можешь. Это
одна из тех вещей, которая задаётся один раз при выполнении команды `initdb`. В
светлом будущем надеемся на логическую репликацию, а пока единственный способ
это поменять -- это сделать `pg_dump`, `initdb`, `pg_restore`, т.е. с простоем.

И если контрольные суммы могут вам и не пригодиться (вдруг у вас безупречно
работающее аппаратное обеспечение и ОС без багов), то `lc_collate`, о котором
пойдёт речь, касается каждого. И сейчас я вам это докажу.

### Порядок сортировки

Допустим, вы поставили PostgreSQL из пакетов или собрали из исходников и
самостоятельно инициализировали базу. Скорее всего, в современном мире
победившего UTF-8 вы увидите нечто такое:

    :::BashSessionLexer
    d0uble ~ $ psql -l
                                   List of databases
       Name    | Owner  | Encoding |   Collate   |    Ctype    | Access privileges
    -----------+--------+----------+-------------+-------------+-------------------
     postgres  | d0uble | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
     template0 | d0uble | UTF8     | en_US.UTF-8 | en_US.UTF-8 | =c/d0uble        +
               |        |          |             |             | d0uble=CTc/d0uble
     template1 | d0uble | UTF8     | en_US.UTF-8 | en_US.UTF-8 | =c/d0uble        +
               |        |          |             |             | d0uble=CTc/d0uble
    (3 rows)

    d0uble ~ $

Если явно не указано другого, то `initdb` возьмёт настройки для столбцов 3-5
из операционной системы. И скорее всего, вам будет казаться, что если там есть
`UTF-8`, то всё будет хорошо. Однако, в некоторых случаях вы вполне себе можете
в этом засомневаться. Взгляните на следующий запрос, выполненный на
linux-машине:

    :::PostgresConsoleLexer
    linux> SELECT name FROM unnest(ARRAY[
        'MYNAME', ' my_name', 'my-image.jpg', 'my-third-image.jpg'
    ]) name ORDER BY name;
            name
    --------------------
     my-image.jpg
      my_name
     MYNAME
     my-third-image.jpg
    (4 rows)

    linux>

Такой порядок сортировки кажется очень странным. И это при том, что клиент
пришёл в базу с вполне себе адекватными настройками:

    :::PostgresConsoleLexer
    linux> SELECT name, setting FROM pg_settings WHERE category ~ 'Locale';
                name            |      setting
    ----------------------------+--------------------
     client_encoding            | UTF8
     DateStyle                  | ISO, MDY
     default_text_search_config | pg_catalog.english
     extra_float_digits         | 0
     IntervalStyle              | postgres
     lc_collate                 | en_US.UTF-8
     lc_ctype                   | en_US.UTF-8
     lc_messages                | en_US.UTF-8
     lc_monetary                | en_US.UTF-8
     lc_numeric                 | en_US.UTF-8
     lc_time                    | en_US.UTF-8
     server_encoding            | UTF8
     TimeZone                   | Europe/Moscow
     timezone_abbreviations     | Default
    (14 rows)

    linux>

Результат не зависит от дистрибутива -- по крайней мере в RHEL 6 и Ubuntu 14.04
он одинаковый. Ещё более странным является тот факт, что тот же запрос с теми
же настройками сервера и клиента в Mac OS X даст другой результат:

    :::PostgresConsoleLexer
    macos> SELECT name FROM unnest(ARRAY[
        'MYNAME', ' my_name', 'my-image.jpg', 'my-third-image.jpg'
    ]) name ORDER BY name;
            name
    --------------------
      my_name
     MYNAME
     my-image.jpg
     my-third-image.jpg
    (4 rows)

    macos>

На первый взгляд кажется, что linux серьёзно сломан в этом месте. Но проблема
не в этом, а в том, что результат, зависящий от операционной системы, - очень
плохой результат. К счастью, мы обнаружили странное поведение на этапе
тестирования - тесты на ноутбуке разработчика проходили нормально, а на
тестовом linux-сервере падали.

Причиной тому является тот факт, что правила сортировки PostgreSQL берёт из ОС,
и (сюрприз!) UTF-8 бывает разный ¯\\\_(ツ)_/¯ Если поискать, то можно найти
множество тредов про различное поведение в Linux и Mac OS X (
[1](http://stackoverflow.com/questions/16328592),
[2](https://www.postgresql.org/message-id/flat/23053.1337036410%40sss.pgh.pa.us#23053.1337036410@sss.pgh.pa.us),
[3](http://stackoverflow.com/questions/27395317),
[4](https://www.postgresql.org/message-id/4B4E845F.80906@postnewspapers.com.au),
[5](http://dba.stackexchange.com/questions/106964),
[6](http://dba.stackexchange.com/questions/94887)).

На вопрос "кто виноват?" мнения расходятся, но можно уверенно сказать, что
Mac OS X точно учитывает не все региональные специфики. Это видно по ссылкам
выше или, например, можно продемонстрировать вот таким примером для русского
языка:

    :::PostgresConsoleLexer
    macos> SELECT name FROM unnest(ARRAY[
        'а', 'д', 'е', 'ё', 'ж', 'я'
    ]) name ORDER BY name;
     name
    ------
     а
     д
     е
     ж
     я
     ё
    (6 rows)

    macos>

Linux при этом с таким запросом справляется логично с моей точки зрения. И даже
вполне себе можно объяснить результат первого запроса, показанный им - linux
просто игнорирует символы пробела, `-` и `_` при сортировке. Т.е. если немного
разобраться, то сломанной уже выглядит Mac OS X.

В конце концов мы унесли тесты в docker, чтобы не зависеть от особенностей ОС и
получать детерменированные результаты, но есть и другие способы это сделать.
Самым простым из них является использование `LC_COLLATE = C`, потому что это
единственный collation, который поставляется вместе с PostgreSQL и не зависит
от ОС (см.
[документацию](https://www.postgresql.org/docs/current/static/charset.html)).

    :::PostgresConsoleLexer
    linux> SELECT name FROM unnest(ARRAY[
        'MYNAME', ' my_name', 'my-image.jpg', 'my-third-image.jpg'
    ]) name ORDER BY name COLLATE "C";
            name
    --------------------
      my_name
     MYNAME
     my-image.jpg
     my-third-image.jpg
    (4 rows)

    linux>

Как видно, в таком случае результаты будут одинаковыми в обеих ОС. Но нетрудно
заметить, что такими же как в Mac OS X, а это значит, что тоже с граблями для
мультибайтных кодировок, например:

    :::PostgresConsoleLexer
    linux> SELECT name FROM unnest(ARRAY[
        'а', 'д', 'е', 'ё', 'ж', 'я'
    ]) name ORDER BY name COLLATE "C";
     name
    ------
     а
     д
     е
     ж
     я
     ё
    (6 rows)

    linux>

Не стоит при этом думать, что результат сортировки с `LC_COLLATE=en_US.UTF-8` в
Mac OS X всегда будет таким же как с `LC_COLLATE=C` в любой ОС. Наверняка можно
быть уверенным лишь в том, что одинаковый результат гарантирует collation `C`,
потому что он поставляется вместе с PostgreSQL и не зависит от ОС.

При этом мне с чисто обывательской точки зрения обычного пользователя кажется
странным не учитывать пробельные символы, дефисы и другие неалфавитные символы
в сортировке, но эти правила когда-то кто-то придумал, стандартизировал и не
мне их менять. Впрочем, в исходной задаче эти правила оказались недопустимыми
и мы стали использовать collation `C`.

### Запросы по префиксу

Тот факт, что postgres опирается на glibc в вопросах сортировки, имеет ещё ряд
нюансов, о которых стоит сказать. Для примера создадим следующую табличку с
двумя текстовыми полями и вставим в неё один миллион случайных строчек:

    :::PostgresConsoleLexer
    linux> CREATE TABLE sort_test (
        a text,
        b text COLLATE "C");
    CREATE TABLE
    linux> INSERT INTO sort_test SELECT md5(n::text), md5(n::text)
        FROM generate_series(1, 1000000) n;
    INSERT 0 1000000
    linux> CREATE INDEX ON sort_test USING btree (a);
    CREATE INDEX
    linux> CREATE INDEX ON sort_test USING btree (b);
    CREATE INDEX
    linux> ANALYZE sort_test ;
    ANALYZE
    linux> SELECT * FROM sort_test LIMIT 2;
                    a                 |                b
    ----------------------------------+----------------------------------
     c4ca4238a0b923820dcc509a6f75849b | c4ca4238a0b923820dcc509a6f75849b
     c81e728d9d4c2f636f067f89cc14862c | c81e728d9d4c2f636f067f89cc14862c
    (2 rows)

    linux>

Одно поле создано с collation по-умолчанию (`en_US.UTF-8` в моём примере),
а второе с collation `C`, значения в них одинаковые. Посмотрим на планы
запросов по префиксу каждого из полей:

    :::PostgresConsoleLexer
    linux> explain SELECT * FROM sort_test WHERE a LIKE 'c4ca4238a0%';
                               QUERY PLAN
    ----------------------------------------------------------------
     Seq Scan on sort_test  (cost=0.00..24846.00 rows=100 width=66)
       Filter: (a ~~ 'c4ca4238a0%'::text)
    (2 rows)

    linux> explain SELECT * FROM sort_test WHERE b LIKE 'c4ca4238a0%';
                                         QUERY PLAN
    ------------------------------------------------------------------------------------
     Index Scan using sort_test_b_idx on sort_test  (cost=0.42..8.45 rows=100 width=66)
       Index Cond: ((b >= 'c4ca4238a0'::text) AND (b < 'c4ca4238a1'::text))
       Filter: (b ~~ 'c4ca4238a0%'::text)
    (3 rows)

    linux>

Как видно, PostgreSQL не использует индекс для выполнения первого запроса, но
использует для второго. Причину этого можно увидеть в выводе EXPLAIN (см.
`Index Cond`) - во втором случае PostgreSQL знает порядок символов и
преобразовывает условие выборки по индексу с `b LIKE 'c4ca4238a0%'` в
`b >= 'c4ca4238a0' AND b < 'c4ca4238a1'`, а эти две операции хорошо
покрываются B-Tree (и только потом полученные результаты postgres уже
дофильтрует по исходному условию).

Как видно, стоимость такого запроса при collation `C` примерно в 2500 раз
меньше.

### Abbreviated keys

Одной из хороших оптимизаций, которая появилась с выходом PostgreSQL 9.5, были
т.н. abbreviated keys, что можно перевести на русский как "сокращённые ключи".
Лучше всего об этом почитать в
[посте автора](http://pgeoghegan.blogspot.ru/2015/01/abbreviated-keys-exploiting-locality-to.html)
этой оптимизации, Peter Geoghegan. Если коротко, то эта оптимизация значительно
ускорила сортировку текстовых полей и создание индексов по ним, примеры можно
посмотреть, например,
[тут](https://www.depesz.com/2015/01/27/waiting-for-9-5-use-abbreviated-keys-for-faster-sorting-of-text-datums/).

К сожалению, в 9.5.2 эту оптимизацию
[выключили](https://git.postgresql.org/gitweb/?p=postgresql.git;a=commitdiff;h=3df9c374e279db37b00cd9c86219471d0cdaa97c)
для всех collation кроме `C`. Причиной тому стал баг в glibc (а как мы помним,
для всех сollation кроме `C` PostgreSQL опирается на glibc), в результате
которого индексы могли получаться неконсистентными.

### Вместо заключения

В задаче, с которой всё началось, мы в конце концов пришли к использованию
`lc_collate = C`, потому что данные предполагают использование самых разных
языков мира и этот collation кажется самым правильным для таких случаев. Да,
он не будет учитывать некоторые пограничные случаи в каждом из языков, но зато
будет работать вмеру хорошо для всех.

При этом грустно, что серебряной пули не бывает и когда все твои данные,
например, на русском, ты вынужден выбирать между производительностью и
правильностью сортировки с учётом специфики русского языка.
