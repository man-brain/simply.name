#!/usr/bin/env python
# -*- coding: utf-8 -*- #
from __future__ import unicode_literals

AUTHOR = 'd0uble'
SITENAME = 'Yet another blog'
SITEURL = 'https://simply.name'
PATH = 'content'
TIMEZONE = 'Europe/Moscow'
DEFAULT_LANG = 'en'
DISPLAY_CATEGORIES_ON_MENU = False
MENUITEMS = (
            ('Russian', '/ru'),
            ('PostgreSQL', '/tag/postgresql.html'),
            )
TAG_CLOUD_MAX_ITEMS = 10
THEME = 'themes/pelican-bootstrap3'
TYPOGRIFY = True
DEFAULT_DATE_FORMAT = '%a %d %b %Y'

# Feed generation is usually not desired when developing
FEED_ALL_ATOM = 'feeds/all.xml'
CATEGORY_FEED_ATOM = 'feeds/%s.xml'
TRANSLATION_FEED_ATOM = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None

# Blogroll
#LINKS = (
#         ('Videos', 'https://events.yandex.ru/lib/people/338694/'),
#        )

# Social widget
SOCIAL = (
          ('github', 'https://github.com/dev1ant'),
          ('twitter', 'https://twitter.com/man_brain'),
          ('rss', '/feeds/all.xml'),
         )

DEFAULT_PAGINATION = 5

# Uncomment following line if you want document-relative URLs when developing
#RELATIVE_URLS = True

# pelican-bootstrap3 settings
BOOTSTRAP_THEME = 'cerulean'
DISPLAY_CATEGORIES_ON_SIDEBAR = False
DISPLAY_RECENT_POSTS_ON_SIDEBAR = False
DISPLAY_TAGS_ON_SIDEBAR = True
DISPLAY_TAGS_INLINE = True
PYGMENTS_STYLE = 'solarizedlight'
#ADDTHIS_PROFILE = 'ra-54a6b4f42fe712f5'
#ADDTHIS_DATA_TRACK_ADDRESSBAR = False
#ADDTHIS_GOOGLE_PLUSONE = False
#CC_LICENSE = 'CC-BY'
DISQUS_SITENAME = 'simplyname'
#ABOUT_ME = 'System administrator working in <a href="yandex.com">Yandex</a>.\
# Recently mostly with PostgreSQL databases.'
#AVATAR = '/images/photo.png'

PLUGIN_PATHS = ['plugins', ]
PLUGINS = ['i18n_subsites', ]
I18N_SUBSITES = {
    'ru': {
        'SITENAME': 'Ещё один блог',
        'THEME': 'themes/pelican-bootstrap3',
        'SITEURL': 'https://simply.name/ru',
        'MENUITEMS': (
            ('English', 'https://simply.name'),
            ('PostgreSQL', '/ru/category/postgresql.html'),
            ),
        'SOCIAL': (
          ('github', 'https://github.com/dev1ant'),
          ('twitter', 'https://twitter.com/man_brain'),
          ('rss', '/ru/feeds/all.xml'),
         ),
#        'ABOUT_ME': 'Системный администратор Яндекс.Почты. В последнее время \
#                занимаюсь в основном PostgreSQL.',
        }
    }
I18N_UNTRANSLATED_ARTICLES = 'remove'
