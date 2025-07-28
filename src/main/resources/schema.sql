--Comment out code
--DROP TABLE IF EXISTS todo;
CREATE TABLE IF NOT EXISTS todo (id SERIAL PRIMARY KEY, description VARCHAR(255), details VARCHAR(4096), done BOOLEAN);
