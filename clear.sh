#!/bin/bash

if [ "$1" == 'y' ]; then
    confirm='y'
else
    read -p 'Are you sure (y/n): ' confirm
fi

if [ $confirm == 'y' ]; then
    rm -rf app.db
    rm -rf migrations
    flask db init
    flask db migrate -m "initial version of the database"
    flask db upgrade
fi