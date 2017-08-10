#!/bin/bash
#
# reset model data and schema, clear cache
#
python manage.py flush_model --model all --threads 9
python manage.py migrate --model all --threads 9
python manage.py clear_cache --prefix all
python manage.py load_data --path ../tests/fixtures/ --threads 11
sleep 2
python manage.py preparemq
python manage.py load_diagrams

# if you really need comment out following lines
# it creates new files, unless there is no changed literals to be translated
# python manage.py extract_translations
# python manage.py compile_translations
