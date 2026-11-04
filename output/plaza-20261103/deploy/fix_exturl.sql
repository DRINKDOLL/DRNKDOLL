UPDATE extensions
SET data = STRINGTOUTF8(REPLACE(UTF8TOSTRING(data), 'http://127.0.0.1:8092', 'http://8.138.34.151'))
WHERE name = '/registry/configmaps/system';

SELECT name, LENGTH(data) AS LEN,
       REGEXP_SUBSTR(UTF8TOSTRING(data), '"externalUrl":\\?"[^"\\]*') AS EXT
FROM extensions
WHERE name = '/registry/configmaps/system';
