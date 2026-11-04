SELECT name, LENGTH(data) AS LEN, LEFT(UTF8TOSTRING(data), 200) AS HEAD FROM extensions WHERE name LIKE '/registry/plugin.halo.run/plugins/%' ORDER BY name;
