-- Пользователь приложения с минимальными правами: владелец своей базы, но не суперпользователь.
-- Образ postgres выполняет этот файл один раз — когда том с данными ещё пустой.
-- Пароль берётся из переменной окружения SKLAD_DB_PASSWORD контейнера db (задаётся в .env).
\getenv password SKLAD_DB_PASSWORD

CREATE ROLE sklad LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
    CONNECTION LIMIT 20 PASSWORD :'password';
CREATE DATABASE sklad OWNER sklad;
REVOKE ALL ON DATABASE sklad FROM PUBLIC;
