Title: PostgreSQL and SystemTap
Date: 2014-12-08 21:00
Category: PostgreSQL
Tags: PostgreSQL, SystemTap, debugging, sources
Status: draft

Once upon a time we started having strange performance issues with writing-only
load on PostgreSQL 9.4 with huge shared_buffers. The problem itself is well
described [here](http://www.postgresql.org/message-id/0DDFB621-7282-4A2B-8879-A47F7CECBCE4@simply.name)
but it is not the topic of the post. And since PostgreSQL does not have
something like Oracle wait events interface yet, we have written a couple of
simple SystemTap scripts to determine the problem. Below are some details.

