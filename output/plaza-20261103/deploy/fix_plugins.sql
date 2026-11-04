UPDATE extensions
SET data = STRINGTOUTF8(REGEXP_REPLACE(UTF8TOSTRING(data),
        'file:///C:[^"]*/plugins/',
        'file:///opt/plaza/workdir/plugins/'))
WHERE name LIKE '/registry/plugin.halo.run/plugins/%';

SELECT name, REGEXP_SUBSTR(UTF8TOSTRING(data), 'file:[^"]*') AS URI
FROM extensions
WHERE name LIKE '/registry/plugin.halo.run/plugins/%'
ORDER BY name;
