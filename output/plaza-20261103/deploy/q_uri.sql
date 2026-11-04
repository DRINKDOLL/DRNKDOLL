SELECT name, REGEXP_SUBSTR(UTF8TOSTRING(data), 'file:[^"]*') AS URI FROM extensions WHERE name LIKE '/registry/plugin.halo.run/plugins/%' ORDER BY name;
