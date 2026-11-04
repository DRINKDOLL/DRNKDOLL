CALL CSVWRITE('/tmp/sys.csv', 'SELECT UTF8TOSTRING(data) AS D FROM extensions WHERE name = ''/registry/configmaps/system''');
