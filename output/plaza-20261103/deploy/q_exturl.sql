SELECT name, REGEXP_SUBSTR(UTF8TOSTRING(data), '"[^"]*external-url[^"]*"\s*:\s*"[^"]*"') AS HIT
FROM extensions
WHERE UTF8TOSTRING(data) LIKE '%external-url%';
