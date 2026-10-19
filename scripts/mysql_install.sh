#!/bin/bash

set -e

###  This script essentially does three things :
###  1) creates database schema
###  2) creates user 'bs_user' with password
###  3) loads some default data from
###  comma delimited (and some semicolon delimited) files found in the data/* directory
###
###
###  The database schema can be found in data/blueseer.schema (See below 
###  where it attempts to create this
###  User is a simple 'create' statement....the bs.cfg file created below has 
###  the USER and PASS variables set with 'bs_user' and 'bsPasswd' respectively.
###  new versions of mysql have stricter requirements for the password.   
###  You should obviously change this in a production environment anyway.  If you do,
###  make sure you change it in the bs.cfg file as well...for each client user
###  NOTE!!!  newer version of MySQL set security variables by default to
###  prevent loading data from local directories.  You will have to adjust the 
###  Global variable 'local_infile' in your MySQL instance.  Something like:
###  'show global variables like 'local_infile';
###  'set global local_infile = 'ON';

defaulthost=localhost
defaultlang=en

echo ''
echo ''
echo ''
echo "NOTE: This script file loads data from files in the data dir into "
echo "your MySQL instance.  Newer versions of MySQL have a security  "
echo "feature which disables loading using 'local data infile'.  "
echo "You may need to ensure this is enabled before loading the data. "
echo "Read the comments in this script for determining this setting "
echo ""
echo ""
echo ""
echo -n "Previous Data will be lost... are you sure you want to install database? (enter: yes or no): "
read -r confirm
if [[ "$confirm" != "yes" ]]; then
    exit 0
fi

echo -n "Enter the IP addr of database server: 'localhost' default=localhost: "
read -r IP

if [[ "$IP" == "" ]]; then
	IP=$defaulthost
fi

echo -n "Enter the administrator password for the MySQL Database: "
IFS= read -r -s PASS
echo ""
echo ""
echo -n "Enter database name (Default = bsdb): "
read -r DB
if [[ "$DB" == "" ]]; then
	DB="bsdb"
fi
if [[ ! "$DB" =~ ^[a-zA-Z0-9_]+$ || ${#DB} -gt 64 ]]; then
    echo "Database name must contain 1-64 letters, digits or underscores." >&2
    exit 1
fi
echo ""
echo ""
echo "choose your two character language code from the options below..."
echo "en=english"
echo "fr=french"
echo "es=spanish"
echo "tr=turkish"
echo "de=german"
echo -n "Enter the two character language code (en, es, fr, etc) default=en: "
read -r LANG

if [ ${#LANG} -ge 3 ]; then echo "you entered more than two characters...try again"; exit 1
else
	echo "you enter $LANG ...proceeding"
fi


if [[ "$LANG" == "" ]]; then
	LANG=$defaultlang
fi

LANG=$(printf '%s' "$LANG" | tr '[:upper:]' '[:lower:]')
if [[ ! "$LANG" =~ ^[a-z][a-z]$ || ! -f "data/$LANG/sq_mysql.txt" || ! -f data/blueseer.schema ]]; then
    echo "Missing schema or language data for $LANG; run from the installation directory." >&2
    exit 1
fi

COUNTRY="US"
if [[ "$LANG" == "es" ]]; then
	COUNTRY="ES"
fi
if [[ "$LANG" == "fr" ]]; then
	COUNTRY="FR"
fi
if [[ "$LANG" == "tr" ]]; then
	COUNTRY="TR"
fi
if [[ "$LANG" == "de" ]]; then
	COUNTRY="DE"
fi
if [[ "$LANG" == "ro" ]]; then
	COUNTRY="RO"
fi
if [[ "$LANG" == "it" ]]; then
	COUNTRY="IT"
fi


# Keep credentials out of the process arguments and environment. An absolute
# filename remains valid when loading the language data from a subdirectory.
umask 077
mysql_defaults=$(mktemp "${TMPDIR:-/tmp}/blueseer-mysql.XXXXXX")
trap 'rm -f "$mysql_defaults"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mysql_password=${PASS//\\/\\\\}
mysql_password=${mysql_password//\"/\\\"}
mysql_password=${mysql_password//$'\t'/\\t}
mysql_password=${mysql_password//$'\r'/\\r}
printf '[client]\npassword="%s"\n' "$mysql_password" > "$mysql_defaults"
unset PASS mysql_password MYSQL_PWD
mysql_options=(--defaults-extra-file="$mysql_defaults" --host="$IP" --user=root)

echo ""
echo ""
echo "creating blueseer config file...."
echo "DBTYPE=mysql" >bs.cfg
echo "DB=$DB" >>bs.cfg
echo "USER=bs_user" >>bs.cfg
echo "PASS=bsPasswd" >>bs.cfg
echo "IP=$IP" >>bs.cfg
echo "PORT=3306" >>bs.cfg
echo "DRIVER=com.mysql.cj.jdbc.Driver" >>bs.cfg
echo "LANGUAGE=$LANG" >>bs.cfg
echo "COUNTRY=$COUNTRY" >>bs.cfg

cd data

echo "creating database schema for database $DB...."
mysql "${mysql_options[@]}" -e "drop database if exists \`$DB\`;"
mysql "${mysql_options[@]}" -e "create database if not exists \`$DB\` character set utf8mb4 collate utf8mb4_unicode_ci;"
mysql "${mysql_options[@]}" -e "drop user if exists 'bs_user'@'%' ;"
mysql "${mysql_options[@]}" -e "create user if not exists 'bs_user'@'%' identified by 'bsPasswd';"
mysql "${mysql_options[@]}" -e "grant select,insert,delete,update on \`$DB\`.* to 'bs_user'@'%';"
mysql "${mysql_options[@]}" -e "set global local_infile = 'ON';"

#  The next line loads the database and table definitions
mysql "${mysql_options[@]}" --local-infile=1 "$DB" <blueseer.schema

echo "Loading some data....."
cd "$LANG"
mysql "${mysql_options[@]}" --local-infile=1 "$DB" <sq_mysql.txt
cd ..



echo 'Finished install!   '
echo ''
echo ''
echo ''
echo ''
echo ''
echo 'you can launch by running ./login.sh in the parent directory'
echo 'you may have to set perms to 755 on login.sh'
echo ''
echo ''
echo 'Optionally...you can launch by typing the following at the command line: '
echo 'NOTE:  make sure you are in the parent blueseer directory!! '
echo ''
echo ''
echo 'jre26/bin/java -cp ".:dist/*" bsmf.MainFrame'
echo ''
echo ''
echo 'NOTE:'
echo 'login and password are admin and admin respectively'
echo ''
echo ''
