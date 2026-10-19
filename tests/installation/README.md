# MySQL installer regression checks

Run with Python 3.8 or newer and Bash:

```sh
python3 tests/installation/test_mysql_install.py
```

The tests run the actual `scripts/mysql_install.sh` in disposable directories.
A fake `mysql` executable records commands and simulates failures; no database
is contacted or modified. Fixtures contain generated test credentials only.

The nine test groups cover remote-host routing, selected-database grants and
imports, default settings, Romanian/Italian country codes, cancellation, missing
language data, invalid database names, password escaping and file permissions,
and credential cleanup after success, MySQL failures, and termination.

The installer now requires `yes` before replacing existing data and stops on the
first failing command. Run it from the unpacked installation directory containing
`data/blueseer.schema` and the language data. Database names may contain 1–64
letters, digits, or underscores.
